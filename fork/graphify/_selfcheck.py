"""graphify-local : auto-controle de l'installation (`graphify verify`).

Verifie, dans un processus graphify, que le verrou anti-fuite est actif
(sockets reseau, DNS, urllib et programmes externes bloques), qu'aucun
backend d'IA n'existe, que les modules reseau sont absents et que les
bibliotheques HTML embarquees sont intactes. Code de sortie 1 si un controle
echoue.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> None:
    """Verifie que cette installation de graphify ne peut rien envoyer dehors."""
    import importlib
    import importlib.util
    import socket
    import subprocess

    results: list[tuple[bool, str]] = []

    def check(ok: bool, label: str) -> None:
        results.append((bool(ok), label))

    from graphify import _egress_guard
    check(_egress_guard.installed(), "anti-leak guard active in the graphify process")

    def _blocked(fn) -> bool:
        try:
            fn()
        except _egress_guard.EgressBlocked:
            return True
        except Exception:
            return False
        return False

    check(_blocked(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM)), "TCP socket creation blocked")
    check(_blocked(lambda: socket.getaddrinfo("example.com", 443)), "DNS resolution blocked")
    check(_blocked(lambda: subprocess.run(["curl", "--version"], capture_output=True)), "launching curl blocked")
    check(_blocked(lambda: subprocess.run(["git", "push"], capture_output=True)), "git push blocked")
    check(_blocked(lambda: __import__("urllib.request").request.urlopen("https://example.com")), "urllib blocked")

    from graphify import llm
    check(not llm.BACKENDS and llm.detect_backend() is None, "no AI backend in graphify")
    for mod in ("graphify.prs", "graphify.transcribe", "graphify.pg_introspect", "graphify.global_graph"):
        check(importlib.util.find_spec(mod) is None, f"module removed: {mod}")
    try:
        import graphify.serve as _serve
        check(not hasattr(_serve, "_build_server"), "MCP server removed")
    except Exception:
        check(False, "MCP server removed")

    from graphify import _vendor
    for name in ("vis-network", "d3", "mermaid"):
        try:
            _vendor._vendor_source(name)
            check(True, f"embedded HTML library intact: {name}")
        except Exception as exc:
            check(False, f"embedded HTML library intact: {name} ({exc})")

    # Informatif : bibliotheques reseau presentes dans l'environnement Python
    # (non utilisees par graphify-local ; un environnement dedie est conseille).
    extra = [m for m in ("openai", "anthropic", "requests", "httpx", "boto3", "mcp", "yt_dlp", "faster_whisper")
             if importlib.util.find_spec(m) is not None]

    failed = [label for ok, label in results if not ok]
    for ok, label in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {label}")
    if extra:
        print(f"  [INFO] network libraries present in this environment (not used by graphify): {', '.join(extra)}")
    from graphify.__main__ import __version__
    print(f"[graphify verify] graphify {__version__}: "
          + ("verification passed." if not failed else f"{len(failed)} check(s) failed."))
    if failed:
        sys.exit(1)
