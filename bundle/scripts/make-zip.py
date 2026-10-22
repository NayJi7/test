"""Assemble le zip d'installation interne.

    python3 -I scripts/make-zip.py <version>                         -> graphify-local-<version>.zip (tous systemes)
    python3 -I scripts/make-zip.py <version> --only windows-amd64-py310 -> graphify-local-<version>-windows-amd64-py310.zip

Contenu, sous un dossier racine graphify-local/ : installer.py,
install-windows.cmd, install-offline.sh, README.md, requirements/ et
wheelhouse/ (du ou des systemes choisis), outils/banc-anti-fuite.py.
"""
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
version = sys.argv[1]
only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
archive = ROOT / (f"graphify-local-{version}-{only}.zip" if only else f"graphify-local-{version}.zip")

entries: list[tuple[Path, str]] = []
for item in ("installer.py", "install-windows.cmd", "install-offline.sh", "README.md"):
    entries.append((ROOT / item, item))
for lock in sorted((ROOT / "requirements").glob("*.lock")):
    if only is None or lock.stem == only:
        entries.append((lock, f"requirements/{lock.name}"))
wh = ROOT / "wheelhouse"
for f in sorted(wh.glob("*.whl")):
    entries.append((f, f"wheelhouse/{f.name}"))
for d in sorted(p for p in wh.iterdir() if p.is_dir()):
    if only is None or d.name == only:
        for f in sorted(d.glob("*.whl")):
            entries.append((f, f"wheelhouse/{d.name}/{f.name}"))
bench = ROOT.parent / "tests-fuite" / "bench.py"
if bench.is_file():
    entries.append((bench, "outils/banc-anti-fuite.py"))

archive.unlink(missing_ok=True)
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
    for src, arc in entries:
        info = zipfile.ZipInfo(f"graphify-local/{arc}", date_time=(2026, 10, 22, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o755 if src.suffix in (".sh", ".py") else 0o644) << 16
        z.writestr(info, src.read_bytes())
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
(ROOT / f"{archive.name}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
print(f"[build] archive : {archive} ({archive.stat().st_size / 1e6:.0f} Mo)\n{digest}  {archive.name}")
