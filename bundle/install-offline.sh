#!/usr/bin/env bash
# graphify - installation HORS LIGNE (Linux x86_64 / macOS Apple Silicon).
# Usage : bash install-offline.sh
# Cree, a cote de ce fichier, le dossier autonome graphify-local/
# (commande graphify + lib/). Toute la logique est dans installer.py.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi
if [ -z "$PY" ]; then echo "Python 3.10 est requis (PYTHON=/chemin/vers/python3.10)." >&2; exit 1; fi
exec "$PY" -I "$HERE/installer.py"
