# Reference graphify : hooks git

```bash
graphify hook install     # installer
graphify hook uninstall   # retirer
graphify hook status      # verifier
```

Apres chaque commit, checkout, merge ou rebase, le hook reconstruit localement le
graphe du CODE modifie (analyse structurelle, sans IA ni reseau) et met a jour
`graph.json` et `GRAPH_REPORT.md`. Les documents ne sont pas retraites par le
hook : lancez `/graphify --update` dans Kiro pour eux.

Le hook ajoute aussi un pilote de fusion pour `graph.json` (ligne dans
`.gitattributes`). Rappel : `graphify-out/` ne doit pas etre commite dans un
depot heberge hors de l'entreprise.

Les integrations pour d'autres assistants (CLAUDE.md, AGENTS.md, Cursor...)
n'existent pas dans cette version de graphify.
