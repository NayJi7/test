"""graphify - installeur HORS LIGNE (Windows, Linux, macOS).

Usage :
    Windows : double-clic sur install-windows.cmd   (ou : py -3.10 -I installer.py)
    Linux / macOS : bash install-offline.sh          (ou : python3.10 -I installer.py)

Options :
    --dest DOSSIER   dossier d'installation
                     (defaut : %LOCALAPPDATA%\\graphify sous Windows, ~/.local/graphify ailleurs)
    --no-path        Windows : ne pas ajouter graphify au PATH de l'utilisateur

Garanties :
- seuls les paquets du dossier wheelhouse/ sont utilises (--no-index : PyPI
  n'est jamais contacte) ;
- chaque paquet doit avoir exactement l'empreinte sha256 inscrite dans
  requirements/<plateforme>-py<XY>.lock (--require-hashes), XY = version de Python, sinon l'installation echoue ;
- installation dans un environnement Python dedie (venv), sans toucher au
  Python du systeme ;
- auto-controle final : `graphify kiro verify`.

N'utilise que la bibliotheque standard de Python.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent


def detect_platform() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in ("amd64", "x86_64"):
        return "windows-amd64"
    if sys.platform.startswith("linux") and machine in ("x86_64", "amd64"):
        return "linux-x86_64"
    if sys.platform == "darwin" and machine in ("arm64", "aarch64"):
        return "macos-arm64"
    raise SystemExit(f"Plateforme non prise en charge par ce bundle : {sys.platform} / {platform.machine()}")


def default_dest() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "graphify"
    return Path.home() / ".local" / "graphify"


def add_to_user_path_windows(folder: Path) -> bool:
    """Ajoute `folder` au PATH de l'utilisateur (registre HKCU, sans droits admin)."""
    import ctypes
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        parts = [p for p in current.split(";") if p]
        if any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(str(folder)) for p in parts):
            return False
        parts.append(str(folder))
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))
    # Previent les nouvelles fenetres (Explorateur, terminaux) du changement.
    HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x001A, 0x0002
    ctypes.windll.user32.SendMessageTimeoutW(HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                                             SMTO_ABORTIFHUNG, 5000, None)
    return True


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description="Installation hors ligne de graphify")
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--no-path", action="store_true")
    args = parser.parse_args()

    plat = detect_platform()
    name = f"{plat}-py{sys.version_info[0]}{sys.version_info[1]}"
    dest = (args.dest or default_dest()).resolve()
    wheelhouse = HERE / "wheelhouse" / name
    lock = HERE / "requirements" / f"{name}.lock"
    if lock.is_file() and not wheelhouse.is_dir():
        print(f"Le dossier des paquets {wheelhouse} est absent. Vous lancez probablement "
              "l'installeur depuis l'archive des SOURCES, qui ne contient pas les paquets : "
              "utilisez le zip d'installation complet (graphify-local-<version>.zip), "
              "ou construisez-le avec build_bundle.py sur une machine connectee.", file=sys.stderr)
        return 1
    if not wheelhouse.is_dir() or not lock.is_file():
        available = sorted(p.stem for p in (HERE / "requirements").glob(f"{plat}-py*.lock"))
        wanted = ", ".join("Python " + a.rsplit("-py", 1)[1][0] + "." + a.rsplit("-py", 1)[1][1:] for a in available)
        print(f"Ce bundle ne contient pas de paquets pour Python {platform.python_version()} sur {plat}. "
              f"Versions prevues : {wanted or 'aucune'}.", file=sys.stderr)
        return 1

    env_dir = dest / "venv"
    print(f"[install] environnement : {env_dir} (plateforme {plat})")
    # Comme `python -m venv` : liens symboliques sous Linux/macOS (indispensable
    # pour les Python compiles avec libpython partagee), copie sous Windows.
    venv.EnvBuilder(with_pip=True, clear=env_dir.exists(), symlinks=(os.name != "nt")).create(env_dir)
    if sys.platform == "win32":
        py = env_dir / "Scripts" / "python.exe"
        graphify = env_dir / "Scripts" / "graphify.exe"
    else:
        py = env_dir / "bin" / "python"
        graphify = env_dir / "bin" / "graphify"

    pip_env = dict(os.environ, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1")
    res = subprocess.run(
        [str(py), "-m", "pip", "install", "--no-index", "--only-binary=:all:", "--require-hashes",
         "--find-links", str(wheelhouse), "-r", str(lock)],
        env=pip_env,
    )
    if res.returncode != 0:
        print("Echec de l'installation (paquet manquant ou empreinte differente).", file=sys.stderr)
        return res.returncode

    if sys.platform == "win32":
        bin_dir = graphify.parent
        if args.no_path:
            path_msg = f"Ajoutez ce dossier au PATH utilisateur : {bin_dir}"
        elif add_to_user_path_windows(bin_dir):
            path_msg = f"{bin_dir} a ete ajoute a votre PATH (ouvrez un nouveau terminal)."
        else:
            path_msg = f"{bin_dir} est deja dans votre PATH."
    else:
        bin_dir = dest / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        link = bin_dir / "graphify"
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(graphify)
        path_msg = f"Ajoutez ce dossier au PATH (par ex. dans ~/.bashrc ou ~/.zshrc) :\n  export PATH=\"{bin_dir}:$PATH\""

    print("[install] auto-controle :")
    res = subprocess.run([str(graphify), "kiro", "verify"])
    if res.returncode != 0:
        print("Auto-controle en echec : ne pas utiliser cette installation.", file=sys.stderr)
        return res.returncode

    print()
    print("Installe.", path_msg)
    print("Puis, dans chaque projet Kiro : graphify kiro install (ou demandez-le a Kiro), et commitez .kiro/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
