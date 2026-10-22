"""graphify-local : adaptation de la suite de tests d'origine.

1. Fichiers de test qui importent un module ou une ressource supprimes du fork :
   ils ne sont pas collectes (liste COLLECT_IGNORE ci-dessous, avec la raison).
2. Tests qui passaient sur graphify d'origine et qui portent sur une fonction
   retiree ou volontairement modifiee : marques "skip" avec la raison exacte,
   lue dans tests/local_skips.json (genere en comparant les deux suites).

Aucun test d'une fonction conservee n'est ignore sans raison documentee ;
voir docs/MODIFICATIONS.md, section "Tests".
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_HERE = Path(__file__).parent

# Fichier -> raison (module / ressource supprime(e) dans graphify-local)
COLLECT_IGNORE = {
    "test_backend_extras.py": "graphify.llm : indications d'installation des backends IA retirees",
    "test_claude_md.py": "integration Claude Code (always_on/claude-md.md) retiree",
    "test_install_strings.py": "skills/always-on des autres assistants retires",
    "test_hyperedge_member_shapes.py": "graphify.llm._sanitize_fragment (reponses LLM) retire",
    "test_semantic_fragment_sanitize.py": "graphify.llm._parse_llm_json/_sanitize_fragment retires",
    "test_injection_sentinel_coverage.py": "graphify.llm (enveloppe <untrusted_source> des appels API) retire",
    "test_ingest_url_type.py": "graphify add <url> (ingest) retire",
    "test_oversized_document_slicing.py": "graphify.llm._read_files (envoi de fichiers a une API) retire",
    "test_pdf_slicing.py": "graphify.llm._read_files/_file_to_text retires",
    "test_pdf_token_estimate.py": "graphify.llm (estimation de jetons pour API) retire",
    "test_pg_introspect.py": "graphify.pg_introspect (connexion PostgreSQL) retire",
    "test_prs.py": "graphify.prs (GitHub via gh) retire",
    "test_transcribe.py": "graphify.transcribe (yt-dlp / Whisper) retire",
}
collect_ignore = list(COLLECT_IGNORE)

_SKIPS = json.loads((_HERE / "local_skips.json").read_text(encoding="utf-8"))


def pytest_collection_modifyitems(config, items):
    reasons = _SKIPS["reasons"]
    skips = _SKIPS["skips"]
    for item in items:
        key = item.nodeid
        if key in skips:
            item.add_marker(pytest.mark.skip(reason="graphify-local : " + reasons[skips[key]]))
