---
inclusion: always
---

graphify : un graphe de connaissances du projet (code, documents, equipe, decisions) se trouve dans `graphify-out/`. Pour toute question sur le code, l'architecture, les dependances, l'equipe ou les documents, quand `graphify-out/graph.json` existe, lance d'abord `graphify query "<question>"` (ou `graphify path "<A>" "<B>"` / `graphify explain "<concept>"`). Ces commandes renvoient un sous-graphe cible, bien plus petit que `GRAPH_REPORT.md` ou qu'une recherche brute. Ne lis `GRAPH_REPORT.md` que pour une vue d'ensemble de l'architecture.

Pour construire ou mettre a jour le graphe, suis le skill `/graphify` (commandes `graphify kiro ...`).
