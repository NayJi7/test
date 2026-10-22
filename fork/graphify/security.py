# Security helpers - URL validation, safe fetch, path guards, label sanitisation
from __future__ import annotations

import html
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any


from graphify.paths import GRAPHIFY_OUT, GRAPHIFY_OUT_NAME

# graphify-local: la recuperation d'URL (safe_fetch, validate_url, garde SSRF)
# est supprimee avec la commande `add`. Ce module ne fait plus aucun acces reseau.

# Graph-load memory-bomb cap: reject .json files larger than this before
# JSON-parsing them into a dict. Without this, a multi-gigabyte (or
# specifically crafted) graph.json can exhaust process memory during
# json.loads + node_link_graph rehydration.
# Default fallback cap. Kept as a module-level constant so the value is
# discoverable and so existing callers/tests that reference it directly keep
# working; the effective cap is resolved at call time by
# ``_max_graph_file_bytes`` (which lets ``GRAPHIFY_MAX_GRAPH_BYTES`` override it).
_MAX_GRAPH_FILE_BYTES = 512 * 1024 * 1024   # 512 MiB


def _max_graph_file_bytes() -> int:
    """Return the graph.json size cap in bytes.

    Honors the ``GRAPHIFY_MAX_GRAPH_BYTES`` environment variable so users with
    large codebases can raise the limit without editing source. The value may
    be plain bytes (``671088640``) or carry an ``MB`` / ``GB`` suffix
    (``640MB``, ``2GB`` — case-insensitive, binary multipliers: ``MB`` is
    1024*1024 and ``GB`` is 1024*1024*1024, i.e. MiB / GiB).
    Falls back to ``_MAX_GRAPH_FILE_BYTES`` (512 MiB) when the env var is unset,
    blank, or unparseable.

    Read fresh on every call so the env var can be set before import and still
    take effect.
    """
    raw = os.environ.get("GRAPHIFY_MAX_GRAPH_BYTES", "").strip()
    if not raw:
        return _MAX_GRAPH_FILE_BYTES
    text = raw.upper()
    multiplier = 1
    if text.endswith("GB"):
        multiplier = 1024 * 1024 * 1024
        text = text[:-2].strip()
    elif text.endswith("MB"):
        multiplier = 1024 * 1024
        text = text[:-2].strip()
    try:
        value = int(text)
    except ValueError:
        return _MAX_GRAPH_FILE_BYTES
    if value <= 0:
        return _MAX_GRAPH_FILE_BYTES
    return value * multiplier

def validate_graph_path(path: str | Path, base: Path | None = None) -> Path:
    """Resolve *path* and verify it stays inside *base*.

    *base* defaults to the `graphify-out` directory relative to CWD.
    Also requires the base directory to exist, so a caller cannot
    trick graphify into reading files before any graph has been built.

    Raises:
        ValueError  - path escapes base, or base does not exist
        FileNotFoundError - resolved path does not exist
    """
    if base is None:
        resolved_hint = Path(path).resolve()
        for candidate in [resolved_hint, *resolved_hint.parents]:
            if candidate.name == GRAPHIFY_OUT_NAME:
                base = candidate
                break
        if base is None:
            base = Path(GRAPHIFY_OUT).resolve()

    base = base.resolve()
    if not base.exists():
        raise ValueError(
            f"Graph base directory does not exist: {base}. "
            "Run /graphify first to build the graph."
        )

    resolved = Path(path).resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError(
            f"Path {path!r} escapes the allowed directory {base}. "
            "Only paths inside graphify-out/ are permitted."
        )

    if not resolved.exists():
        raise FileNotFoundError(f"Graph file not found: {resolved}")

    return resolved


def check_graph_file_size_cap(path: Path) -> None:
    """Reject *path* if its size exceeds the configured graph-file cap.

    Protects callers from memory bombs by failing fast before a multi-GiB
    graph.json is read into memory and JSON-parsed. Silently returns when
    ``path.stat()`` cannot be read — the caller's own existence/path check
    is expected to surface a clearer error in that case.

    The cap is resolved on every call via :func:`_max_graph_file_bytes`, so the
    ``GRAPHIFY_MAX_GRAPH_BYTES`` env var can be set before import and still
    apply.

    Raises:
        ValueError - file size exceeds the cap. The message includes the
        observed size, the cap, and how to raise the limit.
    """
    cap = _max_graph_file_bytes()
    try:
        size = path.stat().st_size
    except OSError:
        return
    if size > cap:
        raise ValueError(
            f"graph file {path} is {size:_d} bytes, exceeds {cap:_d}-byte cap\n"
            f"(set GRAPHIFY_MAX_GRAPH_BYTES=<bytes> or "
            f"GRAPHIFY_MAX_GRAPH_BYTES=<N>GB to raise the limit)"
        )


# ---------------------------------------------------------------------------
# Label sanitisation (mirrors code-review-graph's _sanitize_name pattern)
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")
_MAX_LABEL_LEN = 256


# Credential shapes redacted from free text that is persisted into the graph
# (rationale/comment labels). Shape-based only, so it is risk reduction rather
# than a guarantee: vendor-prefixed tokens and PEM private-key headers.
_SECRET_SHAPE_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY(?: BLOCK)?-----"
    r"|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"
    r"|\bgh[pousr]_[A-Za-z0-9]{36,}"
    r"|\bgithub_pat_[A-Za-z0-9_]{22,}"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}"
    r"|\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}"
    r"|\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"
    r"|\bAIza[0-9A-Za-z_-]{35}\b"
    r"|\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
    r"|(?<=\bBearer )[A-Za-z0-9._~+/=-]{16,}"
    r"|(?<=://)[^\s/:@]+:[^\s/@]+(?=@)"
)

REDACTED_MARKER = "[redacted]"


def redact_secrets(text: str | None) -> str:
    """Replace credential-shaped substrings in *text* with ``[redacted]``.

    Applied to free text copied out of source files (docstrings and ``# WHY:``
    style comments) before it becomes a node label, so a token pasted into a
    comment does not land in graph.json / graph.html / GRAPH_REPORT.md.
    """
    if not text:
        return "" if text is None else text
    return _SECRET_SHAPE_RE.sub(REDACTED_MARKER, str(text))


def sanitize_label(text: str | None) -> str:
    """Strip control characters and cap length.

    Safe for embedding in JSON data (inside <script> tags) and plain text.
    For direct HTML injection, wrap the result with html.escape().
    """
    if text is None:
        return ""
    text = _CONTROL_CHAR_RE.sub("", str(text))
    if len(text) > _MAX_LABEL_LEN:
        text = text[:_MAX_LABEL_LEN]
    return text


# ---------------------------------------------------------------------------
# Metadata sanitisation (recursive, bounded, HTML-safe)
# ---------------------------------------------------------------------------

_METADATA_MAX_VALUE_LEN = 512
_METADATA_MAX_LIST_ITEMS = 50
_METADATA_MAX_ATTRIBUTES = 100


def _sanitize_metadata_string(value: object) -> str:
    """Return a control-character-free, HTML-escaped, bounded string."""
    text = _CONTROL_CHAR_RE.sub("", str(value))
    text = html.escape(text, quote=True)
    if len(text) > _METADATA_MAX_VALUE_LEN:
        text = text[:_METADATA_MAX_VALUE_LEN]
    return text  # html is imported at module level (line 5)


def _sanitize_metadata_value(value: object) -> object:
    """Sanitize a metadata value while preserving simple JSON-compatible types."""
    if isinstance(value, bool):
        # bool is a subclass of int — must be checked first to avoid coercion.
        return value
    if isinstance(value, str):
        return _sanitize_metadata_string(value)
    if isinstance(value, dict):
        return sanitize_metadata(value)
    if isinstance(value, (list, tuple)):
        return [_sanitize_metadata_value(item) for item in value[:_METADATA_MAX_LIST_ITEMS]]
    if isinstance(value, (int, float)) or value is None:
        return value
    return _sanitize_metadata_string(value)


def sanitize_metadata(metadata: Mapping[str, Any] | None) -> dict[str, object]:
    """Sanitize metadata keys and values before graph export.

    Metadata is less constrained than node labels: it can contain nested
    dicts, lists, source snippets, external index symbols, and docstring
    text. This helper keeps the data JSON-compatible, strips control
    characters, escapes HTML-sensitive characters in strings, caps long
    strings/lists, and drops entries whose key becomes empty after
    sanitization.
    """
    if metadata is None:
        return {}

    result: dict[str, object] = {}
    for key, value in metadata.items():
        clean_key = _sanitize_metadata_string(key)
        if not clean_key:
            continue
        result[clean_key] = _sanitize_metadata_value(value)
    return result
