---
name: graphify
description: "A utiliser pour toute question sur le code, l'architecture, les liens entre fichiers, l'equipe, l'entreprise ou le contenu des documents du projet - en particulier quand graphify-out/ existe : interroger d'abord le graphe de connaissances (graphify query/path/explain). Sert aussi a construire ou mettre a jour ce graphe (/graphify). Version locale : aucun acces reseau, aucune IA externe."
---

# /graphify (version locale, mode Kiro)

Construit et interroge un graphe de connaissances local du projet : code (analyse
structurelle locale), documents, PDF, fichiers Office et images (lus par le
sous-agents Kiro a partir de missions generees par graphify). Sorties dans `graphify-out/` :
`graph.json`, `GRAPH_REPORT.md`, `graph.html`.

## Installation de graphify

Ce skill utilise la commande `graphify` du bundle interne **graphify**.
Si `graphify` est introuvable, dis a l'utilisateur d'installer ce bundle. N'installe
pas le paquet PyPI d'origine `graphifyy` a la place : il n'a pas les protections
anti-fuite (il peut envoyer le corpus a des IA externes).

## Usage

```
/graphify                     construire le graphe du dossier courant
/graphify <chemin>            construire le graphe d'un dossier
/graphify <chemin> --update   mise a jour incrementale (fichiers modifies seulement)
/graphify <chemin> --deep     extraction plus riche (plus d'aretes INFERRED)
/graphify <chemin> --directed graphe oriente
/graphify <chemin> --no-viz   sans graph.html
/graphify --cluster-only      recalculer les communautes du graphe existant
/graphify query "<question>"  interroger le graphe
/graphify path "A" "B"        plus court chemin entre deux concepts
/graphify explain "X"         expliquer un noeud et ses voisins
```

Si l'utilisateur demande `/graphify --help`, affiche ce bloc Usage et arrete-toi.

## Chemin rapide : le graphe existe deja

Si `graphify-out/graph.json` existe et que la demande est une question (pas une
reconstruction), va directement a la section « Interroger le graphe ».

## Construire ou mettre a jour le graphe

### Etape 1 - Preparer

```bash
graphify kiro prepare <chemin>            # premiere construction
graphify kiro prepare <chemin> --update   # mise a jour incrementale
```

(ajoute `--deep` si l'utilisateur l'a demande). Resume la sortie a
l'utilisateur en quelques lignes : nombre de fichiers par type, documents
exclus pour secret probable (avec la liste affichee), fichiers audio/video
ignores. N'affiche pas les fichiers JSON internes.

Si la commande indique « rien a faire », arrete-toi et dis-le.

### Etape 2 - Faire lire les documents par le sous-agent

Si `prepare` a liste des lots (`lot NN : .../graphify-out/kiro/chunk_NN.task.md`) :

- Lance un sous-agent par lot, tous dans le meme message pour qu'ils
  travaillent en parallele.
- Le message envoye a chaque sous-agent est :
  `Execute la mission decrite dans <chemin absolu du fichier chunk_NN.task.md>`
  La mission contient deja la liste des fichiers, le fichier JSON a ecrire et
  le format attendu.
- Le sous-agent doit pouvoir lire des fichiers et en ecrire un.

Si aucun lot n'est liste (projet sans documents, ou tout est en cache), passe
directement a l'etape 3.

### Etape 3 - Verifier

```bash
graphify kiro status
```

Si des lots sont marques `MISSING`, relance une seule fois le sous-agent pour ces lots,
puis continue (les fichiers manquants seront retentes au prochain `--update`).

### Etape 4 - Assembler le graphe

```bash
graphify kiro finalize            # options si demandees : --directed --no-viz
```

`--force` uniquement si l'utilisateur confirme avoir supprime des fichiers et
accepte un graphe plus petit. Rapporte les avertissements affiches (lots
rejetes, elements ecartes, lectures partielles).

### Etape 5 - Nommer les communautes

`finalize` affiche les communautes et leurs principaux membres. Pour chacune
(hors celles marquees `[already named]`, sauf si le contenu a clairement change),
choisis un nom de 2 a 5 mots decrivant le sujet (ex. « Facturation clients »,
« Equipe support », « Projet Atlas »). Ecris le fichier
`graphify-out/kiro/labels.json` sous la forme `{"0": "Nom", "1": "Nom"}` puis :

```bash
graphify kiro labels graphify-out/kiro/labels.json
```

Les noms contenant une commande ou une URL sont refuses par graphify.

### Etape 6 - Presenter le resultat

Lis `graphify-out/GRAPH_REPORT.md` et presente seulement les sections
« God Nodes », « Surprising Connections » et « Suggested Questions ». Indique
les fichiers produits (`graph.html`, `GRAPH_REPORT.md`, `graph.json`). Propose
ensuite d'explorer la question suggeree la plus interessante.

## Interroger le graphe

```bash
graphify query "<question>"                 # parcours en largeur, contexte large
graphify query "<question>" --dfs           # suivre un chemin precis
graphify query "<question>" --budget 3000   # limiter la taille de la reponse
graphify path "<A>" "<B>"                   # chemin entre deux concepts
graphify explain "<concept>"                # un noeud et ses voisins
graphify affected "<noeud>"                 # ce qui depend de ce noeud
graphify god-nodes                          # noeuds les plus connectes
```

Reponds uniquement a partir de ce que renvoient ces commandes et cite
`source_file` / `source_location` pour chaque fait. Code de sortie 3 : nom
ambigu (les candidats sont listes, choisis ou demande) ; 4 : aucun noeud. Voir
`references/query.md` pour les details.

## Autres commandes autorisees

```bash
graphify cluster-only <chemin>       # recalcul des communautes (noms deterministes)
graphify update <chemin>             # reconstruction du code seul (AST local)
graphify export html|obsidian|wiki|svg|graphml|callflow-html
graphify export neo4j                # fichier Cypher LOCAL uniquement (pas d'envoi)
graphify tree                        # vue arborescente HTML
graphify hook install                # hooks git : reconstruction locale du code
```

Voir `references/exports.md` et `references/hooks.md`.

## Non disponible dans cette version

graphify n'envoie rien hors de la machine. Ces fonctions de graphify d'origine
sont donc retirees et refusees par la commande : recuperation d'URL
(`graphify add`), clonage (`graphify clone`), transcription audio/video, export
Google Workspace, tableau de bord des PR, serveur MCP, envoi vers
Neo4j/FalkorDB, graphe global, appels a des IA externes. Si l'utilisateur veut
ajouter une page web ou un depot au corpus, Kiro peut le recuperer lui-meme et
deposer le fichier dans le dossier, puis lancer `/graphify --update`.

## Regles d'honnetete

- N'invente jamais une arete ; en cas de doute, AMBIGUOUS.
- Signale toujours les documents exclus et les lots rejetes.
- Montre les scores de cohesion tels quels.
- Previens avant tout export HTML d'un graphe de plus de 5 000 noeuds.
