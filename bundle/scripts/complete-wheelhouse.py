"""Complete et verifie wheelhouse/<plateforme>-py<XY>/ pour la cible exacte.

`pip download --python-version X --platform Y` evalue les conditions des
dependances (`python_version < "3.11"`, `sys_platform == "win32"`, ...) avec la
machine qui construit, pas avec la cible. Il peut donc oublier des paquets
necessaires sur le poste (ex. `tomli` sous Python 3.10, `colorama` sous
Windows).

Ce script lit les dependances declarees par chaque wheel, evalue leurs
conditions pour la cible (version de Python + systeme), telecharge les paquets
manquants (`--no-deps`, puis nouvelle passe) et echoue si une dependance reste
introuvable ou de version incompatible.

Usage (depuis bundle/, avec le Python de .build-venv qui fournit `packaging`) :
    .build-venv/bin/python scripts/complete-wheelhouse.py 3.10.7
"""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from email.parser import Parser
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {
    "linux-x86_64": {"sys_platform": "linux", "platform_system": "Linux", "os_name": "posix", "platform_machine": "x86_64",
                     "tags": ["manylinux2014_x86_64", "manylinux_2_17_x86_64", "manylinux_2_28_x86_64", "manylinux1_x86_64",
                              "manylinux2010_x86_64", "manylinux_2_5_x86_64", "manylinux_2_12_x86_64"]},
    "windows-amd64": {"sys_platform": "win32", "platform_system": "Windows", "os_name": "nt", "platform_machine": "AMD64",
                      "tags": ["win_amd64"]},
    "macos-arm64": {"sys_platform": "darwin", "platform_system": "Darwin", "os_name": "posix", "platform_machine": "arm64",
                    "tags": ["macosx_11_0_arm64", "macosx_12_0_arm64", "macosx_13_0_arm64", "macosx_14_0_arm64",
                             "macosx_10_9_universal2", "macosx_10_13_universal2", "macosx_11_0_universal2"]},
}


def wheel_meta(path: Path):
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
        msg = Parser().parsestr(z.read(name).decode("utf-8"))
    return canonicalize_name(msg["Name"]), Version(msg["Version"]), msg.get_all("Requires-Dist") or []


def check(dirpath: Path, env: dict, root_extras: dict[str, set[str]]) -> list[str]:
    wheels = {}
    for w in list(dirpath.glob("*.whl")):
        n, v, reqs = wheel_meta(w)
        wheels[n] = (v, reqs)
    missing = []
    for pkg, (_, reqs) in wheels.items():
        extras = root_extras.get(pkg, {""})
        for raw in reqs:
            req = Requirement(raw)
            if req.marker is not None and not any(req.marker.evaluate({**env, "extra": e}) for e in extras):
                continue
            dep = canonicalize_name(req.name)
            if dep not in wheels:
                missing.append(str(req.name) + (str(req.specifier) if req.specifier else ""))
            elif req.specifier and not req.specifier.contains(wheels[dep][0], prereleases=True):
                raise SystemExit(f"[complete] {dirpath.name} : {pkg} demande {req}, present {wheels[dep][0]}")
    return sorted(set(missing))


def main() -> None:
    full = sys.argv[1] if len(sys.argv) > 1 else "3.10.7"
    major, minor = full.split(".")[:2]
    abi = f"cp{major}{minor}"
    for plat, t in TARGETS.items():
        d = ROOT / "wheelhouse" / f"{plat}-py{major}{minor}"
        if not d.is_dir():
            continue
        env = {"python_version": f"{major}.{minor}", "python_full_version": full, "implementation_name": "cpython",
               "platform_python_implementation": "CPython", "implementation_version": full,
               "sys_platform": t["sys_platform"], "platform_system": t["platform_system"], "os_name": t["os_name"],
               "platform_machine": t["platform_machine"], "platform_release": "", "platform_version": ""}
        for _ in range(10):
            missing = check(d, env, {"graphify-local": {"", "local"}})
            if not missing:
                print(f"[complete] {d.name} : toutes les dependances de la cible sont presentes")
                break
            print(f"[complete] {d.name} : ajout de {', '.join(missing)}")
            args = [sys.executable, "-m", "pip", "download", "-q", "--no-deps", "--only-binary=:all:",
                    "--python-version", f"{major}.{minor}", "--implementation", "cp",
                    "--abi", abi, "--abi", "abi3", "--abi", "none", "-d", str(d)]
            for tag in t["tags"]:
                args += ["--platform", tag]
            constraints = ROOT / f".constraints-{d.name}.txt"
            if constraints.is_file():
                args += ["-c", str(constraints)]
            subprocess.run(args + missing, check=True)
        else:
            raise SystemExit(f"[complete] {d.name} : dependances toujours manquantes")


if __name__ == "__main__":
    main()
