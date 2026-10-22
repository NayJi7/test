"""graphify-local : verrou anti-fuite installe dans le processus.

Ce module est importe en tout premier par ``graphify/__init__.py``. Il installe
un *audit hook* Python (PEP 578, ``sys.addaudithook``). Une fois installe, un
audit hook ne peut plus etre retire par le code Python du meme processus : il
s'applique a tout le code qui s'execute ensuite (graphify, ses dependances,
et tout code qu'un agent tenterait de faire executer via graphify).

Ce qui est refuse (exception ``EgressBlocked``, sous-classe de PermissionError) :

* la creation de toute socket qui n'est pas une socket Unix locale (AF_UNIX) :
  donc aucun TCP/UDP, ni vers Internet, ni vers le reseau interne, ni vers
  127.0.0.1 (un proxy local pourrait relayer vers l'exterieur) ;
* toute connexion, liaison ou emission sur une socket non Unix ;
* toute resolution DNS (le DNS peut servir a exfiltrer des donnees) ;
* l'ouverture d'URL via urllib et le lancement d'un navigateur ;
* le lancement de tout programme externe, sauf une liste blanche minimale :
    - ``git`` limite aux sous-commandes locales ``ls-files``, ``config``,
      ``rev-parse`` (pas de fetch/clone/push) ;
    - ``cpp`` (preprocesseur C, utilise sans acces fichier pour le Fortran) ;
    - l'interpreteur Python courant, uniquement pour relancer graphify
      (``-m graphify``), le code de reconstruction des hooks graphify
      (``-c "from graphify..."``) ou les processus de travail de
      ``multiprocessing``.

Il n'existe volontairement AUCUNE variable d'environnement pour desactiver ce
verrou : un agent detourne pourrait sinon la positionner.
"""
from __future__ import annotations

import os
import re
import sys
import threading

__all__ = ["EgressBlocked", "install", "installed"]


class EgressBlocked(PermissionError):
    """Action reseau ou lancement de programme refuse par graphify-local."""


_INSTALLED = False
_LOCK = threading.Lock()
_TLS = threading.local()

_GIT_ALLOWED_SUBCOMMANDS = frozenset({"ls-files", "config", "rev-parse"})
_DNS_EVENTS = frozenset({
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.gethostbyname_ex",
    "socket.gethostbyaddr",
    "socket.getnameinfo",
})
_SOCKET_USE_EVENTS = frozenset({
    "socket.connect",
    "socket.bind",
    "socket.sendto",
    "socket.sendmsg",
})
_ALWAYS_BLOCKED_EVENTS = frozenset({
    "urllib.Request",
    "webbrowser.open",
    "os.system",
    "os.startfile",
    "pty.spawn",
})


def installed() -> bool:
    return _INSTALLED


def _deny(what: str) -> None:
    raise EgressBlocked(
        f"graphify: action bloquee par le verrou anti-fuite : {what}"
    )


def _unix_family() -> int | None:
    import socket

    return getattr(socket, "AF_UNIX", None)


def _exe_name(path: object) -> str:
    name = os.path.basename(os.fsdecode(path) if isinstance(path, (bytes, os.PathLike)) else str(path))
    name = name.lower()
    for ext in (".exe", ".cmd", ".bat"):
        if name.endswith(ext):
            name = name[: -len(ext)]
    return name


def _is_current_python(path: object) -> bool:
    try:
        target = os.path.realpath(os.fsdecode(path) if isinstance(path, (bytes, os.PathLike)) else str(path))
    except (TypeError, ValueError):
        return False
    candidates = {sys.executable, getattr(sys, "_base_executable", "") or ""}
    for cand in candidates:
        if cand and os.path.realpath(cand) == target:
            return True
    return False


_GRAPHIFY_CODE_RE = re.compile(
    r"^\s*(from graphify(\.[A-Za-z_][\w.]*)? import |import graphify(\.[\w.]+)?\s*($|[;\n,]))"
)
# Lignes de commande exactes generees par la bibliotheque standard (3.10-3.14).
_MP_CODE_RES = (
    re.compile(r"^from multiprocessing\.spawn import spawn_main; spawn_main\([\w=, ']*\)$"),
    re.compile(r"^from multiprocessing\.resource_tracker import main;main\(\d+\)$"),
    re.compile(
        r"^import sys; from multiprocessing\.forkserver import main; "
        r"main\(\d+, \d+, [^;]*\)$"
    ),
)
_PY_FLAG_WITH_VALUE = frozenset({"-W", "-X"})
_PY_FLAGS = frozenset({"-I", "-E", "-s", "-S", "-B", "-u", "-q", "-O", "-OO", "-b", "-bb", "-P"})


def _python_args_allowed(argv: list[str]) -> bool:
    rest = argv[1:]
    # Options d'interpreteur sans effet reseau tolerees devant -m / -c.
    while rest:
        if rest[0] in _PY_FLAG_WITH_VALUE:
            rest = rest[2:]
        elif rest[0] in _PY_FLAGS:
            rest = rest[1:]
        else:
            break
    if len(rest) >= 2 and rest[0] == "-m" and rest[1] == "graphify":
        return True
    if len(rest) >= 2 and rest[0] == "-c":
        code = rest[1]
        if _GRAPHIFY_CODE_RE.match(code):
            return True
        return any(r.match(code) for r in _MP_CODE_RES)
    return False


def _git_args_allowed(argv: list[str]) -> bool:
    rest = argv[1:]
    # Saute les options globales `-C <dir>` / `-c key=val` placees avant la sous-commande.
    while rest and rest[0] in ("-C", "-c"):
        rest = rest[2:]
    return bool(rest) and rest[0] in _GIT_ALLOWED_SUBCOMMANDS


def _check_exec(executable: object, argv: object) -> None:
    if isinstance(argv, (str, bytes, os.PathLike)):
        args = [os.fsdecode(argv) if not isinstance(argv, str) else argv]
    else:
        try:
            args = [os.fsdecode(a) if not isinstance(a, str) else a for a in (argv or [])]
        except TypeError:
            args = []
    exe = executable if executable is not None else (args[0] if args else "")
    name = _exe_name(exe)
    if not args:
        args = [str(exe)]
    if name == "git" and _git_args_allowed(args):
        return
    if name == "cpp":
        return
    if _is_current_python(exe) and _python_args_allowed(args):
        return
    _deny(f"lancement du programme {name!r} ({' '.join(args[:4])}...)")


def _hook(event: str, args: tuple) -> None:
    if event == "socket.__new__":
        # args = (socket, family, type, proto)
        family = args[1] if len(args) > 1 else None
        if family not in (_unix_family(), -1):
            _deny(f"creation d'une socket reseau (famille {family})")
        return
    if event in _SOCKET_USE_EVENTS:
        sock = args[0] if args else None
        if getattr(sock, "family", None) != _unix_family():
            _deny(f"{event} vers {args[1] if len(args) > 1 else '?'}")
        return
    if event in _DNS_EVENTS:
        _deny(f"resolution DNS ({event} {args[0] if args else ''})")
    if event in _ALWAYS_BLOCKED_EVENTS:
        _deny(event)
    if event == "subprocess.Popen":
        # args = (executable, args, cwd, env)
        _check_exec(args[0], args[1])
        _TLS.popen_checked = True
        return
    if event == "os.exec":
        # args = (path, args, env)
        _check_exec(args[0], args[1])
        return
    if event == "os.spawn":
        # args = (mode, path, args, env)
        _check_exec(args[1], args[2])
        return
    if event == "os.posix_spawn":
        # args = (path, argv, env)
        _check_exec(args[0], args[1])
        return
    if event == "_winapi.CreateProcess":
        # Deja controle via subprocess.Popen, ou processus de travail multiprocessing.
        if getattr(_TLS, "popen_checked", False):
            _TLS.popen_checked = False
            return
        cmdline = str(args[1] if len(args) > 1 else "")
        if "--multiprocessing-fork" in cmdline:
            return
        _deny(f"CreateProcess {cmdline[:80]}")


def install() -> None:
    """Installe le verrou (idempotent)."""
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return
        sys.addaudithook(_hook)
        _INSTALLED = True
