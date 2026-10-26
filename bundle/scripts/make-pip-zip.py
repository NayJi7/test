"""Assemble le paquet pip leger (Windows, Python 3.10) :

    python3 -I scripts/make-pip-zip.py <version>   -> graphify-local-<version>-pip.zip
                                                       + les memes fichiers dans paquet-pip/

Contenu, sous un dossier racine graphify-local-<version>-pip/ :
- graphify_local-<version>-py3-none-any.whl : graphify-local (absent de PyPI) ;
- requirements.txt : ce wheel + les 66 dependances, chacune a version et
  empreinte sha256 figees (copie de requirements/windows-amd64-py310.lock, ou
  la ligne graphify-local pointe sur le fichier local : pip ne le cherche donc
  jamais sur PyPI) ;
- install-pip.cmd : la commande pip a lancer (double-clic), lue dans
  paquet-pip/ (seul exemplaire du fichier).

Les dependances sont telechargees par pip depuis PyPI (ou le miroir configure
dans pip.ini) au moment de l'installation.
"""
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
version = sys.argv[1]
lock_name = sys.argv[sys.argv.index("--lock") + 1] if "--lock" in sys.argv else "windows-amd64-py310"
wheel_name = f"graphify_local-{version}-py3-none-any.whl"
wheel = ROOT / "wheelhouse" / wheel_name
lock = (ROOT / "requirements" / f"{lock_name}.lock").read_text(encoding="utf-8")

digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
requirements, n = re.subn(
    rf"^graphify-local=={re.escape(version)} \\\n    --hash=sha256:([0-9a-f]{{64}})$",
    lambda m: f"./{wheel_name} \\\n    --hash=sha256:{m.group(1)}",
    lock, flags=re.M,
)
if n != 1 or digest not in requirements:
    raise SystemExit(f"{lock_name}.lock ne reference pas {wheel_name} avec son empreinte actuelle")
requirements = requirements.replace(
    "# Genere par scripts/make-locks.py - ne pas modifier a la main.",
    "# Genere par scripts/make-pip-zip.py - ne pas modifier a la main.\n"
    "# graphify-local vient du fichier local ; les dependances viennent de PyPI\n"
    "# (ou du miroir de pip.ini), refusees si leur empreinte differe.",
)

root = f"graphify-local-{version}-pip"
archive = ROOT / f"{root}.zip"
cmd = (ROOT / "paquet-pip" / "install-pip.cmd").read_bytes()
archive.unlink(missing_ok=True)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for arc, data in ((wheel_name, wheel.read_bytes()),
                      ("requirements.txt", requirements.encode("utf-8")),
                      ("install-pip.cmd", cmd)):
        info = zipfile.ZipInfo(f"{root}/{arc}", date_time=(2026, 10, 22, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        z.writestr(info, data)
if lock_name == "windows-amd64-py310":
    folder = ROOT / "paquet-pip"
    folder.mkdir(exist_ok=True)
    for old in folder.glob("graphify_local-*.whl"):
        old.unlink()
    (folder / wheel_name).write_bytes(wheel.read_bytes())
    (folder / "requirements.txt").write_bytes(requirements.encode("utf-8"))
zdigest = hashlib.sha256(archive.read_bytes()).hexdigest()
(ROOT / f"{archive.name}.sha256").write_text(f"{zdigest}  {archive.name}\n", encoding="utf-8")
print(f"[build] archive : {archive} ({archive.stat().st_size / 1e6:.1f} Mo)\n{zdigest}  {archive.name}")
