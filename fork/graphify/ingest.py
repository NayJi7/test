# local Q&A memory (save-result); URL ingestion removed in graphify-local
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

# graphify-local: `ingest(url)` (commande `graphify add`) est supprime : il
# telechargeait des pages web, tweets, articles arXiv, PDF et videos. Seul
# l'enregistrement local des questions/reponses (save-result) est conserve.


def _yaml_str(s: str) -> str:
    """Escape a string for embedding in a YAML double-quoted scalar.

    Handles every YAML 1.1/1.2 line-break and control character that could
    let a hostile value (e.g. a fetched page title) break out of the quoted
    scalar and inject sibling YAML keys (F-009 / F-019). The previous
    implementation missed `\\t`, `\\0`, the unicode line-separator U+2028 and
    paragraph-separator U+2029 — all of which YAML treats as line breaks.

    We intentionally do not depend on PyYAML (not in pyproject deps) and
    instead emit safely-escaped double-quoted scalars by hand: the YAML
    double-quoted form recognises `\\\\`, `\\"`, `\\n`, `\\r`, `\\t`, `\\0`,
    `\\L` (U+2028), `\\P` (U+2029), and `\\xNN`/`\\uNNNN` numeric escapes.
    """
    if s is None:
        return ""
    out: list[str] = []
    for ch in str(s):
        cp = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\0":
            out.append("\\0")
        elif cp == 0x2028:
            out.append("\\L")
        elif cp == 0x2029:
            out.append("\\P")
        elif cp < 0x20 or cp == 0x7F:
            out.append(f"\\x{cp:02x}")
        else:
            out.append(ch)
    return "".join(out)


OUTCOMES = ("useful", "dead_end", "corrected")


def save_query_result(
    question: str,
    answer: str,
    memory_dir: Path,
    query_type: str = "query",
    source_nodes: list[str] | None = None,
    outcome: str | None = None,
    correction: str | None = None,
) -> Path:
    """Save a Q&A result as markdown so it gets extracted into the graph on next --update.

    Files are stored in memory_dir (typically graphify-out/memory/) with YAML frontmatter
    that graphify's extractor reads as node metadata. This closes the feedback loop:
    the system grows smarter from both what you add AND what you ask.

    ``outcome`` (one of :data:`OUTCOMES`) and ``correction`` are optional work-memory
    signals: they are written both to the frontmatter (so `graphify reflect` can
    aggregate them deterministically) and to an ``## Outcome`` body section (so the
    signal round-trips into the graph on the next semantic re-extraction).
    """
    if outcome is not None and outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")

    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    slug = re.sub(r"[^\w]", "_", question.lower())[:50].strip("_")
    # A second-granularity stamp plus a 50-char slug is not unique: two saves in
    # the same second whose questions share a prefix resolve to one path, and the
    # later write_text silently replaces the earlier one (#3301). The short uuid
    # makes every save its own file; the query_ prefix and .md suffix are kept.
    filename = f"query_{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{slug}.md"

    frontmatter_lines = [
        "---",
        f'type: "{query_type}"',
        f'date: "{now.isoformat()}"',
        f'question: "{_yaml_str(question)}"',
        'contributor: "graphify"',
    ]
    if outcome:
        frontmatter_lines.append(f'outcome: "{_yaml_str(outcome)}"')
    if correction:
        frontmatter_lines.append(f'correction: "{_yaml_str(correction)}"')
    if source_nodes:
        nodes_str = ", ".join(f'"{_yaml_str(n)}"' for n in source_nodes[:10])
        frontmatter_lines.append(f"source_nodes: [{nodes_str}]")
    frontmatter_lines.append("---")

    body_lines = [
        "",
        f"# Q: {question}",
        "",
        "## Answer",
        "",
        answer,
    ]
    if outcome or correction:
        body_lines += ["", "## Outcome", ""]
        if outcome:
            body_lines.append(f"- Signal: {outcome}")
        if correction:
            body_lines.append(f"- Correction: {correction}")
    if source_nodes:
        body_lines += ["", "## Source Nodes", ""]
        body_lines += [f"- {n}" for n in source_nodes]

    content = "\n".join(frontmatter_lines + body_lines)
    out_path = memory_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path

