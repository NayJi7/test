# graphify - installation interne par pip (graphify-local 0.9.93.1)

Fork de `graphifyy` 0.9.93 qui **ne peut rien envoyer hors de la machine** :
aucun appel à une IA externe, aucun téléchargement, aucun serveur, et un verrou
anti-fuite actif dans chaque processus graphify. L'intelligence (lecture des
documents, nommage des communautés) est assurée par **Kiro**, à qui graphify
fournit un skill et des missions d'extraction. Kiro lui-même n'est ni bridé ni
reconfiguré.

## Contenu

| Élément | Rôle |
|---|---|
| `paquet-pip/` | **Le paquet à livrer aux postes** (≈ 2,3 Mo) : `graphify_local-0.9.93.1-py3-none-any.whl` (graphify-local, absent de PyPI), `requirements.txt` (ce fichier + les 66 dépendances, versions et empreintes sha256 figées) et `install-pip.cmd` (double-clic) |
| `requirements/windows-amd64-py310.lock` | Versions et empreintes sha256 de référence (Windows, Python 3.10) |
| `build_bundle.py`, `scripts/` | Reconstruction du paquet sur une machine connectée (voir § 6) |

Aucune des 66 dépendances n'est une bibliothèque réseau : pas de `requests`,
`httpx`, `urllib3`, `openai`, `anthropic`, `boto3`, `mcp`, `huggingface_hub`,
`yt-dlp`…

## 1. Installer (sur chaque poste Windows)

Prérequis :
- **Python 3.10 64 bits** dans le PATH (testé avec 3.10.7 ; tout 3.10.x convient), avec pip ;
- accès à PyPI, ou à un miroir d'entreprise configuré dans `pip.ini`.

Copier le dossier `paquet-pip` (ou le zip `graphify-local-0.9.93.1-pip.zip`)
sur le poste, puis **double-cliquer sur `install-pip.cmd`**. Il lance :

```
python -m pip install --require-hashes --only-binary=:all: --disable-pip-version-check --no-warn-script-location -r requirements.txt
```

puis `python -m graphify kiro verify`, qui doit afficher « verification passed ».

- graphify-local est pris dans le fichier `.whl` local, jamais sur PyPI ;
- les 66 dépendances sont téléchargées par pip, aux versions et empreintes
  sha256 figées : tout fichier différent est refusé, et rien n'est installé ;
- `--only-binary=:all:` : aucun script d'installation n'est exécuté, pip ne
  fait que copier des fichiers déjà compilés ;
- la commande `graphify` est créée dans le dossier `Scripts` de ce Python
  (affiché à la fin) : l'ajouter au PATH si `graphify` n'est pas reconnu, puis
  ouvrir un nouveau terminal.

Limites :
- graphify est installé dans le Python du poste. Un `pip install graphifyy`
  (graphify d'origine) dans ce même Python l'écraserait sans prévenir ;
  `graphify kiro verify` échoue alors. D'autres installations pip peuvent
  aussi changer les versions des dépendances ;
- PyPI (ou le miroir) voit l'adresse IP et la liste des paquets demandés ;
- si pip affiche « from versions: none », il ne joint pas son index (proxy,
  certificat, miroir incomplet) : `python -m pip config debug` et
  `python -m pip download beautifulsoup4==4.15.0 --no-deps -d %TEMP%\pip-test -v`
  indiquent la cause.

### Hooks git

`graphify hook install` dans un projet installe les hooks (post-commit,
post-checkout, post-merge, post-rewrite) et le pilote de fusion de
`graph.json`. Ils utilisent le Python dans lequel graphify est installé.

## 2. Brancher un projet sur Kiro

Dans le dossier du projet :

```bash
graphify kiro install
```

Cette commande écrit :
- `.kiro/skills/graphify/SKILL.md` et `references/` : le skill `/graphify` ;
- `.kiro/steering/graphify.md` : Kiro interroge le graphe avant de répondre aux questions sur le projet.

Elle ne touche à aucun réglage ni aucune permission de Kiro. Ces fichiers peuvent être commités dans le dépôt du projet.

## 3. Construire le graphe (dans Kiro)

Dans Kiro, tapez `/graphify` (ou `/graphify <dossier>`). Le skill enchaîne :

1. `graphify kiro prepare <dossier>` : détection des fichiers, analyse locale du
   code, exclusion des documents contenant un secret, découpage des documents
   en lots, écriture d'une mission par lot (`graphify-out/kiro/chunk_NN.task.md`) ;
2. Kiro lance un sous-agent par lot (« Exécute la mission décrite dans … ») ;
3. `graphify kiro finalize` : validation stricte des JSON écrits par les
   sous-agents, assemblage du graphe, communautés, rapport, `graph.html` ;
4. Kiro nomme les communautés puis lance `graphify kiro labels …`.

Mise à jour : `/graphify --update`. Le code seul se met aussi à jour sans Kiro :
`graphify update .` ou les hooks git (`graphify hook install`).

## 4. Interroger

Kiro le fait de lui-même grâce au fichier de steering. À la main :

```bash
graphify query "qui travaille sur la facturation ?"
graphify path "Projet Atlas" "facturer"
graphify explain "Client"
```

## 5. Vérifier à tout moment

```bash
graphify kiro verify                                   # auto-contrôle de l'installation
python3 -I tests-fuite/bench.py $(which graphify)      # banc anti-fuite complet (Linux, strace)
```

## 6. Reconstruire le paquet pip

Après une modification du code (`fork/`), sur une machine **connectée**
(Windows, Linux ou macOS, Python ≥ 3.10) :

```bash
cd bundle
python build_bundle.py                        # postes en Python 3.10.7 (défaut)
python build_bundle.py --python 3.10.7
```

Le script construit le wheel graphify-local de façon reproductible (même
source = même empreinte), télécharge les dépendances Windows dans
`wheelhouse/` (cache local, jamais livré) pour en calculer les empreintes,
vérifie que toutes les dépendances requises sont présentes, régénère le
`.lock` en affichant les différences (« aucune » = fichiers identiques), puis
met à jour `paquet-pip/` et produit `graphify-local-<version>-pip.zip`.

Les versions restent figées par le `.lock` existant. Pour changer
volontairement une dépendance, supprimez le `.lock`, relancez, relisez le
diff, puis relancez le banc anti-fuite.

## Documents qui contiennent un secret

`graphify kiro prepare` liste les documents écartés (règle et numéro de ligne,
jamais la valeur). Ils n'entrent pas dans le graphe. Si c'est un faux positif,
un humain peut approuver **cette version exacte** du fichier :

```bash
echo "$(sha256sum docs/fichier.md | cut -d' ' -f1)  docs/fichier.md" >> .graphify-secrets-allow
```

Toute modification ultérieure du fichier invalide l'approbation.
