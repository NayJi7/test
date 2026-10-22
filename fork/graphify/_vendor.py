"""graphify-local : bibliotheques JavaScript embarquees dans les pages HTML.

L'original chargeait vis-network (unpkg.com), d3 (d3js.org, sans controle
d'integrite, version flottante) et mermaid (cdn.jsdelivr.net, sans controle
d'integrite, version flottante). Ouvrir un export HTML contactait donc ces CDN,
et un CDN compromis aurait pu lire le graphe integre dans la page.

Ici le code des bibliotheques est livre dans ``graphify/vendor/`` (versions
figees, empreintes verifiees, voir vendor/SOURCES.md), verifie au chargement,
puis integre en ligne dans la page. Chaque page porte en plus une politique
CSP qui interdit au navigateur toute requete reseau (fetch, XHR, images,
polices, iframes) depuis la page.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from pathlib import Path

_VENDOR_DIR = Path(__file__).parent / "vendor"

# Empreintes sha384 attendues (identiques aux valeurs SRI de vendor/SOURCES.md).
_VENDOR_FILES = {
    "vis-network": (
        "vis-network-9.1.6.min.js",
        "Ux6phic9PEHJ38YtrijhkzyJ8yQlH8i/+buBR8s3mAZOJrP1gwyvAcIYl3GWtpX1",
    ),
    "d3": (
        "d3-7.9.0.min.js",
        "CjloA8y00+1SDAUkjs099PVfnY2KmDC2BZnws9kh8D/lX1s46w6EPhpXdqMfjK6i",
    ),
    "mermaid": (
        "mermaid-11.17.2.min.js",
        "EOXBFmc3gx5mb+vn0vPvvGqACToJD24hhacX5Yx+8NUUQrHIle/Qi5Bg9o3zKwW2",
    ),
}

# Politique de securite du contenu des pages generees : seul le code integre
# dans la page s'execute ; aucune ressource ni connexion externe n'est permise.
CSP_META = (
    '<meta http-equiv="Content-Security-Policy" content="'
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; "
    "img-src data: blob:; "
    "font-src data:; "
    "connect-src 'none'; "
    "frame-src 'none'; "
    "form-action 'none'; "
    "base-uri 'none'"
    '">'
)


class VendorIntegrityError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def _vendor_source(name: str) -> str:
    filename, expected = _VENDOR_FILES[name]
    data = (_VENDOR_DIR / filename).read_bytes()
    digest = base64.b64encode(hashlib.sha384(data).digest()).decode("ascii")
    if digest != expected:
        raise VendorIntegrityError(
            f"graphify: empreinte inattendue pour {filename} "
            f"(attendu sha384-{expected}, obtenu sha384-{digest})"
        )
    text = data.decode("utf-8")
    # Neutralise les sequences qui pourraient fermer ou perturber un <script>
    # en ligne. Elles n'apparaissent que dans des chaines/regex, ou "\!" et
    # "\/" sont equivalents a "!" et "/".
    return text.replace("<!--", "<\\!--").replace("</script", "<\\/script")


def vendor_script_tag(name: str) -> str:
    """Balise <script> contenant la bibliotheque `name` en ligne."""
    return f"<script>/* {_VENDOR_FILES[name][0]} (embarque) */\n{_vendor_source(name)}\n</script>"
