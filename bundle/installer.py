"""graphify - installeur HORS LIGNE (Windows, Linux, macOS).

Usage :
    Windows : double-clic sur install-windows.cmd   (ou : py -3.10 -I installer.py)
    Linux / macOS : bash install-offline.sh          (ou : python3.10 -I installer.py)

Options :
    --dest DOSSIER   dossier d'installation
                     (defaut : %LOCALAPPDATA%\\graphify sous Windows, ~/.local/graphify ailleurs)
    --no-path        Windows : ne pas ajouter graphify au PATH de l'utilisateur
    --mode MODE      "dossier" (defaut sous Windows) ou "venv" (defaut ailleurs)

Modes :
- dossier : les paquets sont installes dans DOSSIER\\lib et graphify est lance
  par le Python deja present sur le poste, via DOSSIER\\graphify.cmd
  (`python -m graphify`). Aucun executable n'est copie ni cree : compatible
  avec les strategies de groupe Windows qui interdisent d'executer des
  programmes depuis le profil utilisateur (erreur WinError 1260). Le Python
  du poste n'est pas modifie (rien n'est ajoute a ses site-packages).
- venv : environnement Python dedie (copie/lien de python.exe dans DOSSIER\\venv).

Garanties :
- seuls les paquets du dossier wheelhouse/ sont utilises (--no-index : PyPI
  n'est jamais contacte) ;
- chaque paquet doit avoir exactement l'empreinte sha256 inscrite dans
  requirements/<plateforme>-py<XY>.lock (--require-hashes), XY = version de Python, sinon l'installation echoue ;
- le Python du systeme n'est jamais modifie ;
- auto-controle final : `graphify kiro verify`.

N'utilise que la bibliotheque standard de Python.
"""
from __future__ import annotations

import argparse
import os
import shutil
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


def bundled_pip_command() -> list[str]:
    """Commande pip sans rien installer dans le Python du poste.

    Utilise le pip livre avec Python (ensurepip/_bundled/pip-*.whl), execute
    directement depuis son fichier wheel. A defaut, `python -m pip`.
    """
    try:
        import ensurepip

        wheels = sorted((Path(ensurepip.__file__).parent / "_bundled").glob("pip-*.whl"))
    except Exception:
        wheels = []
    if wheels:
        # -E -s : ignore PYTHONPATH et le site utilisateur ; pas -I, qui
        # retirerait le dossier du script (le wheel) de sys.path.
        return [sys.executable, "-E", "-s", str(wheels[-1] / "pip")]
    return [sys.executable, "-m", "pip"]


def write_wrapper(dest: Path, lib_dir: Path) -> Path:
    """Lanceur `graphify` qui utilise le Python du poste et le dossier lib/."""
    if sys.platform == "win32":
        wrapper = dest / "graphify.cmd"
        wrapper.write_text(
            "@echo off\r\n"
            "rem graphify (bundle interne) - lanceur genere par installer.py\r\n"
            "setlocal\r\n"
            f'set "PYTHONPATH={lib_dir}"\r\n'
            'set "PYTHONNOUSERSITE=1"\r\n'
            f'"{sys.executable}" -m graphify %*\r\n'
            "exit /b %ERRORLEVEL%\r\n",
            encoding="ascii",
            newline="",
        )
    else:
        wrapper = dest / "bin" / "graphify"
        wrapper.parent.mkdir(parents=True, exist_ok=True)
        wrapper.write_text(
            "#!/bin/sh\n"
            "# graphify (bundle interne) - lanceur genere par installer.py\n"
            f'PYTHONPATH="{lib_dir}" PYTHONNOUSERSITE=1 exec "{sys.executable}" -m graphify "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    return wrapper


def install_dossier(dest: Path, wheelhouse: Path, lock: Path, pip_env: dict) -> Path | None:
    lib_dir = dest / "lib"
    marker = lib_dir / ".graphify-local"
    if lib_dir.exists():
        if not marker.exists() and any(lib_dir.iterdir()):
            print(f"{lib_dir} existe deja et n'a pas ete cree par cet installeur : choisissez un autre --dest.",
                  file=sys.stderr)
            return None
        shutil.rmtree(lib_dir)
    old_venv = dest / "venv"
    if (old_venv / "pyvenv.cfg").exists():
        shutil.rmtree(old_venv, ignore_errors=True)  # reste d'une tentative en mode venv
    lib_dir.mkdir(parents=True)
    res = subprocess.run(
        bundled_pip_command() + [
            "install", "--no-index", "--only-binary=:all:", "--require-hashes",
            "--find-links", str(wheelhouse), "-r", str(lock),
            "--target", str(lib_dir), "--no-warn-script-location", "--disable-pip-version-check",
        ],
        env=pip_env,
    )
    if res.returncode != 0:
        print("Echec de l'installation (paquet manquant ou empreinte differente).", file=sys.stderr)
        return None
    # Les lanceurs .exe generes par pip ne sont pas utilises : on les retire.
    shutil.rmtree(lib_dir / "bin", ignore_errors=True)
    marker.write_text("installe par installer.py (mode dossier)\n", encoding="utf-8")
    return write_wrapper(dest, lib_dir)


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description="Installation hors ligne de graphify")
    parser.add_argument("--dest", type=Path, default=None)
    parser.add_argument("--no-path", action="store_true")
    parser.add_argument("--mode", choices=("dossier", "venv"),
                        default="dossier" if sys.platform == "win32" else "venv")
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

    pip_env = dict(os.environ, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PIP_NO_INPUT="1")
    dest.mkdir(parents=True, exist_ok=True)

    if args.mode == "dossier":
        print(f"[install] dossier : {dest} (plateforme {plat}, Python du poste : {sys.executable})")
        graphify = install_dossier(dest, wheelhouse, lock, pip_env)
        if graphify is None:
            return 1
        bin_dir = graphify.parent
    else:
        env_dir = dest / "venv"
        print(f"[install] environnement : {env_dir} (plateforme {plat})")
        # Comme `python -m venv` : liens symboliques sous Linux/macOS (indispensable
        # pour les Python compiles avec libpython partagee), copie sous Windows.
        try:
            venv.EnvBuilder(with_pip=True, clear=env_dir.exists(), symlinks=(os.name != "nt")).create(env_dir)
        except OSError as exc:
            print(f"Creation de l'environnement impossible : {exc}", file=sys.stderr)
            if getattr(exc, "winerror", None) == 1260:
                print("Une strategie de groupe interdit d'executer la copie de python.exe. "
                      "Relancez avec --mode dossier (mode par defaut sous Windows).", file=sys.stderr)
            return 1
        if sys.platform == "win32":
            py = env_dir / "Scripts" / "python.exe"
            graphify = env_dir / "Scripts" / "graphify.exe"
        else:
            py = env_dir / "bin" / "python"
            graphify = env_dir / "bin" / "graphify"
        res = subprocess.run(
            [str(py), "-m", "pip", "install", "--no-index", "--only-binary=:all:", "--require-hashes",
             "--find-links", str(wheelhouse), "-r", str(lock)],
            env=pip_env,
        )
        if res.returncode != 0:
            print("Echec de l'installation (paquet manquant ou empreinte differente).", file=sys.stderr)
            return res.returncode
        bin_dir = graphify.parent
        if sys.platform != "win32":
            bin_dir = dest / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            link = bin_dir / "graphify"
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(graphify)

    if sys.platform == "win32":
        if args.no_path:
            path_msg = f"Ajoutez ce dossier au PATH utilisateur : {bin_dir}"
        elif add_to_user_path_windows(bin_dir):
            path_msg = f"{bin_dir} a ete ajoute a votre PATH (ouvrez un nouveau terminal)."
        else:
            path_msg = f"{bin_dir} est deja dans votre PATH."
    else:
        path_msg = f"Ajoutez ce dossier au PATH (par ex. dans ~/.bashrc ou ~/.zshrc) :\n  export PATH=\"{bin_dir}:$PATH\""

    print("[install] auto-controle :")
    cmd = ["cmd", "/c", str(graphify)] if str(graphify).lower().endswith(".cmd") else [str(graphify)]
    try:
        res = subprocess.run(cmd + ["kiro", "verify"])
    except OSError as exc:
        print(f"Impossible de lancer graphify : {exc}", file=sys.stderr)
        if getattr(exc, "winerror", None) == 1260:
            print("Une strategie de groupe bloque ce lanceur dans ce dossier : relancez avec "
                  "--dest <dossier ou vos scripts sont autorises>.", file=sys.stderr)
        return 1
    if res.returncode != 0:
        print("Auto-controle en echec : ne pas utiliser cette installation. Si le message parle d'une "
              "strategie de groupe, relancez avec --dest <dossier ou vos scripts sont autorises>.",
              file=sys.stderr)
        return res.returncode

    print()
    print("Installe.", path_msg)
    print("Puis, dans chaque projet Kiro : graphify kiro install (ou demandez-le a Kiro), et commitez .kiro/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
