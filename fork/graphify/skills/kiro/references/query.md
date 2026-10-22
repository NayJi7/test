# Reference graphify : interroger le graphe

Toutes ces commandes lisent `graphify-out/graph.json` localement. Elles
n'ecrivent rien (sauf `save-result`) et n'accedent pas au reseau.

## query

```bash
graphify query "<question>"                    # largeur d'abord (contexte large)
graphify query "<question>" --dfs              # profondeur d'abord (suivre un chemin)
graphify query "<question>" --budget 3000      # taille max de la reponse (jetons, defaut 2000)
graphify query "<question>" --seed "<noeud>"   # partir d'un noeud precis (repetable)
graphify query "<question>" --context <rel>    # filtrer par type de relation (repetable)
```

Avant d'interroger, reformule la question avec le vocabulaire du graphe : si la
premiere requete renvoie peu de choses, utilise `graphify god-nodes` pour voir
les termes centraux, puis relance avec ces termes. N'ajoute que des termes
presents dans le graphe.

## path et explain

```bash
graphify path "<A>" "<B>"             # plus court chemin (oriente par defaut ; --undirected)
graphify explain "<concept>"          # le noeud et ses 20 voisins principaux (--all pour tout)
graphify affected "<noeud>"           # impact inverse (--depth N, --relation R)
```

Codes de sortie : 0 reponse, 3 nom ambigu (candidats listes), 4 aucun noeud.

## Repondre

Reponds uniquement avec ce que renvoient les commandes. Cite `source_file` et
`source_location` pour chaque fait. Si le graphe ne contient pas l'information,
dis-le plutot que de deviner.

## Memoire (optionnel)

Si l'utilisateur le demande, enregistre une reponse utile pour les sessions
futures :

```bash
graphify save-result --question "<question>" --answer "<reponse>" --type query --nodes "<noeud1>" "<noeud2>" --outcome useful
```

Ces fichiers (`graphify-out/memory/`) appartiennent au meme niveau de
confidentialite que le graphe.
