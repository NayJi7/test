"""graphify-local - (re)construction du paquet pip (Windows, Python 3.10).

A lancer sur une machine CONNECTEE (Windows, Linux ou macOS, Python >= 3.10).

Usage (depuis le dossier bundle/) :
    python build_bundle.py                       # fork dans ../fork, postes en Python 3.10.7
    python build_bundle.py --fork ../fork --python 3.10.7

Etapes :
1. Construit le wheel graphify-local depuis les sources du fork, de facon
   reproductible (SOURCE_DATE_EPOCH fixe : meme source => meme empreinte).
2. Telecharge dans wheelhouse/ (cache de construction, jamais livre) les
   dependances precompilees pour Windows et la version de Python des postes,
   afin d'en calculer les empreintes. Si requirements/windows-amd64-py<XY>.lock
   existe, ses versions sont imposees (aucune derive). Pour mettre a jour
   volontairement une dependance, supprimez le .lock puis relisez le diff affiche.
3. Verifie que toutes les dependances requises par la cible sont presentes
   (scripts/complete-wheelhouse.py ; ex. `tomli` sous Python 3.10).
4. Regenere le .lock (version + sha256) et affiche les differences.
5. Met a jour paquet-pip/ (wheel + requirements.txt) et produit
   graphify-local-<version>-pip.zip (+ empreinte .sha256).
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLATFORMS = ["windows-amd64"]
TAGS = {
    "linux-x86_64": ["manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64", "manylinux1_x86_64",
                     "manylinux2010_x86_64", "manylinux_2_5_x86_64", "manylinux_2_12_x86_64"],
    "windows-amd64": ["win_amd64"],
    "macos-arm64": ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_13_0_arm64", "macosx_14_0_arm64",
                    "macosx_10_9_universal2", "macosx_10_13_universal2", "macosx_11_0_universal2"],
}


def run(cmd: list[str], **kw) -> None:
    print("  $", " ".join(str(c) for c in cmd[:6]), "..." if len(cmd) > 6 else "")
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fork", type=Path, default=HERE.parent / "fork")
    ap.add_argument("--python", default="3.10.7", help="version de Python des postes (defaut 3.10.7)")
    args = ap.parse_args()

    fork = args.fork.resolve()
    full = args.python
    major, minor = full.split(".")[:2]
    pytag, abi = f"py{major}{minor}", f"cp{major}{minor}"
    platforms = PLATFORMS
    m = re.search(r'^version = "([^"]+)"', (fork / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit("version introuvable dans pyproject.toml")
    version = m.group(1)

    # 1. Environnement de construction + wheel du fork
    bvenv = HERE / ".build-venv"
    if not bvenv.exists():
        venv.EnvBuilder(with_pip=True, symlinks=(os.name != "nt")).create(bvenv)
    bpy = bvenv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    run([bpy, "-m", "pip", "install", "-q", "build>=1.5", "setuptools>=83", "wheel>=0.47", "packaging"])
    print(f"[build] wheel graphify-local {version} depuis {fork} (postes : Python {full})")
    for d in ("build", "dist"):
        shutil.rmtree(fork / d, ignore_errors=True)
    # Droits normalises (le wheel les enregistre) : meme source => meme empreinte,
    # quels que soient l'umask ou l'outil d'extraction (git archive, zip...).
    if os.name != "nt":
        for f in [*fork.glob("*"), *(fork / "graphify").rglob("*")]:
            if f.is_file():
                f.chmod(0o755 if f.stat().st_mode & 0o111 else 0o644)
    env = dict(os.environ, SOURCE_DATE_EPOCH=os.environ.get("SOURCE_DATE_EPOCH", "1792800000"))
    run([bpy, "-m", "build", "--wheel", "--no-isolation"], cwd=fork, env=env)
    wheelhouse = HERE / "wheelhouse"
    wheelhouse.mkdir(exist_ok=True)
    for old in wheelhouse.glob("graphify_local-*.whl"):
        old.unlink()
    shutil.copy2(fork / "dist" / f"graphify_local-{version}-py3-none-any.whl", wheelhouse)
    for d in ("build", "dist"):
        shutil.rmtree(fork / d, ignore_errors=True)
    for egg in fork.glob("*.egg-info"):
        shutil.rmtree(egg, ignore_errors=True)

    # 2. Dependances par systeme (versions figees par les .lock existants)
    reqs = HERE / "requirements"
    reqs.mkdir(exist_ok=True)
    previous: dict[str, str] = {}
    for plat in platforms:
        name = f"{plat}-{pytag}"
        print(f"[build] dependances {name}")
        target = wheelhouse / name
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir()
        cmd = [bpy, "-m", "pip", "download", "-q", "--only-binary=:all:", "--python-version", f"{major}.{minor}",
               "--implementation", "cp", "--abi", abi, "--abi", "abi3", "--abi", "none", "-d", target,
               "--find-links", wheelhouse]
        for tag in TAGS[plat]:
            cmd += ["--platform", tag]
        lock = reqs / f"{name}.lock"
        if lock.is_file():
            previous[name] = lock.read_text(encoding="utf-8")
            pins = [l.rstrip(" \\") for l in previous[name].splitlines()
                    if re.match(r"^[A-Za-z0-9_.-]+==", l) and not l.startswith("graphify-local==")]
            constraints = HERE / f".constraints-{name}.txt"
            constraints.write_text("\n".join(pins) + "\n", encoding="utf-8")
            cmd += ["-c", constraints]
        run(cmd + [f"graphify-local[local]=={version}"])

    # 3. Completude pour la cible exacte, 4. verrous, diff
    run([bpy, HERE / "scripts" / "complete-wheelhouse.py", full])
    for c in HERE.glob(".constraints-*.txt"):
        c.unlink()
    run([sys.executable, "-I", HERE / "scripts" / "make-locks.py"])
    for name, old in previous.items():
        new = (reqs / f"{name}.lock").read_text(encoding="utf-8")
        diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0))
        print(f"[build] differences de verrouillage {name} : {'aucune' if not diff else ''}")
        for line in diff[2:]:
            print("   ", line)

    # 5. Paquet pip
    run([sys.executable, "-I", HERE / "scripts" / "make-pip-zip.py", version, "--lock", f"windows-amd64-{pytag}"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
