#!/usr/bin/env bash
# Enveloppe de build_bundle.py (meme fonctionnement sous Windows : python build_bundle.py).
# Usage : ./build-bundle.sh [--fork ../fork] [--python 3.10.7] [--only windows-amd64]
set -euo pipefail
cd "$(dirname "$0")"
exec python3 build_bundle.py "$@"
