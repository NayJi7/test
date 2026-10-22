"""graphify-local : pipeline de construction pilote par Kiro.

Remplace les blocs ``python -c "..."`` du skill d'origine par quatre commandes
fixes, auditables et testees. L'agent Kiro n'execute plus de code Python libre :
il ne lance que ``graphify kiro <etape>``.

    graphify kiro prepare [CHEMIN] [--update] [--deep] [--force]
        Detection des fichiers (avec exclusion des secrets), extraction AST du
        code, verification du cache semantique, decoupage des documents en lots
        et ecriture, pour chaque lot, d'un fichier de mission
        ``graphify-out/kiro/chunk_NN.task.md`` destine a un sous-agent Kiro.

    graphify kiro status
        Etat des lots : ecrits, manquants.

    graphify kiro finalize [--directed] [--no-viz] [--force]
        Validation stricte des fichiers JSON ecrits par les sous-agents,
        mise en cache, fusion code + documents, construction du graphe,
        communautes, rapport, manifeste, export HTML. Affiche les communautes a
        nommer.

    graphify kiro labels FICHIER.json
        Applique les noms de communautes choisis par l'agent (valides et
        nettoyes), regenere rapport, graph.json et HTML.

    graphify kiro verify
        Auto-controle de l'installation : verrou anti-fuite actif, modules
        reseau absents, bibliotheques HTML intactes.

Aucune de ces etapes n'appelle d'IA ni le reseau : tout est local. Le travail
"intelligent" (lire les documents, nommer les communautes) est fait par Kiro.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from graphify.paths import out_path, write_json_atomic

STATE_DIRNAME = "kiro"
PLAN_NAME = "plan.json"
SPEC_RELPATH = Path("skills") / "kiro" / "references" / "extraction-spec.md"

MAX_FILES_PER_CHUNK = 20
MAX_LINES_PER_CHUNK = 6000
SOLO_LINES = 2000
MAX_NODES_PER_CHUNK = 3000
MAX_EDGES_PER_CHUNK = 10000
MAX_HYPEREDGES_PER_CHUNK = 10
MAX_LABEL_LEN = 200
MAX_RATIONALE_LEN = 600
MAX_COMMUNITY_NAME_LEN = 60

_NODE_KEYS = {
    "id", "label", "file_type", "source_file", "source_location", "source_url",
    "captured_at", "author", "contributor", "rationale",
}
_EDGE_KEYS = {
    "source", "target", "relation", "confidence", "confidence_score",
    "source_file", "source_location", "weight",
}
_HYPEREDGE_KEYS = {"id", "label", "nodes", "relation", "confidence", "confidence_score", "source_file"}
_TOP_KEYS = {"nodes", "edges", "hyperedges", "coverage", "input_tokens", "output_tokens"}
_FILE_TYPES = {"code", "document", "paper", "image", "rationale", "concept"}
_CONFIDENCES = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
_RELATION_RE = re.compile(r"^[a-z][a-z0-9_]{0,48}$")
_ID_RE = re.compile(r"^[\w.:-]{1,256}$")

# Texte qui ressemble a une instruction ou a une commande plutot qu'a un
# libelle de connaissance. Un element de graphe qui en contient est ecarte :
# il pourrait etre relu plus tard par l'agent principal (injection indirecte).
_SUSPICIOUS_RE = re.compile(
    r"(?i)("
    r"ignore (all |the |any )?(previous|prior|above) (instructions|rules)|"
    r"ignore[rz]? (les|toutes les) (instructions|consignes|regles)|"
    r"disregard (the|all|previous)|system prompt|prompt syst[eè]me|"
    r"you are now|tu es maintenant|new instructions|nouvelles instructions|"
    r"\b(curl|wget|invoke-webrequest|iwr|nc|ncat|netcat|scp|sftp|ssh|ftp|telnet)\s+\S|"
    r"\bpowershell\b|\bbash\s+-c\b|\bsh\s+-c\b|\bpython3?\s+-c\b|"
    r"\bbase64\s+(-d|--decode)\b|"
    r"<\s*/?\s*(script|iframe|img|svg)\b|javascript:|"
    r"\bexfiltr"
    r")"
)

_SEM_TYPES = ("document", "paper", "image")


# --------------------------------------------------------------------------- #
# Utilitaires
# --------------------------------------------------------------------------- #

def _state_dir() -> Path:
    return out_path(STATE_DIRNAME)


def _spec_path() -> Path:
    return Path(__file__).parent / SPEC_RELPATH


def _die(msg: str, code: int = 1) -> None:
    print(f"[graphify kiro] erreur : {msg}", file=sys.stderr)
    sys.exit(code)


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _line_count(path: Path) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _clean_text(value, max_len: int) -> str | None:
    from graphify.security import sanitize_label

    if value is None:
        return None
    if not isinstance(value, str):
        return None
    text = sanitize_label(value)[:max_len].strip()
    return text or None


def _is_suspicious(*values) -> bool:
    return any(isinstance(v, str) and _SUSPICIOUS_RE.search(v) for v in values)


def _rel(path: str | Path, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


# --------------------------------------------------------------------------- #
# prepare
# --------------------------------------------------------------------------- #

def _pdf_sidecar(pdf: Path, state: Path) -> Path | None:
    """Convertit un PDF en texte local (pypdf) pour que le sous-agent lise du texte."""
    import hashlib
    from graphify.detect import extract_pdf_text

    try:
        text = extract_pdf_text(pdf) or ""
    except Exception:
        text = ""
    if not text.strip():
        return None
    digest = hashlib.sha256(str(pdf.resolve()).encode("utf-8")).hexdigest()[:16]
    target = state / "pdf-text" / f"{pdf.stem[:60]}-{digest}.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _make_chunks(items: list[dict]) -> list[list[dict]]:
    """Lots d'au plus 20 fichiers / 6000 lignes ; gros fichiers et images seuls."""
    chunks: list[list[dict]] = []
    current: list[dict] = []
    lines = 0
    for it in sorted(items, key=lambda i: (str(Path(i["source_file"]).parent), i["source_file"])):
        solo = it["kind"] == "image" or it["lines"] > SOLO_LINES
        if solo:
            chunks.append([it])
            continue
        if current and (len(current) >= MAX_FILES_PER_CHUNK or lines + it["lines"] > MAX_LINES_PER_CHUNK):
            chunks.append(current)
            current, lines = [], 0
        current.append(it)
        lines += it["lines"]
    if current:
        chunks.append(current)
    return chunks


def _task_text(spec: str, chunk_no: int, total: int, files: list[dict], out_file: Path, deep: bool) -> str:
    listing = []
    for f in files:
        if f["read_path"] != f["source_file"]:
            listing.append(f"- LIRE : {f['read_path']}\n  source_file a ecrire : {f['source_file']}")
        else:
            listing.append(f"- {f['source_file']}")
    return (
        f"# Mission d'extraction graphify - lot {chunk_no} sur {total}\n\n"
        "Lis les fichiers ci-dessous et ecris le fichier JSON demande, selon les regles qui suivent.\n\n"
        "## Fichiers a lire (en entier)\n\n" + "\n".join(listing) + "\n\n"
        f"## Fichier a ecrire (un seul, JSON)\n\n{out_file}\n\n"
        f"DEEP_MODE : {'oui' if deep else 'non'}\n\n"
        "## Regles\n\n" + spec
    )


def cmd_prepare(argv: list[str]) -> None:
    from graphify.cache import check_semantic_cache
    from graphify.detect import detect, detect_incremental
    from graphify.extract import collect_files, extract
    from graphify.watch import _read_build_excludes, _read_build_gitignore

    update = False
    deep = False
    paths: list[str] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--update":
            update = True
        elif a == "--deep" or a == "--mode=deep":
            deep = True
        elif a == "--mode" and i + 1 < len(argv):
            deep = argv[i + 1] == "deep"
            i += 1
        elif a.startswith("--"):
            _die(f"option inconnue : {a}")
        else:
            paths.append(a)
        i += 1
    if len(paths) > 1:
        _die("un seul dossier a la fois.")
    root = Path(paths[0] if paths else ".").resolve()
    if not root.is_dir():
        _die(f"dossier introuvable : {root}")

    out_dir = out_path()
    out_dir.mkdir(parents=True, exist_ok=True)
    state = _state_dir()
    if state.exists():
        shutil.rmtree(state)
    state.mkdir(parents=True)

    excludes = _read_build_excludes(out_dir)
    gitignore = _read_build_gitignore(out_dir)
    if update:
        inc = detect_incremental(root, extra_excludes=excludes, gitignore=gitignore)
        work_files = inc.get("new_files", {}) or {}
        corpus_files = inc.get("files", {}) or {}
        deleted = list(inc.get("deleted_files", []) or [])
        detection = inc
        if not inc.get("new_total", 0) and not deleted:
            print("[graphify kiro] aucun fichier modifie depuis la derniere construction : rien a faire.")
            return
    else:
        detection = detect(root, extra_excludes=excludes, gitignore=gitignore)
        work_files = detection.get("files", {})
        corpus_files = work_files
        deleted = []

    # Rapport de detection
    print(f"[graphify kiro] corpus : {detection.get('total_files', 0)} fichiers, "
          f"~{detection.get('total_words', 0):,} mots ({root})")
    for t in ("code", "document", "paper", "image", "video"):
        n = len(work_files.get(t, []))
        if n:
            print(f"  {t:9s}: {n} fichier(s) {'a traiter' if update else ''}".rstrip())
    secrets = detection.get("secret_findings", []) or []
    if secrets:
        by_file: dict[str, list[str]] = {}
        for s in secrets:
            by_file.setdefault(s["file"], []).append(f"{s['rule']} l.{s['line']}")
        print(f"[graphify kiro] {len(by_file)} document(s) EXCLU(S) car ils contiennent un secret probable "
              "(ils ne seront jamais lus par un sous-agent) :")
        for f, rules in sorted(by_file.items()):
            print(f"  - {f} : {', '.join(rules[:5])}")
        print("  -> retirez le secret du document, ou faites approuver ce fichier par un humain "
              "dans .graphify-secrets-allow (voir la documentation).")
    sensitive = [s for s in detection.get("skipped_sensitive", []) if s not in {str(root / x['file']) for x in secrets}]
    if sensitive:
        print(f"[graphify kiro] {len(sensitive)} fichier(s) ignores (nom sensible ou format non pris en charge).")
    videos = work_files.get("video", [])
    if videos:
        print(f"[graphify kiro] {len(videos)} fichier(s) audio/video ignores : la transcription n'est pas "
              "disponible dans cette version de graphify. Deposez une transcription .txt/.md a la place.")

    # Extraction AST (locale, sans IA)
    code_paths: list[Path] = []
    for f in work_files.get("code", []):
        p = Path(f)
        code_paths.extend(collect_files(p) if p.is_dir() else [p])
    if code_paths:
        ast = extract(code_paths, cache_root=root, root=root)
        print(f"[graphify kiro] code : {len(ast.get('nodes', []))} noeuds, {len(ast.get('edges', []))} aretes (AST local)")
    else:
        ast = {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}
    write_json_atomic(state / "ast.json", ast, ensure_ascii=False)

    # Cache semantique
    sem_files = [f for t in _SEM_TYPES for f in work_files.get(t, [])]
    spec = _spec_path()
    mode = "deep" if deep else None
    cached_nodes, cached_edges, cached_hyper, uncached = check_semantic_cache(
        sem_files, root=root, mode=mode, prompt_file=spec
    ) if sem_files else ([], [], [], [])
    write_json_atomic(state / "cached.json", {
        "nodes": cached_nodes, "edges": cached_edges, "hyperedges": cached_hyper,
    }, ensure_ascii=False)

    # Lots pour les sous-agents
    kinds = {f: t for t in _SEM_TYPES for f in work_files.get(t, [])}
    items: list[dict] = []
    for f in uncached:
        p = Path(f)
        kind = kinds.get(f, "document")
        read_path = p
        if p.suffix.lower() == ".pdf":
            side = _pdf_sidecar(p, state)
            if side is None:
                print(f"[graphify kiro] PDF sans texte extractible, ignore : {_rel(p, root)}")
                continue
            read_path = side
        lines = 0 if kind == "image" else _line_count(read_path)
        items.append({"source_file": str(p), "read_path": str(read_path), "kind": kind, "lines": lines})
    chunks = _make_chunks(items)
    spec_text = spec.read_text(encoding="utf-8")
    plan_chunks = []
    for i, files in enumerate(chunks, start=1):
        out_file = (state / f"chunk_{i:02d}.json").resolve()
        task_file = (state / f"chunk_{i:02d}.task.md").resolve()
        task_file.write_text(_task_text(spec_text, i, len(chunks), files, out_file, deep), encoding="utf-8")
        plan_chunks.append({"n": i, "task": str(task_file), "output": str(out_file), "files": files})

    plan = {
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "update": update,
        "deep": deep,
        "spec": str(spec),
        "work_files": work_files,
        "corpus_files": corpus_files,
        "deleted_files": deleted,
        "uncached": [it["source_file"] for it in items],
        "detection": {k: detection.get(k) for k in (
            "total_files", "total_words", "needs_graph", "warning", "skipped_sensitive",
            "secret_findings", "scan_root",
        )},
        "chunks": plan_chunks,
    }
    write_json_atomic(state / PLAN_NAME, plan, ensure_ascii=False)

    hits = len(sem_files) - len(uncached)
    print(f"[graphify kiro] documents : {len(sem_files)} au total, {hits} deja en cache, "
          f"{len(items)} a extraire en {len(plan_chunks)} lot(s).")
    if plan_chunks:
        print("[graphify kiro] ETAPE SUIVANTE : pour chaque lot ci-dessous, lancer un sous-agent Kiro "
              "avec la consigne : \"Execute la mission decrite dans <fichier>\".")
        for c in plan_chunks:
            print(f"  lot {c['n']:02d} : {c['task']}  ({len(c['files'])} fichier(s))")
        print("Puis : graphify kiro finalize")
    else:
        print("[graphify kiro] aucun document a faire lire : lancez directement `graphify kiro finalize`.")


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #

def _load_plan() -> dict:
    plan = _load_json(_state_dir() / PLAN_NAME)
    if not isinstance(plan, dict):
        _die("aucune preparation trouvee : lancez d'abord `graphify kiro prepare`.")
    return plan


def cmd_status(argv: list[str]) -> None:
    plan = _load_plan()
    done = [c for c in plan["chunks"] if Path(c["output"]).is_file()]
    print(f"[graphify kiro] {len(done)}/{len(plan['chunks'])} lot(s) ecrits.")
    for c in plan["chunks"]:
        state = "ecrit" if Path(c["output"]).is_file() else "MANQUANT"
        print(f"  lot {c['n']:02d} : {state}")


# --------------------------------------------------------------------------- #
# Validation stricte des lots ecrits par les sous-agents
# --------------------------------------------------------------------------- #

def _strict_filter(fragment: dict, chunk: dict, root: Path) -> tuple[dict, list[str]]:
    """Ne garde que des elements conformes ; renvoie (fragment propre, remarques)."""
    notes: list[str] = []
    allowed: dict[str, str] = {}
    for f in chunk["files"]:
        src = f["source_file"]
        for alias in {src, f["read_path"], _rel(src, root), _rel(f["read_path"], root)}:
            allowed[alias] = src

    def _src(value) -> str | None:
        if not isinstance(value, str):
            return None
        return allowed.get(value) or allowed.get(value.replace("\\", "/"))

    extra = set(fragment) - _TOP_KEYS
    if extra:
        notes.append(f"cles inconnues ignorees : {sorted(extra)[:5]}")

    nodes_out: list[dict] = []
    node_ids: set[str] = set()
    for n in (fragment.get("nodes") or [])[:MAX_NODES_PER_CHUNK]:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        src = _src(n.get("source_file"))
        label = _clean_text(n.get("label"), MAX_LABEL_LEN)
        if not (isinstance(nid, str) and _ID_RE.match(nid)) or not label:
            notes.append("noeud invalide ignore (id/libelle)")
            continue
        if src is None:
            notes.append(f"noeud {nid!r} ignore : source_file hors du lot")
            continue
        rationale = _clean_text(n.get("rationale"), MAX_RATIONALE_LEN)
        if _is_suspicious(label, rationale):
            notes.append(f"noeud {nid!r} ecarte : contenu ressemblant a une instruction ou une commande")
            continue
        clean = {
            "id": nid,
            "label": label,
            "file_type": n.get("file_type") if n.get("file_type") in _FILE_TYPES else "concept",
            "source_file": src,
            "source_location": _clean_text(n.get("source_location"), 64),
        }
        for k in ("source_url", "captured_at", "author", "contributor"):
            v = _clean_text(n.get(k), 256)
            if v and not _is_suspicious(v):
                clean[k] = v
        if rationale:
            clean["rationale"] = rationale
        if set(n) - _NODE_KEYS:
            notes.append(f"noeud {nid!r} : champs inconnus retires")
        nodes_out.append(clean)
        node_ids.add(nid)

    edges_out: list[dict] = []
    for e in (fragment.get("edges") or [])[:MAX_EDGES_PER_CHUNK]:
        if not isinstance(e, dict):
            continue
        s, t, rel = e.get("source"), e.get("target"), e.get("relation")
        if not (isinstance(s, str) and _ID_RE.match(s) and isinstance(t, str) and _ID_RE.match(t)):
            continue
        if not (isinstance(rel, str) and _RELATION_RE.match(rel)):
            notes.append("arete ignoree : relation invalide")
            continue
        src = _src(e.get("source_file"))
        if src is None:
            notes.append("arete ignoree : source_file hors du lot")
            continue
        conf = e.get("confidence") if e.get("confidence") in _CONFIDENCES else "AMBIGUOUS"
        score = e.get("confidence_score")
        score = float(score) if isinstance(score, (int, float)) and 0 <= score <= 1 else (1.0 if conf == "EXTRACTED" else 0.3)
        weight = e.get("weight")
        weight = float(weight) if isinstance(weight, (int, float)) and 0 <= weight <= 100 else 1.0
        edges_out.append({
            "source": s, "target": t, "relation": rel, "confidence": conf,
            "confidence_score": score, "source_file": src,
            "source_location": _clean_text(e.get("source_location"), 64), "weight": weight,
        })

    hyper_out: list[dict] = []
    for h in (fragment.get("hyperedges") or [])[:MAX_HYPEREDGES_PER_CHUNK]:
        if not isinstance(h, dict):
            continue
        hid, label = h.get("id"), _clean_text(h.get("label"), MAX_LABEL_LEN)
        members = [m for m in (h.get("nodes") or []) if isinstance(m, str) and _ID_RE.match(m)][:256]
        src = _src(h.get("source_file"))
        rel = h.get("relation")
        if not (isinstance(hid, str) and _ID_RE.match(hid) and label and len(members) >= 3 and src):
            continue
        if _is_suspicious(label):
            notes.append(f"hyperarete {hid!r} ecartee : contenu suspect")
            continue
        conf = h.get("confidence") if h.get("confidence") in ("EXTRACTED", "INFERRED") else "INFERRED"
        score = h.get("confidence_score")
        hyper_out.append({
            "id": hid, "label": label, "nodes": members,
            "relation": rel if isinstance(rel, str) and _RELATION_RE.match(rel) else "participate_in",
            "confidence": conf,
            "confidence_score": float(score) if isinstance(score, (int, float)) and 0 <= score <= 1 else 0.75,
            "source_file": src,
        })

    coverage: dict[str, int] = {}
    cov = fragment.get("coverage")
    if isinstance(cov, dict):
        for k, v in cov.items():
            src = _src(k)
            if src and isinstance(v, int) and v >= 0:
                coverage[src] = max(coverage.get(src, 0), v)

    return {"nodes": nodes_out, "edges": edges_out, "hyperedges": hyper_out, "coverage": coverage}, notes


# --------------------------------------------------------------------------- #
# finalize
# --------------------------------------------------------------------------- #

def _build_outputs(extraction: dict, detection: dict, root: Path, directed: bool, force: bool,
                   no_viz: bool, labels: dict[int, str] | None = None) -> tuple[object, dict]:
    from graphify.analyze import god_nodes, suggest_questions, surprising_connections
    from graphify.build import build_from_json
    from graphify.cluster import cluster, label_communities_by_hub, score_all
    from graphify.export import to_json
    from graphify.report import generate

    G = build_from_json(extraction, root=str(root), directed=directed)
    if G.number_of_nodes() == 0:
        _die("le graphe est vide (aucun noeud extrait).")
    communities = cluster(G)
    cohesion = score_all(G, communities)
    gods = god_nodes(G)
    surprises = surprising_connections(G, communities)
    reused: set[int] = set()
    if labels is None:
        labels = label_communities_by_hub(G, communities)
        labels, reused = _reuse_previous_names(G, communities, labels)
    questions = suggest_questions(G, communities, labels)
    wrote = to_json(G, communities, str(out_path("graph.json")), force=force, community_labels=labels)
    if not wrote:
        _die("graph.json existant plus gros : reconstruction refusee (relancez avec --force si des "
             "fichiers ont ete supprimes volontairement).")
    tokens = {"input": 0, "output": 0}
    report = generate(G, communities, cohesion, labels, gods, surprises, detection, tokens, str(root),
                      suggested_questions=questions)
    out_path("GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in cohesion.items()},
        "gods": gods,
        "surprises": surprises,
        "labels": {str(k): v for k, v in labels.items()},
        "named": sorted(reused),
        "directed": directed,
    }
    if not no_viz:
        if G.number_of_nodes() > 5000:
            print("[graphify kiro] graphe > 5000 noeuds : export HTML ignore (utilisez `graphify export html`).")
        else:
            from graphify.export import to_html

            to_html(G, communities, str(out_path("graph.html")), community_labels=labels)
    return G, analysis


LABELS_META = ".graphify_labels_meta.json"


def _community_hubs(G, communities: dict[int, list[str]]) -> dict[int, str]:
    return {cid: max(members, key=lambda n: (G.degree(n), str(n))) for cid, members in communities.items() if members}


def _reuse_previous_names(G, communities: dict[int, list[str]], labels: dict[int, str]) -> tuple[dict[int, str], set[int]]:
    """Reprend les noms choisis lors d'une construction precedente quand une
    communaute a garde le meme noeud central (hub)."""
    meta = _load_json(out_path(LABELS_META), {}) or {}
    by_hub = {v.get("hub"): v.get("name") for v in meta.values() if isinstance(v, dict)}
    reused: set[int] = set()
    for cid, hub in _community_hubs(G, communities).items():
        name = by_hub.get(hub)
        if isinstance(name, str) and name:
            labels[cid] = name
            reused.add(cid)
    return labels, reused


def _print_communities(G, analysis: dict) -> None:
    from graphify.security import sanitize_label

    comms = {int(k): v for k, v in analysis["communities"].items()}
    print("[graphify kiro] COMMUNAUTES A NOMMER (2 a 5 mots chacune). Ecrivez un fichier JSON "
          f"{{\"<id>\": \"<nom>\"}} dans {_state_dir() / 'labels.json'} puis lancez "
          "`graphify kiro labels " + str(_state_dir() / "labels.json") + "`.")
    for cid in sorted(comms, key=lambda c: -len(comms[c]))[:200]:
        members = comms[cid]
        ranked = sorted(members, key=lambda n: -G.degree(n))[:8]
        names = [sanitize_label(str(G.nodes[n].get("label", n)))[:60] for n in ranked]
        tag = f" [deja nomme : {analysis['labels'].get(str(cid))}]" if cid in set(analysis.get("named", [])) else ""
        print(f"  {cid}: ({len(members)} noeuds){tag} " + " | ".join(names))


def cmd_finalize(argv: list[str]) -> None:
    from graphify.cache import save_semantic_cache
    from graphify.cli import _stamped_manifest_files
    from graphify.detect import save_manifest
    from graphify.diagnostics import diagnose_extraction
    from graphify.llm import _stamp_semantic_origin
    from graphify.semantic_cleanup import load_validated_semantic_fragment

    directed = "--directed" in argv
    no_viz = "--no-viz" in argv
    force = "--force" in argv
    plan = _load_plan()
    state = _state_dir()
    root = Path(plan["root"])
    mode = "deep" if plan.get("deep") else None

    # 1. Lots des sous-agents : validation stricte
    new = {"nodes": [], "edges": [], "hyperedges": []}
    partial: set[str] = set()
    missing_sources: set[str] = set()
    rejected = 0
    for c in plan["chunks"]:
        out_file = Path(c["output"])
        if not out_file.is_file():
            print(f"[graphify kiro] lot {c['n']:02d} MANQUANT : ses fichiers seront retentes au prochain --update.")
            missing_sources.update(f["source_file"] for f in c["files"])
            continue
        frag, errors = load_validated_semantic_fragment(out_file)
        if errors or frag is None:
            rejected += 1
            print(f"[graphify kiro] lot {c['n']:02d} REJETE : {errors[:3]}")
            missing_sources.update(f["source_file"] for f in c["files"])
            continue
        clean, notes = _strict_filter(frag, c, root)
        for note in sorted(set(notes))[:8]:
            print(f"[graphify kiro] lot {c['n']:02d} : {note}")
        new["nodes"] += clean["nodes"]
        new["edges"] += clean["edges"]
        new["hyperedges"] += clean["hyperedges"]
        for f in c["files"]:
            if f["kind"] == "image" or not f["lines"]:
                continue
            got = clean["coverage"].get(f["source_file"])
            if got is None or got < f["lines"]:
                partial.add(f["source_file"])
                print(f"[graphify kiro] lecture partielle : {_rel(f['source_file'], root)} "
                      f"({got if got is not None else '?'} / {f['lines']} lignes) - sera retente.")

    # 2. Cache semantique (seulement pour les fichiers effectivement traites)
    uncached_ok = [s for s in plan["uncached"] if s not in missing_sources]
    if uncached_ok:
        saved = save_semantic_cache(new["nodes"], new["edges"], new["hyperedges"], root=root,
                                    allowed_source_files=uncached_ok, mode=mode,
                                    prompt_file=Path(plan["spec"]), partial_source_files=sorted(partial))
        print(f"[graphify kiro] cache : {saved} fichier(s) enregistres.")

    # 3. Cache + nouveaux resultats
    cached = _load_json(state / "cached.json", {"nodes": [], "edges": [], "hyperedges": []})
    seen: set[str] = set()
    sem_nodes = []
    for n in cached.get("nodes", []) + new["nodes"]:
        if n.get("id") not in seen:
            seen.add(n.get("id"))
            sem_nodes.append(n)
    semantic = _stamp_semantic_origin({
        "nodes": sem_nodes,
        "edges": cached.get("edges", []) + new["edges"],
        "hyperedges": cached.get("hyperedges", []) + new["hyperedges"],
    })

    # 4. Fusion code (AST) + documents
    ast = _load_json(state / "ast.json", {"nodes": [], "edges": []})
    ids = {n["id"] for n in ast.get("nodes", [])}
    merged_nodes = list(ast.get("nodes", [])) + [n for n in semantic["nodes"] if n["id"] not in ids]
    extraction = {
        "nodes": merged_nodes,
        "edges": ast.get("edges", []) + semantic["edges"],
        "hyperedges": semantic.get("hyperedges", []),
        "input_tokens": 0,
        "output_tokens": 0,
    }

    # 5. Mise a jour incrementale : fusion avec le graphe existant
    graph_json = out_path("graph.json")
    if plan.get("update") and graph_json.exists():
        from graphify.build import build_merge

        G0 = build_merge([extraction], graph_path=str(graph_json),
                         prune_sources=list(plan.get("deleted_files") or []) or None,
                         root=str(root), directed=directed)
        extraction = {
            "nodes": [{"id": n, **d} for n, d in G0.nodes(data=True)],
            "edges": [
                {**{k: v for k, v in d.items() if k not in ("_src", "_tgt", "source", "target")},
                 "source": d.get("_src", u), "target": d.get("_tgt", v)}
                for u, v, d in G0.edges(data=True)
            ],
            "hyperedges": list(G0.graph.get("hyperedges", [])),
            "input_tokens": 0,
            "output_tokens": 0,
        }
        print(f"[graphify kiro] mise a jour fusionnee : {G0.number_of_nodes()} noeuds.")
    write_json_atomic(state / "extract.json", extraction, ensure_ascii=False)

    # 6. Sante du graphe (lecture seule)
    try:
        summary = diagnose_extraction(extraction, directed=directed, root=str(root))
        flags = [f"{summary[k]} {k}" for k in (
            "dangling_endpoint_edges", "missing_endpoint_edges", "self_loop_edges",
        ) if summary.get(k, 0)]
        print("[graphify kiro] sante du graphe : " + ("; ".join(flags) if flags else "OK"))
    except Exception as exc:  # diagnostic seulement, jamais bloquant
        print(f"[graphify kiro] diagnostic indisponible : {exc}")

    # 7. Graphe, communautes, rapport, HTML
    detection = dict(plan.get("detection") or {})
    G, analysis = _build_outputs(extraction, detection, root, directed, force, no_viz)
    write_json_atomic(state / "analysis.json", analysis, ensure_ascii=False)

    # 8. Manifeste (pour --update) : seuls les fichiers reellement extraits sont marques
    corpus = plan.get("corpus_files") or {}
    manifest_files = _stamped_manifest_files(corpus, semantic, root, partial_source_files=partial)
    dispatched = {f for t, fl in (plan.get("work_files") or {}).items() if t in _SEM_TYPES for f in fl}
    stamped = {f for fl in manifest_files.values() for f in fl}
    cleared = dispatched - stamped
    scan = {f for fl in corpus.values() for f in fl}
    save_manifest(manifest_files, root=root, scan_corpus=scan, clear_semantic=cleared or None)

    for c in plan["chunks"]:
        Path(c["output"]).unlink(missing_ok=True)
    print(f"[graphify kiro] graphe : {G.number_of_nodes()} noeuds, {G.number_of_edges()} aretes, "
          f"{len(analysis['communities'])} communautes -> {out_path()}")
    if rejected:
        print(f"[graphify kiro] ATTENTION : {rejected} lot(s) rejete(s) ; relancez /graphify --update.")
    _print_communities(G, analysis)


# --------------------------------------------------------------------------- #
# labels
# --------------------------------------------------------------------------- #

def cmd_labels(argv: list[str]) -> None:
    files = [a for a in argv if not a.startswith("--")]
    if not files:
        _die("usage : graphify kiro labels <fichier.json>")
    data = _load_json(Path(files[0]))
    if not isinstance(data, dict):
        _die("le fichier de noms doit etre un objet JSON {\"<id>\": \"<nom>\"}.")
    state = _state_dir()
    analysis = _load_json(state / "analysis.json")
    extraction = _load_json(state / "extract.json")
    plan = _load_plan()
    if not isinstance(analysis, dict) or not isinstance(extraction, dict):
        _die("aucune construction recente : lancez `graphify kiro finalize` d'abord.")
    comm_ids = {int(k) for k in analysis["communities"]}
    labels = {int(k): v for k, v in analysis.get("labels", {}).items()}
    applied, refused = 0, []
    named = set(analysis.get("named", []))
    for k, v in data.items():
        try:
            cid = int(k)
        except (TypeError, ValueError):
            refused.append(str(k)[:20])
            continue
        name = _clean_text(v, MAX_COMMUNITY_NAME_LEN)
        if cid not in comm_ids or not name or _is_suspicious(name):
            refused.append(str(k)[:20])
            continue
        labels[cid] = name
        named.add(cid)
        applied += 1
    root = Path(plan["root"])
    directed = bool(analysis.get("directed"))
    from graphify.analyze import suggest_questions
    from graphify.build import build_from_json
    from graphify.export import to_html, to_json
    from graphify.report import generate

    G = build_from_json(extraction, root=str(root), directed=directed)
    communities = {int(k): v for k, v in analysis["communities"].items()}
    cohesion = {int(k): v for k, v in analysis["cohesion"].items()}
    questions = suggest_questions(G, communities, labels)
    report = generate(G, communities, cohesion, labels, analysis["gods"], analysis["surprises"],
                      dict(plan.get("detection") or {}), {"input": 0, "output": 0}, str(root),
                      suggested_questions=questions)
    out_path("GRAPH_REPORT.md").write_text(report, encoding="utf-8")
    out_path(".graphify_labels.json").write_text(
        json.dumps({str(k): v for k, v in labels.items()}, ensure_ascii=False), encoding="utf-8")
    if not to_json(G, communities, str(out_path("graph.json")), community_labels=labels):
        _die("graph.json n'a pas pu etre reecrit (garde-fou de reduction).")
    if out_path("graph.html").exists() and G.number_of_nodes() <= 5000:
        to_html(G, communities, str(out_path("graph.html")), community_labels=labels)
    analysis["labels"] = {str(k): v for k, v in labels.items()}
    write_json_atomic(state / "analysis.json", analysis, ensure_ascii=False)
    hubs = _community_hubs(G, communities)
    write_json_atomic(out_path(LABELS_META), {
        str(cid): {"name": labels[cid], "hub": hubs.get(cid)} for cid in sorted(named) if cid in hubs
    }, ensure_ascii=False)
    analysis["named"] = sorted(named)
    write_json_atomic(state / "analysis.json", analysis, ensure_ascii=False)
    print(f"[graphify kiro] {applied} nom(s) applique(s)" + (f", {len(refused)} refuse(s)" if refused else "") + ".")
    print(f"[graphify kiro] rapport : {out_path('GRAPH_REPORT.md')}")


# --------------------------------------------------------------------------- #
# verify : auto-controle apres installation
# --------------------------------------------------------------------------- #

def cmd_verify(argv: list[str]) -> None:
    """Verifie que cette installation de graphify ne peut rien envoyer dehors."""
    import importlib
    import importlib.util
    import socket
    import subprocess

    results: list[tuple[bool, str]] = []

    def check(ok: bool, label: str) -> None:
        results.append((bool(ok), label))

    from graphify import _egress_guard
    check(_egress_guard.installed(), "verrou anti-fuite actif dans le processus graphify")

    def _blocked(fn) -> bool:
        try:
            fn()
        except _egress_guard.EgressBlocked:
            return True
        except Exception:
            return False
        return False

    check(_blocked(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM)), "creation de socket TCP bloquee")
    check(_blocked(lambda: socket.getaddrinfo("example.com", 443)), "resolution DNS bloquee")
    check(_blocked(lambda: subprocess.run(["curl", "--version"], capture_output=True)), "lancement de curl bloque")
    check(_blocked(lambda: subprocess.run(["git", "push"], capture_output=True)), "git push bloque")
    check(_blocked(lambda: __import__("urllib.request").request.urlopen("https://example.com")), "urllib bloque")

    from graphify import llm
    check(not llm.BACKENDS and llm.detect_backend() is None, "aucun backend IA dans graphify")
    for mod in ("graphify.prs", "graphify.transcribe", "graphify.pg_introspect", "graphify.global_graph"):
        check(importlib.util.find_spec(mod) is None, f"module retire : {mod}")
    try:
        import graphify.serve as _serve
        check(not hasattr(_serve, "_build_server"), "serveur MCP retire")
    except Exception:
        check(False, "serveur MCP retire")

    from graphify import _vendor
    for name in ("vis-network", "d3", "mermaid"):
        try:
            _vendor._vendor_source(name)
            check(True, f"bibliotheque HTML embarquee intacte : {name}")
        except Exception as exc:
            check(False, f"bibliotheque HTML embarquee intacte : {name} ({exc})")

    # Informatif : bibliotheques reseau presentes dans l'environnement Python
    # (non utilisees par graphify-local ; un environnement dedie est conseille).
    extra = [m for m in ("openai", "anthropic", "requests", "httpx", "boto3", "mcp", "yt_dlp", "faster_whisper")
             if importlib.util.find_spec(m) is not None]

    failed = [label for ok, label in results if not ok]
    for ok, label in results:
        print(f"  [{'OK' if ok else 'ECHEC'}] {label}")
    if extra:
        print(f"  [INFO] bibliotheques reseau presentes dans cet environnement (non utilisees par graphify) : {', '.join(extra)}")
    from graphify.__main__ import __version__
    print(f"[graphify kiro] graphify {__version__} : "
          + ("verification reussie." if not failed else f"{len(failed)} controle(s) en echec."))
    if failed:
        sys.exit(1)


# --------------------------------------------------------------------------- #

_COMMANDS = {"prepare": cmd_prepare, "status": cmd_status, "finalize": cmd_finalize, "labels": cmd_labels, "verify": cmd_verify}


def is_pipeline_command(argv: list[str]) -> bool:
    return len(argv) >= 3 and argv[1] == "kiro" and argv[2] in _COMMANDS


def main(argv: list[str]) -> None:
    _COMMANDS[argv[2]](argv[3:])
