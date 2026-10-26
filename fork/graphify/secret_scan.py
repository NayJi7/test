"""graphify-local : detection de secrets dans le CONTENU des documents.

graphify d'origine n'excluait les fichiers sensibles que d'apres leur NOM
(.env, *.pem, id_rsa, ...). Un mot de passe ecrit dans un compte rendu .md, une
cle d'API collee dans un PDF ou une chaine de connexion dans un tableur etait
donc transmis tel quel a l'extraction semantique.

Ce module lit le texte des documents (docs, PDF, conversions Office) avant
toute extraction. Un fichier qui contient un secret probable est retire du
corpus (il ne sera jamais propose aux sous-agents de l'assistant) et signale dans
``skipped_sensitive`` et ``secret_findings`` (chemin, regle, numero de ligne ;
jamais la valeur du secret).

Faux positif ? Un humain peut approuver un fichier precis, dans sa version
exacte, en ajoutant une ligne ``<sha256>  <chemin relatif>`` au fichier
``.graphify-secrets-allow`` a la racine du corpus. Toute modification du
fichier invalide l'approbation (l'empreinte ne correspond plus).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ALLOWLIST_NAME = ".graphify-secrets-allow"
_MAX_SCAN_BYTES = 20 * 1024 * 1024

_PLACEHOLDER_RE = re.compile(
    r"^(?:x+|\*+|\.+|<[^>]*>|\{[^}]*\}|\$\{?[A-Za-z_][A-Za-z0-9_]*\}?|"
    r"changeme|change_me|example|exemple|password|motdepasse|secret|your[_-]?\w*|"
    r"todo|tbd|none|null|redacted|\[redacted\]|xxx+|placeholder)$",
    re.I,
)

# (nom de la regle, motif). Les motifs "forme" reprennent et etendent ceux de
# security._SECRET_SHAPE_RE ; les motifs "affectation" ciblent les valeurs
# ecrites en clair a cote d'un mot-cle (password=, token:, mot de passe : ...).
_SHAPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("cle-privee", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("aws-secret-key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{22,}")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("stripe-key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}")),
    ("llm-api-key", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("azure-storage-key", re.compile(r"(?i)AccountKey=[A-Za-z0-9+/=]{40,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("bearer-token", re.compile(r"(?<=\bBearer )[A-Za-z0-9._~+/=-]{16,}")),
    ("url-avec-identifiants", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]{3,}@")),
]
_ASSIGN_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|passphrase|secret|client[_-]?secret|api[_-]?key|"
    r"apikey|access[_-]?token|auth[_-]?token|private[_-]?key|token|"
    r"mot[ _-]de[ _-]passe|mdp|identifiant[ _-]secret)\b"
    r"[\"']?\s*[:=]\s*[\"']?([^\s\"'<>,;]{8,})"
)


def _find_secrets(text: str) -> list[tuple[str, int]]:
    """Liste des (regle, numero de ligne) pour chaque secret probable."""
    hits: list[tuple[str, int]] = []

    def _line(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    for name, rx in _SHAPE_RULES:
        for m in rx.finditer(text):
            hits.append((name, _line(m.start())))
    for m in _ASSIGN_RE.finditer(text):
        value = m.group(2)
        if _PLACEHOLDER_RE.match(value):
            continue
        # Une valeur d'au moins 8 caracteres, avec chiffres ou symboles, a cote
        # d'un mot-cle : secret probable. Un simple mot (lettres seules) est ignore.
        if not re.search(r"[0-9!@#$%^&*()_+\-=\[\]{}|/\\.?~]", value):
            continue
        hits.append(("affectation-" + m.group(1).lower().replace(" ", "-"), _line(m.start())))
    hits.sort(key=lambda h: (h[1], h[0]))
    return hits


def _file_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from graphify.detect import extract_pdf_text

            return extract_pdf_text(path) or ""
        except Exception:
            return ""
    try:
        with open(path, "rb") as fh:
            data = fh.read(_MAX_SCAN_BYTES)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_allowlist(root: Path) -> set[tuple[str, str]]:
    """Paires (sha256, chemin relatif POSIX) approuvees par un humain."""
    allow: set[tuple[str, str]] = set()
    path = root / ALLOWLIST_NAME
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return allow
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            allow.add((parts[0], parts[1].strip().replace("\\", "/")))
    return allow


def scan_file(path: Path, root: Path, allow: set[tuple[str, str]] | None = None) -> list[dict]:
    """Constats de secrets pour `path` (liste vide = rien trouve ou approuve)."""
    hits = _find_secrets(_file_text(path))
    if not hits:
        return []
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.as_posix()
    if allow:
        try:
            if (_sha256(path), rel) in allow:
                return []
        except OSError:
            pass
    return [{"file": rel, "rule": rule, "line": line} for rule, line in hits]
