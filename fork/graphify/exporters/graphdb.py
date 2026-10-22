# graphify-local: l'envoi direct vers Neo4j / FalkorDB est supprime.
#
# L'original ouvrait une connexion reseau (bolt:// ou redis://, TLS non impose)
# vers l'URI fournie et y poussait tous les noeuds et aretes. La generation
# locale d'un fichier Cypher (`graphify export neo4j` sans --push, voir
# export.to_cypher) reste disponible : importez ce fichier vous-meme dans une
# base interne si besoin.
from __future__ import annotations

_PUSH_DISABLED = (
    "graphify: l'envoi reseau vers une base de graphes est desactive. "
    "Generez un fichier Cypher local avec `graphify export neo4j` (sans --push)."
)


def push_to_neo4j(*args, **kwargs) -> dict:
    raise RuntimeError(_PUSH_DISABLED)


def push_to_falkordb(*args, **kwargs) -> dict:
    raise RuntimeError(_PUSH_DISABLED)
