# graphify-local: integration Google Workspace supprimee.
#
# L'original exportait les raccourcis .gdoc/.gsheet/.gslides en lancant le CLI
# `gws` (Google Drive). Ici les raccourcis sont simplement ignores : exportez
# les documents manuellement (docx/xlsx/pdf) puis deposez-les dans le corpus.
from __future__ import annotations

from pathlib import Path

GOOGLE_WORKSPACE_EXTENSIONS = {".gdoc", ".gsheet", ".gslides"}


def google_workspace_enabled(value: str | None = None) -> bool:
    """Toujours faux : l'export Google Workspace est desactive."""
    return False


def convert_google_workspace_file(path: Path, out_dir: Path, *args, **kwargs) -> Path | None:
    """Aucune conversion (aucun appel a `gws` / Google Drive)."""
    return None
