# Reference graphify : exports

Tous les exports sont des fichiers LOCAUX ecrits dans `graphify-out/`. Aucun
export n'envoie de donnees vers un service ou une base distante.

```bash
graphify export html            # graph.html interactif (bibliotheque embarquee, aucune requete reseau)
graphify export obsidian        # coffre Obsidian dans graphify-out/obsidian (option --dir <chemin>)
graphify export wiki            # wiki markdown (index + un article par communaute)
graphify export svg             # graph.svg
graphify export graphml         # graph.graphml (Gephi, yEd)
graphify export callflow-html   # diagrammes d'architecture Mermaid (bibliotheque embarquee)
graphify export neo4j           # graphify-out/cypher.txt, a importer soi-meme dans une base INTERNE
graphify tree                   # GRAPH_TREE.html, vue arborescente (d3 embarque)
```

Non disponible : `--push` vers Neo4j/FalkorDB, serveur MCP (`--mcp`). Ces
options sont refusees par graphify.

Les pages HTML generees portent une politique de securite (CSP) qui interdit
au navigateur tout chargement externe : elles s'ouvrent hors ligne.

Ne partagez ces fichiers que par les canaux internes autorises pour le niveau
de confidentialite du graphe : ils contiennent des noms et des resumes issus
du corpus.
