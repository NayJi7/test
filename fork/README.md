# graphify (version locale)

Graphe de connaissances local d'un projet (code, documents, PDF, Office,
images), pour l'assistant IA de votre choix (Kiro, Claude Code, Codex,
Copilot…). Cette version ne contacte jamais le réseau et n'appelle aucune IA
externe : la lecture des documents et le nommage des communautés sont faits
par l'assistant qui exécute le skill `/graphify`, installé par
`graphify <assistant> install` (par exemple `graphify kiro install`).

- Installation : paquet pip interne (voir `bundle/README.md`).
- Utilisation : `/graphify` dans l'assistant, ou `graphify query "<question>"`.
- Auto-contrôle : `graphify verify`.

Basé sur graphify 0.9.93 (Apache-2.0 / MIT, voir LICENSE, LICENSE-MIT,
NOTICE). Détail des modifications : `docs/MODIFICATIONS.md`.
