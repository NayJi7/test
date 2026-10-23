"""graphify - installeur HORS LIGNE (Windows, Linux, macOS).

Usage :
    Windows       : double-clic sur install-windows.cmd
    Linux / macOS : bash install-offline.sh

Une seule methode d'installation : l'installeur cree, A COTE DE LUI, un dossier
`graphify-local/` autonome :

    graphify-local/
        graphify.exe        (Windows ; `graphify` sous Linux/macOS) : la commande
        lib/                graphify + ses 66 dependances, deja decompresses
        graphify-local.json version, Python utilise, date
        LISEZMOI.txt

Ce dossier peut ensuite etre deplace n'importe ou sur le poste, puis ajoute au
PATH : `graphify` fonctionne alors comme apres un `pip install`. L'installeur
ne modifie ni le PATH, ni le Python du poste, ni aucun autre dossier.

`graphify.exe` est le lanceur standard que pip utilise pour ses commandes
(`t64.exe` de distlib, fourni dans launcher/). Il lance le Python 3.10 qui a
execute l'installeur (chemin absolu, inscrit dans le lanceur : jamais un
python.exe trouve dans le dossier courant) en mode isole (-I : PYTHONPATH,
PYTHONHOME et site utilisateur ignores). Le dossier lib/ est retrouve a cote
du lanceur : deplacer le dossier ne casse rien.

Garanties :
- seuls les paquets du dossier wheelhouse/ sont utilises (rien n'est telecharge,
  pip n'est pas utilise) ;
- chaque paquet doit avoir exactement l'empreinte sha256 inscrite dans
  requirements/<plateforme>-py<XY>.lock, et chaque paquet du .lock doit etre
  present : sinon rien n'est installe ;
- auto-controle final : `graphify kiro verify`.

N'utilise que la bibliotheque standard de Python.
"""
from __future__ import annotations

import compileall
import datetime
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
NAME = "graphify-local"
DEST = HERE / NAME
MARKER = "graphify-local.json"
# Present tant que l'installation n'est pas terminee (supprime a la fin).
IN_PROGRESS = "INSTALLATION-INCOMPLETE.txt"
# Lanceur distlib 0.4.0 (distlib/t64.exe du wheel distlib-0.4.0-py2.py3-none-any.whl,
# sha256 du wheel 9659f7d87e46584a30b5780e43ac7a2143098441670ff0a49d5f9034c54a6c16).
LAUNCHER_SHA256 = "81a618f21cb87db9076134e70388b6e9cb7c2106739011b6a51772d22cae06b7"
WIN_MAX_PATH = 259  # MAX_PATH (260) moins le NUL final
# Ajout maximal d'un fichier .pyc par rapport a son .py :
# "a/b.py" -> "a/__pycache__/b.cpython-310.pyc"
PYC_EXTRA = len("__pycache__/") + len(".cpython-3XX.pyc") - len(".py")

# Code du lanceur (__main__.py de l'archive ajoutee au lanceur).
LAUNCHER_MAIN = '''\
# graphify-local : lanceur du dossier portable (genere par installer.py).
import os
import re
import sys

_here = os.path.dirname(os.path.realpath(sys.argv[0]))
_lib = os.path.join(_here, "lib")
if not os.path.isfile(os.path.join(_lib, "graphify", "__init__.py")):
    sys.exit("graphify : dossier lib introuvable dans " + _here + " (relancez l'installeur).")
sys.path.insert(0, _lib)
# Pour les processus Python que graphify relance lui-meme (python -m graphify).
os.environ["PYTHONPATH"] = _lib
sys.argv[0] = re.sub(r"(\\.exe)?$", "", sys.argv[0], flags=re.IGNORECASE)
from graphify.__main__ import main
sys.exit(main())
'''

LISEZMOI = """\
graphify (graphify-local {version}) - dossier portable
=====================================================

Ce dossier contient tout graphify : la commande {exe}, et dans lib/ graphify
et toutes ses dependances. Il n'a besoin que de Python {pyver} :
    {python}
(le Python qui a lance l'installeur ; si ce Python est deplace ou desinstalle,
relancez l'installeur).

Utilisation
-----------
1. Placez ce dossier ou vous voulez (a un endroit ou l'execution de programmes
   est autorisee). Sous Windows, son chemin complet ne doit pas depasser
   {maxlen} caracteres (limite Windows de 260 caracteres par fichier).
2. Ajoutez ce dossier au PATH, puis ouvrez un nouveau terminal.
3. Verifiez : graphify kiro verify

Le dossier peut etre deplace a nouveau plus tard : mettez simplement le PATH a
jour. Les hooks git deja installes (graphify hook install) retrouvent le
nouveau dossier via le PATH.

Desinstaller : retirez le dossier du PATH et supprimez-le.
"""


def fail(msg: str) -> int:
    print(f"\nERREUR : {msg}", file=sys.stderr)
    return 1


def detect_platform() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "windows-amd64"
    if sys.platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    if sys.platform == "darwin" and machine in ("arm64", "aarch64"):
        return "macos-arm64"
    raise SystemExit(f"Plateforme non prise en charge par ce bundle : {sys.platform} / {platform.machine()}")


def canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def read_lock(lock: Path) -> dict[str, tuple[str, set[str]]]:
    """{nom canonique: (version, {sha256...})} depuis un .lock au format pip."""
    text = lock.read_text(encoding="utf-8").replace("\\\n", " ")
    pins: dict[str, tuple[str, set[str]]] = {}
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+)==(\S+)\s+(.*)$", line.strip())
        if m:
            hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", m.group(3)))
            pins[canon(m.group(1))] = (m.group(2), hashes)
    return pins


def verified_wheels(wheelhouse: Path, lock: Path) -> list[Path]:
    """Les wheels du .lock, apres verification de leur empreinte sha256."""
    pins = read_lock(lock)
    found: dict[str, Path] = {}
    errors = []
    rejected = set()
    for whl in sorted(wheelhouse.glob("*.whl")):
        parts = whl.name[:-4].split("-")
        name, version = canon(parts[0]), parts[1]
        pin = pins.get(name)
        if pin is None or pin[0] != version:
            rejected.add(name)
            errors.append(f"{whl.name} : absent du verrouillage {lock.name}")
            continue
        digest = hashlib.sha256(whl.read_bytes()).hexdigest()
        if digest not in pin[1]:
            rejected.add(name)
            errors.append(f"{whl.name} : empreinte {digest} differente de celle du verrouillage")
            continue
        found[name] = whl
    for name, (version, _) in sorted(pins.items()):
        if name not in found and name not in rejected:
            errors.append(f"{name}=={version} : paquet absent de {wheelhouse}")
    if errors:
        raise SystemExit("Paquets refuses (rien n'a ete installe) :\n  - " + "\n  - ".join(errors))
    return [found[n] for n in sorted(found)]


def wheel_targets(whl: Path) -> list[tuple[zipfile.ZipInfo, str]]:
    """(entree, chemin relatif dans lib/) pour chaque fichier a installer.

    Comme pip : le contenu d'un wheel va dans site-packages, sauf <nom>.data/
    dont seuls purelib/ et platlib/ vont aussi dans site-packages (scripts,
    headers et data ne servent pas a graphify et ne sont pas installes).
    Refuse tout chemin absolu ou contenant '..'.
    """
    out = []
    with zipfile.ZipFile(whl) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            p = PurePosixPath(info.filename)
            if p.is_absolute() or ".." in p.parts or ":" in info.filename or "\\" in info.filename:
                raise SystemExit(f"{whl.name} : chemin interdit dans l'archive : {info.filename}")
            if p.parts[0].endswith(".data"):
                if len(p.parts) > 2 and p.parts[1] in ("purelib", "platlib"):
                    out.append((info, str(PurePosixPath(*p.parts[2:]))))
                continue
            out.append((info, info.filename))
    return out


def long_paths_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as key:
            return winreg.QueryValueEx(key, "LongPathsEnabled")[0] == 1
    except OSError:
        return False


def build_launcher(target: Path, python: str) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("__main__.py", date_time=(2026, 1, 1, 0, 0, 0)), LAUNCHER_MAIN)
    if sys.platform == "win32":
        stub = (HERE / "launcher" / "t64.exe").read_bytes()
        if hashlib.sha256(stub).hexdigest() != LAUNCHER_SHA256:
            raise SystemExit("launcher/t64.exe : empreinte inattendue, installation annulee.")
        shebang = f'#!"{python}" -I\n'.encode("utf-8")
    else:
        stub = b""
        shebang = f"#!{python} -I\n".encode("utf-8")
    target.write_bytes(stub + shebang + buf.getvalue())
    if sys.platform != "win32":
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def remove_tree(path: Path) -> bool:
    """Supprime un dossier cree par l'installeur, en reessayant pendant ~20 s :
    sous Windows, un antivirus qui analyse encore des fichiers neufs les garde
    ouverts quelques secondes (erreur "Acces refuse")."""
    def onerror(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except OSError:
            pass
    for attempt in range(20):
        shutil.rmtree(path, onerror=onerror)
        if not path.exists():
            return True
        time.sleep(1)
    return False


def check_python(python: str) -> str | None:
    if sys.maxsize <= 2 ** 32:
        return "ce Python est en 32 bits ; graphify a besoin de Python 3.10 en 64 bits."
    if '"' in python or "\n" in python:
        return f"chemin de Python non pris en charge : {python!r}"
    if sys.platform != "win32" and (" " in python or len(python) > 120):
        return f"chemin de Python non pris en charge dans un lanceur Linux/macOS : {python!r}"
    return None


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    plat = detect_platform()
    tag = f"{sys.version_info[0]}{sys.version_info[1]}"
    name = f"{plat}-py{tag}"
    wheelhouse = HERE / "wheelhouse" / name
    lock = HERE / "requirements" / f"{name}.lock"
    if lock.is_file() and not wheelhouse.is_dir():
        return fail(f"le dossier des paquets {wheelhouse} est absent. Vous lancez probablement "
                    "l'installeur depuis l'archive des SOURCES, qui ne contient pas les paquets : "
                    "utilisez le zip d'installation, ou construisez-le avec build_bundle.py.")
    if not wheelhouse.is_dir() or not lock.is_file():
        available = sorted(p.stem.rsplit("-py", 1)[1] for p in (HERE / "requirements").glob(f"{plat}-py*.lock"))
        wanted = ", ".join(f"Python {a[0]}.{a[1:]}" for a in available) or "aucune"
        return fail(f"ce bundle ne contient pas de paquets pour Python {platform.python_version()} "
                    f"sur {plat}. Versions prevues : {wanted}.")

    python = os.path.realpath(sys.executable)
    problem = check_python(python)
    if problem:
        return fail(problem)
    exe = "graphify.exe" if sys.platform == "win32" else "graphify"
    print(f"[install] Python utilise : {python} ({platform.python_version()})")
    print(f"[install] dossier cree   : {DEST}")

    if DEST.exists() and not ((DEST / MARKER).is_file() or (DEST / IN_PROGRESS).is_file()):
        return fail(f"{DEST} existe deja et n'est pas une installation graphify : "
                    "deplacez-le ou renommez-le, puis relancez.")

    wheels = verified_wheels(wheelhouse, lock)
    print(f"[install] {len(wheels)} paquets verifies (sha256 conformes a {lock.name})")
    plan = [(whl, wheel_targets(whl)) for whl in wheels]

    longest = max(len(rel) + (PYC_EXTRA if rel.endswith(".py") else 0) for _, items in plan for _, rel in items)
    suffix = len(os.sep + "lib" + os.sep) + longest
    maxlen = WIN_MAX_PATH - suffix
    if sys.platform == "win32" and not long_paths_enabled() and len(str(DEST)) > maxlen:
        return fail(f"le chemin {DEST} est trop long ({len(str(DEST))} caracteres, maximum {maxlen} : "
                    "limite Windows de 260 caracteres par fichier). Placez le bundle dans un dossier "
                    "au chemin plus court, puis relancez.")

    # Restes eventuels d'une version precedente de l'installeur.
    for leftover in (HERE / f"{NAME}.nouveau", HERE / f"{NAME}.ancien"):
        if leftover.exists() and not remove_tree(leftover):
            print(f"[install] (impossible de supprimer {leftover} : supprimez-le a la main)")
    # Installation directement dans le dossier final : pas de renommage de
    # dossier a la fin (refuse par Windows tant qu'un antivirus analyse les
    # fichiers qui viennent d'etre ecrits).
    if DEST.exists():
        print("[install] suppression de l'installation precedente...")
        if not remove_tree(DEST):
            return fail(f"impossible de supprimer l'installation precedente {DEST} : un fichier est "
                        "encore ouvert (graphify en cours d'utilisation, ou analyse antivirus). "
                        "Fermez les terminaux qui utilisent graphify, puis relancez.")
    lib = DEST / "lib"
    lib.mkdir(parents=True)
    (DEST / IN_PROGRESS).write_text("Installation interrompue : relancez l'installeur.\n", encoding="utf-8")
    owners: dict[str, str] = {}
    for whl, items in plan:
        with zipfile.ZipFile(whl) as z:
            for info, rel in items:
                key = rel.lower()
                if key in owners and owners[key] != whl.name:
                    return fail(f"{rel} est fourni a la fois par {owners[key]} et {whl.name}")
                owners[key] = whl.name
                out = lib / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    print(f"[install] {len(owners)} fichiers decompresses dans lib/")
    print("[install] precompilation des modules Python (peut prendre une minute)...")
    compileall.compile_dir(str(lib), quiet=2, workers=0)

    build_launcher(DEST / exe, python)
    version = read_lock(lock)["graphify-local"][0]
    (DEST / "LISEZMOI.txt").write_text(LISEZMOI.format(
        version=version, exe=exe, pyver=f"{sys.version_info[0]}.{sys.version_info[1]}",
        python=python, maxlen=maxlen), encoding="utf-8")
    (DEST / MARKER).write_text(json.dumps({
        "version": version,
        "plateforme": name,
        "python": python,
        "python_version": platform.python_version(),
        "installe_le": datetime.datetime.now().isoformat(timespec="seconds"),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DEST / IN_PROGRESS).unlink()

    graphify = DEST / exe
    print("[install] auto-controle :")
    try:
        res = subprocess.run([str(graphify), "kiro", "verify"])
    except OSError as exc:
        print(f"Impossible de lancer {graphify} : {exc}", file=sys.stderr)
        if getattr(exc, "winerror", None) == 1260:
            print("Une strategie de groupe interdit d'executer des programmes dans ce dossier. "
                  "Placez le bundle a un endroit ou l'execution est autorisee, puis relancez.",
                  file=sys.stderr)
        return 1
    if res.returncode != 0:
        return fail("auto-controle en echec : ne pas utiliser cette installation.")

    print()
    print(f"Installe : {DEST}")
    print("Ce dossier est autonome : deplacez-le ou vous voulez, puis ajoutez-le au PATH.")
    if sys.platform == "win32":
        print(f"(chemin complet du dossier : {maxlen} caracteres au maximum)")
        stale = Path(os.environ.get("LOCALAPPDATA", "")) / "graphify" / "graphify.cmd"
        if os.environ.get("LOCALAPPDATA") and stale.is_file():
            print(f"\nATTENTION : une ancienne installation de test existe dans {stale.parent}. "
                  "Supprimez ce dossier et retirez-le du PATH, sinon il pourrait masquer le nouveau.")
    print("Puis, dans chaque projet Kiro : graphify kiro install (ou demandez-le a Kiro), et commitez .kiro/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
