"""Genere requirements/<plateforme>-py<XY>.lock depuis wheelhouse/<plateforme>-py<XY>/.

Chaque ligne fige le nom, la version et l'empreinte sha256 exacte du fichier
telecharge : `pip install --require-hashes` refusera tout autre fichier.
Usage : python3 -I scripts/make-locks.py   (depuis le dossier bundle/)
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def wheel_name_version(filename: str) -> tuple[str, str]:
    m = re.match(r"^([A-Za-z0-9_.]+?)-([0-9][^-]*)-", filename)
    if not m:
        raise SystemExit(f"nom de wheel inattendu : {filename}")
    return m.group(1).replace("_", "-").lower(), m.group(2)


def main() -> None:
    (ROOT / "requirements").mkdir(exist_ok=True)
    for wh in sorted((ROOT / "wheelhouse").glob("*-py3*")):
        if not wh.is_dir():
            continue
        name = wh.name
        pyver = re.search(r"-py(\d)(\d+)$", name)
        wheels = sorted(wh.glob("*.whl"))
        if not wheels or not pyver:
            print(f"[make-locks] {name} : ignore", file=sys.stderr)
            continue
        version = next((wheel_name_version(w.name)[1] for w in wheels
                        if wheel_name_version(w.name)[0] == "graphify-local"), "?")
        lines = [
            f"# graphify-local {version} - verrouillage {name} / CPython {pyver.group(1)}.{pyver.group(2)}",
            "# Genere par scripts/make-locks.py - ne pas modifier a la main.",
            "",
        ]
        for w in wheels:
            pkg, ver = wheel_name_version(w.name)
            digest = hashlib.sha256(w.read_bytes()).hexdigest()
            lines.append(f"{pkg}=={ver} \\\n    --hash=sha256:{digest}")
        (ROOT / "requirements" / f"{name}.lock").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[make-locks] {name} : {len(wheels)} paquets verrouilles")


if __name__ == "__main__":
    main()
