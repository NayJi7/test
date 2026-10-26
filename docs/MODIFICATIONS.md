# graphify-local 0.9.93.1 - modifications détaillées de A à Z

> **Nom** : `graphify-local` est un nom **interne**, utilisé pour le dossier,
> l'archive zip et le nom de paquet pip. Pour les utilisateurs, l'outil
> s'appelle simplement **graphify** : la commande, les messages, le skill
> Kiro `/graphify` et `graphify --version`. Le nom de paquet pip reste
> différent de `graphifyy` pour qu'un `pip install -U graphifyy` tapé par
> erreur ne puisse pas remplacer cette version par celle d'origine. Rien n'est
> publié sur PyPI : la diffusion se fait par le zip interne.

Fork de **graphifyy 0.9.93** (PyPI), licence Apache-2.0 / MIT conservée
(fichiers `LICENSE`, `LICENSE-MIT`, `NOTICE` inchangés).

**Objectif unique : graphify ne doit pouvoir envoyer aucune donnée hors de la
machine.** Kiro n'est pas modifié : aucune permission, aucun réglage, aucune
restriction. On lui ajoute seulement un skill et un fichier de steering, comme
le faisait graphify d'origine.

Le diff complet est dans `docs/PATCH-COMPLET.diff`, sans les bibliothèques
JavaScript minifiées : ce sont des copies à l'identique des paquets npm, dont
les empreintes sont listées dans `fork/graphify/vendor/SOURCES.md`.

---

## 0. Point de départ vérifié

- Sources : sdist `graphifyy-0.9.93.tar.gz` de PyPI. J'ai vérifié que son
  dossier `graphify/` est **identique octet par octet** au wheel publié.
- Le paquet d'origine compte environ 57 000 lignes de Python. Les algorithmes
  d'analyse du code (tree-sitter), de construction du graphe, de communautés
  (Leiden), de requête et d'export ne sont pas modifiés. Seuls les points de
  sortie de données et l'intégration Kiro le sont.

## 1. Plus aucun appel à une IA externe

### `graphify/llm.py` : 3 855 → 263 lignes

**Avant** :
- 9 fournisseurs : Gemini, Kimi, Anthropic, OpenAI, DeepSeek, Azure, Bedrock,
  Ollama, CLI `claude` ;
- choix **automatique** du fournisseur selon les variables d'environnement
  présentes (`GOOGLE_API_KEY`, `OPENAI_API_KEY`… et même `AWS_REGION` seul,
  qui sélectionnait Bedrock) ;
- envoi du texte intégral des documents ;
- repli silencieux sur le CLI `claude` s'il était installé.

**Après** : le module n'importe plus rien de réseau et ne lance aucun
programme. Il ne conserve que du code local pur :
- le texte du prompt d'extraction (`_EXTRACTION_SYSTEM`, `_extraction_system`),
  utilisé pour attribuer les entrées du cache ;
- les marqueurs de lecture partielle (`_mark_partial`, `_partial_source_files`,
  `_strip_partial_markers`, …) ;
- le tampon d'origine sémantique (`_stamp_semantic_origin`) ;
- `_placeholder_community_labels`.

Les fonctions publiques restantes sont des bouchons :

| Fonction | Comportement |
|---|---|
| `BACKENDS` | `{}` (aucun fournisseur) |
| `detect_backend()`, `detect_backend_with_source()` | `None`, quelles que soient les variables d'environnement |
| `backend_disabled_by_env()` | toujours `True` |
| `_claude_cli_available()` | toujours `False` (repli `claude -p` supprimé) |
| `extract_corpus_parallel`, `extract_files_direct`, `_call_llm`, `label_communities`, `_validate_ollama_base_url` | lèvent `LLMDisabledError` |
| `generate_community_labels` | renvoie des libellés « Community N » ; l'appelant garde alors les libellés déterministes (nœud central de chaque communauté) |

### `graphify/dedup.py`

`_llm_tiebreak` (option `--dedup-llm`, qui envoyait des paires de libellés à
une IA) est réduit à un message et un `return`. Les paires ambiguës restent
séparées, comme sans l'option.

### `graphify/cli.py` : commande `extract`

Avec des documents dans le corpus, elle indexe le code seul et affiche « aucune
IA dans graphify ; … lancez /graphify dans Kiro ». Elle ne cherche plus de clé
d'API.

## 2. Plus aucun accès réseau

### Modules supprimés

| Fichier | Ce qu'il faisait |
|---|---|
| `prs.py` | tableau de bord des PR via `gh` (GitHub), plus un tri par IA |
| `transcribe.py` | `yt-dlp` (téléchargement de vidéos) et faster-whisper (modèle téléchargé depuis Hugging Face) |
| `pg_introspect.py` | connexion à une base PostgreSQL |
| `global_graph.py` | copie de chaque graphe dans `~/.graphify/global-graph.json` |

### Modules réduits

- **`security.py`** (493 → 239 lignes) : suppression de `validate_url`,
  `safe_fetch`, `safe_fetch_text`, des connexions HTTP(S) « anti-SSRF » et de
  leurs imports (`urllib`, `http.client`, `socket`, `ipaddress`). Restent :
  `validate_graph_path`, `check_graph_file_size_cap`, `sanitize_label`,
  `sanitize_metadata`, `redact_secrets`.
- **`ingest.py`** (383 → 130 lignes) : suppression de `ingest(url)` (commande
  `add` : pages web, tweets, arXiv, PDF, vidéos). Reste l'enregistrement local
  des questions/réponses (`save-result`).
- **`google_workspace.py`** (237 → 20 lignes) : bouchon. Les raccourcis
  `.gdoc/.gsheet/.gslides` sont ignorés et le CLI `gws` n'est plus lancé.
  `detect.py` garde son interface.
- **`exporters/graphdb.py`** (210 → 21 lignes) : `push_to_neo4j` et
  `push_to_falkordb` lèvent une erreur. La génération locale d'un fichier
  Cypher (`graphify export neo4j` sans `--push`) reste possible.
- **`serve.py`** (3 089 → 2 183 lignes) : suppression du serveur MCP (stdio et
  HTTP/SSE, sans authentification par défaut) et de ses outils PR (`gh`). Les
  fonctions de requête locales, utilisées par `query`, `path` et `explain`,
  sont conservées. `_main` affiche « serveur MCP désactivé » et sort avec le
  code 2.

### `cli.py` : contrôle central `_local_gate`

Appelé au début de `dispatch_command`, il refuse **avant toute exécution**
(message `graphify: fonction desactivee …`, code de sortie 2) :

- les commandes `provider`, `prs`, `add`, `clone`, `global`, `label` (le
  nommage passe par `graphify kiro labels`) ;
- les options `--backend`, `--model`, `--dedup-llm`, `--postgres`,
  `--google-workspace`, `--global`, `--push`, `--mcp`, `--neo4j-push`,
  `--falkordb-push` ;
- une URL (`http://`, `https://`, `git@`, `ssh://`) passée comme chemin aux
  commandes `extract`, `update`, `watch`, `cluster-only`, `label`,
  `merge-graphs`, `check-update`, `tree`.

Le code des branches `provider`, `prs`, `add`, `clone` et `global`, ainsi que
`_clone_repo`, est remplacé par ce refus.

## 3. Verrou anti-fuite dans le processus (`_egress_guard.py`, nouveau)

Installé en tout premier par `graphify/__init__.py` : tout import de graphify
l'active pour le reste du processus. C'est le cas de la CLI, des hooks git, des
processus de travail et de `python -c "from graphify…"`. Il repose sur un
*audit hook* Python (`sys.addaudithook`, PEP 578), **qui ne peut pas être
retiré** une fois installé.

**Refusé** (exception `EgressBlocked`) :
- la création de toute socket qui n'est pas une socket Unix locale : ni TCP ni
  UDP, ni vers Internet, ni vers le réseau interne, ni vers 127.0.0.1 (un proxy
  local pourrait relayer vers l'extérieur) ;
- `connect`, `bind`, `sendto` et `sendmsg` sur une socket non Unix ;
- toute résolution DNS (`getaddrinfo`, `gethostbyname`…), car le DNS peut
  servir à exfiltrer ;
- `urllib.Request`, `webbrowser.open`, `os.system`, `os.startfile`, `pty.spawn` ;
- le lancement de tout programme externe, sauf :
  - `git` limité à `ls-files`, `config` et `rev-parse` (pas de fetch, clone ni
    push) ;
  - `cpp` (préprocesseur utilisé pour le Fortran, sans accès fichier) ;
  - l'interpréteur Python courant, uniquement pour `-m graphify`, pour le code
    des hooks (`-c "from graphify…"`) et pour les commandes exactes de
    `multiprocessing` (spawn, forkserver, resource_tracker). Ces processus
    enfants réimportent graphify et ont donc eux aussi le verrou.

**Aucune variable d'environnement ne permet de le désactiver.**

**Particularités Windows** (corrigées après un essai réel sous Wine avec le
Python Windows officiel 3.10.7) :
- sous Windows, `subprocess.Popen` transmet à l'audit une **seule chaîne** de
  commande et non une liste. Le verrou la découpe désormais selon les règles
  de Windows (`_split_windows_cmdline`, inverse exact de
  `subprocess.list2cmdline`). Sans cela, `git -C <dossier> config …` était vu
  comme un programme inconnu et **tous les appels git de graphify étaient
  bloqués sous Windows** (dont l'enregistrement du pilote de fusion par
  `graphify hook install`) ;
- Python 3.10 transmet à l'événement `_winapi.CreateProcess` une ligne de
  commande illisible (bogue CPython, corrigé en 3.11). Le verrou lit donc la
  vraie ligne de commande dans le code appelant : `subprocess.Popen` (elle doit
  être identique à celle qui vient d'être contrôlée) ou `multiprocessing`
  (processus de travail de ce même Python uniquement). Tout autre appel est
  refusé. L'ancienne règle (« contient `--multiprocessing-fork` ») est
  supprimée, car elle aurait accepté n'importe quel programme portant ce mot.

Vérifié par les tests :
- TCP vers Internet ou localhost, DNS, urllib, `curl`, `bash`, `os.system`,
  `git fetch`/`push`/`clone`, `python -c` arbitraire et `pip install` sont
  bloqués ;
- `git rev-parse`, les sockets Unix et le multiprocessing (y compris en mode
  spawn) fonctionnent.

## 4. Exports HTML autonomes

- **`vendor/`** (nouveau) : `vis-network-9.1.6.min.js`, `d3-7.9.0.min.js`,
  `mermaid-11.17.2.min.js`, avec leurs licences (MIT / Apache-2.0 / ISC) et
  `SOURCES.md`.
  - Les fichiers ont été téléchargés depuis le registre npm, et l'empreinte
    sha512 de chaque tarball a été vérifiée contre celle publiée par npm.
  - L'empreinte sha384 de vis-network est **identique** à l'attribut
    `integrity` du code graphify d'origine.
- **`_vendor.py`** (nouveau) :
  - vérifie l'empreinte sha384 de chaque bibliothèque à chaque chargement ;
  - l'intègre directement dans la page ;
  - fournit une politique CSP (`default-src 'none'; connect-src 'none'; …`) qui
    interdit au navigateur toute requête externe depuis la page.
- **`exporters/html.py`**, **`tree_html.py`**, **`callflow_html.py`** :
  - les balises `<script src="https://unpkg.com/…">`, `https://d3js.org/…`
    (sans contrôle d'intégrité, version flottante) et
    `https://cdn.jsdelivr.net/npm/mermaid@11/…` (sans contrôle, version
    flottante) sont remplacées par le code embarqué ;
  - la CSP est ajoutée en tête de chaque page.
- **Vérifié dans Chromium** (Playwright), pour les 3 types de pages :
  0 requête externe, 0 violation CSP, 0 erreur JavaScript. Le graphe s'affiche
  (canvas vis-network), l'arbre aussi (SVG d3), et les 3 diagrammes mermaid
  sont rendus.

## 5. Secrets dans le contenu des documents

- **`secret_scan.py`** (nouveau) :
  - lit le texte des documents et des PDF ;
  - cherche des clés privées, des clés AWS, des jetons GitHub, GitLab, Slack et
    Stripe, des clés d'API d'IA, des clés Google et Azure, des JWT, des jetons
    Bearer et des URL contenant des identifiants ;
  - cherche aussi les affectations du type `password=`, `token:` ou
    `mot de passe :` suivies d'une valeur réelle (les espaces réservés comme
    `<…>`, `${…}` ou `changeme` sont ignorés).
- **`detect.py`** : après la classification, chaque document ou PDF suspect est
  **retiré du corpus**, ajouté à `skipped_sensitive` et décrit dans
  `secret_findings` (fichier, règle, ligne ; jamais la valeur). La détection
  incrémentale (`--update`) passe par le même code.
- **Approbation humaine** : une ligne `<sha256>  <chemin>` dans
  `.graphify-secrets-allow`. Elle porte sur une version précise du fichier :
  toute modification l'invalide.
- Le filtre d'origine par nom de fichier (`.env`, `*.pem`, `id_rsa`…) est
  conservé.

## 6. Pipeline de construction piloté par Kiro (`kiro_pipeline.py`, nouveau)

Le skill d'origine faisait exécuter à l'agent une quinzaine de blocs
`python -c "…"` modifiables. Ils sont remplacés par des commandes fixes :

| Commande | Rôle |
|---|---|
| `graphify kiro prepare [chemin] [--update] [--deep]` | détection (avec scan de secrets), analyse AST locale du code, cache sémantique, conversion locale des PDF en texte, lots d'au plus 20 fichiers / 6 000 lignes (gros fichiers et images seuls), **un fichier de mission par lot** (`graphify-out/kiro/chunk_NN.task.md`) |
| `graphify kiro status` | lots écrits / manquants |
| `graphify kiro finalize [--directed] [--no-viz] [--force]` | validation des JSON des sous-agents, cache, fusion code + documents, mise à jour incrémentale (`build_merge`), contrôle de santé, graphe, communautés, rapport, manifeste, `graph.html`, liste des communautés à nommer |
| `graphify kiro labels fichier.json` | applique les noms choisis par Kiro, régénère rapport, `graph.json` et HTML ; les noms sont réappliqués aux mises à jour suivantes si la communauté garde le même nœud central |
| `graphify kiro verify` | auto-contrôle de l'installation (15 contrôles) |

**Validation stricte d'un lot** (graphify protège ses propres données) :
- schéma déjà validé par graphify, plus les règles suivantes ;
- clés inconnues retirées ;
- identifiants vérifiés par une expression régulière ;
- `source_file` obligatoirement un fichier **du lot** ;
- libellés nettoyés (caractères de contrôle) et limités à 200 caractères ;
- relations de la forme `[a-z_]` ;
- confiance et score bornés ;
- au plus 3 000 nœuds, 10 000 arêtes et 10 hyperarêtes par lot ;
- tout élément dont le texte ressemble à une commande ou à une instruction
  (`curl …`, `ignore previous instructions`, `<script`, …) est écarté et
  signalé ;
- une lecture incomplète (champ `coverage` inférieur au nombre de lignes) fait
  retenter le fichier au prochain `--update`.

## 7. Skill et steering Kiro

- **`skill-kiro.md`** (793 → 158 lignes), réécrit en français :
  - toutes les étapes passent par `graphify kiro …` ;
  - **retirés** : l'installation et la mise à jour automatiques depuis PyPI
    (`uv tool install --upgrade graphifyy`, `pip install … --break-system-packages`),
    l'utilisation automatique de Gemini, les blocs `python -c`, le clonage
    GitHub, `add <url>`, la transcription, les envois Neo4j/FalkorDB, MCP et le
    lien de sponsoring ;
  - **aucune règle ne limite Kiro**. Le skill indique seulement d'utiliser le
    bundle interne plutôt que `graphifyy` de PyPI, qui n'a pas les protections.
- **`always_on/kiro-steering.md`** : traduit, même rôle (interroger le graphe
  d'abord).
- **`skills/kiro/references/`** :
  - `extraction-spec.md` réécrit : règles du JSON, pas de secret recopié,
    libellés courts ;
  - `query.md`, `exports.md` et `hooks.md` réécrits ;
  - `add-watch.md`, `github-and-merge.md`, `transcribe.md` et `update.md`
    supprimés.
- **Retiré à votre demande**, pour ne pas toucher à Kiro : une politique
  `managed-settings.json` et un sous-agent restreint `graphify-extractor` que
  j'avais préparés.

## 8. Intégration et nettoyage

- **`__main__.py`** :
  - routage de `graphify kiro prepare|status|finalize|labels|verify` ;
  - les intégrations des autres assistants (claude, codex, gemini, cursor…)
    sont refusées ;
  - `graphify install` n'est accepté qu'avec `--platform kiro` ;
  - plus de réécriture automatique des skills installés ;
  - avertissements de version limités au skill Kiro.
- **`install.py`** : messages traduits, publicités app.graphify.com retirées.
  `graphify kiro install` écrit uniquement le skill, ses références et le
  steering.
- **`hooks.py`** :
  - suppression de la sonde qui exécutait l'interpréteur indiqué dans
    `graphify-out/.graphify_python` (fichier commitable par un tiers). Seuls
    l'interpréteur figé à l'installation ou le lanceur du PATH sont utilisés ;
  - **prise en charge du dossier portable** (voir § 9) : graphify n'y est pas
    dans le site-packages du Python. Quand `graphify hook install` est lancé
    depuis ce dossier (reconnu à son `graphify-local.json`), les hooks
    reçoivent le chemin de `graphify-local/lib` (`_GFY_LIB`) et l'exportent
    dans `PYTHONPATH`. Si le dossier a été déplacé depuis, ils le retrouvent à
    côté du `graphify` du PATH. Le pilote de fusion de `graph.json` appelle le
    `graphify.exe` du dossier. `graphify hook status` ignore cette valeur
    figée, comme celle de l'interpréteur.
- **Aide (`graphify --help`)** : les commandes et options refusées n'y
  figurent plus (clone, add, label, prs, provider, global, intégrations des
  autres assistants, `--backend`, `--model`, `--postgres`, `--google-workspace`,
  `--global`, `--push`, options propres aux appels LLM). `export neo4j` et
  `export falkordb` y sont décrits comme écrivant seulement un fichier Cypher.
- **Langue** : l'aide et tous les messages de la ligne de commande (fonctions
  désactivées, verrou anti-fuite, `graphify kiro …`) sont en anglais, comme
  graphify d'origine. Restent en français : le skill, le steering et les
  références Kiro, les missions des sous-agents (`chunk_NN.task.md`),
  l'installeur, les `.cmd`/`.sh`, les README et cette documentation.
- **Messages** : retrait de « Tip: set GEMINI_API_KEY… » après
  `graphify update`, et des renvois à `graphify label` (refusé dans ce fork),
  remplacés par `/graphify --update` dans Kiro.
- **`cli.py`** : `_print_cloud_cta` (publicité Graphify Cloud) neutralisé.
- **Nom de distribution** `graphify-local` (interne) : lecture de version
  (`__main__.py`, `install.py`, `export.py`, `cache.py`). Messages d'aide
  (`extract.py`, `detect.py`, `manifest_ingest.py`) qui renvoient au bundle
  interne au lieu de `pip install graphifyy[...]`.
- **`README.md`** du fork remplacé par une courte présentation (l'original
  décrivait l'installation depuis PyPI et le service hébergé). `PKG-INFO`
  (métadonnées générées du sdist d'origine) retiré.
- **Fichiers supprimés** :
  - les skills des 15 autres assistants (`skill.md`, `skill-codex.md`, …,
    `command-kilo.md`) ;
  - `skills/<autres>/`, les autres `always_on/*.md` et `pi/`.
- **`pyproject.toml`** :
  - nom `graphify-local`, version `0.9.93.1` ;
  - options conservées : pdf, office, leiden, watch, svg, sql, terraform,
    ocaml, pascal, commonlisp, dm, robot, solidity, vbnet, r, erlang, chinese,
    plus un méta-groupe `local` ;
  - options retirées : mcp, neo4j, falkordb, google, postgres, video, kimi,
    ollama, bedrock, anthropic, gemini, openai, all ;
  - point d'entrée `graphify-mcp` supprimé ;
  - fichiers embarqués : skill Kiro, `vendor/`.

## 9. Bundle (dossier `bundle/`) - cible Python 3.10 (testé avec 3.10.7)

> **État actuel : seule l'installation par pip est livrée** (`bundle/paquet-pip/` :
> wheel graphify-local + `requirements.txt` à versions et empreintes figées +
> `install-pip.cmd`). L'installation hors ligne (paquets dans `wheelhouse/`,
> `installer.py`, dossier portable avec `graphify.exe`, `install-windows.cmd`,
> `install-offline.sh`, `launcher/`) a été **retirée du dépôt**, ainsi que les
> verrous Linux et macOS. Les paragraphes ci-dessous qui la décrivent sont
> conservés comme historique des essais. `build_bundle.py` ne produit plus
> que le paquet pip Windows ; `wheelhouse/` n'y est qu'un cache local. La prise
> en charge du dossier portable reste dans `hooks.py` (inactive sans le
> fichier `graphify-local.json` créé par l'ancien installeur).
> `build_bundle.py` normalise les droits des fichiers du fork (644, ou 755 pour
> un exécutable) avant de construire le wheel : vérifié depuis une copie propre
> du dépôt, la reconstruction redonne exactement le même wheel, le même
> `requirements.txt` et le même zip.

- **67 paquets par plateforme** (Linux x86_64, Windows x64, macOS arm64), tous
  précompilés pour CPython 3.10. **Aucune bibliothèque réseau parmi eux.**
  Versions adaptées à 3.10 : numpy 2.2.6, scipy 1.15.3, networkx 3.4.2,
  matplotlib 3.10.9…
- **Compatibilité 3.10** dans `pyproject.toml` :
  - les options `leiden` et `chinese` utilisent les mêmes paquets précompilés
    pour toutes les versions de Python (`graspologic-native`, `jieba-py`) ;
  - cela évite, sous 3.10, le gros paquet `graspologic` et ses nombreuses
    dépendances, ainsi que l'ancien `jieba`, distribué uniquement en sources ;
  - `cluster.py` utilise déjà `graspologic_native` en priorité.
- **`scripts/complete-wheelhouse.py`** (nouveau) : `pip download` évalue les
  conditions des dépendances (`python_version < "3.11"`,
  `sys_platform == "win32"`…) avec la machine qui construit, pas avec la cible.
  Le script relit les dépendances de chaque paquet, évalue ces conditions pour
  la cible exacte (Python 3.10.7 + système) et télécharge ce qui manque. Il a
  ainsi ajouté `tomli`, requis seulement sous Python < 3.11, qui manquait.
- `requirements/<plateforme>-py310.lock` : version et sha256 de chaque fichier.
- Wheel du fork **reproductible** (`SOURCE_DATE_EPOCH` fixe) : même source,
  même empreinte.
- **Installeur : une seule méthode, un dossier portable** :
  - double-clic sur `install-windows.cmd` (Linux/macOS : `install-offline.sh`) ;
    il prend le Python 3.10 du PATH (sinon `py -3.10`) et lance `installer.py`
    (bibliothèque standard uniquement) ;
  - `installer.py` crée **à côté de lui** le dossier `graphify-local/` :
    `graphify.exe` (Linux/macOS : `graphify`), `lib/`, `graphify-local.json`,
    `README.txt`. Il ne modifie ni le PATH, ni le Python du poste, ni aucun
    autre dossier. Relancé, il remplace le dossier qu'il a créé (et refuse de
    toucher à un dossier `graphify-local` qu'il n'a pas créé) ;
  - **pip n'est pas utilisé** : chaque wheel est contrôlé (sha256 du `.lock`,
    aucun paquet absent, en trop ou d'une autre version), puis décompressé dans
    `lib/` comme le ferait pip (chemins `..` ou absolus refusés, collisions
    refusées), puis les modules sont précompilés ;
  - `graphify.exe` est **le lanceur standard que pip utilise** pour ses
    commandes (`t64.exe` de distlib 0.4.0, fourni dans `launcher/` avec sa
    licence ; empreinte vérifiée par l'installeur), suivi d'une ligne
    `#!"<python.exe>" -I` et d'une petite archive contenant `__main__.py`. Le
    Python est celui qui a lancé l'installeur, **en chemin absolu** : un
    `python.exe` placé dans le dossier courant (un projet cloné, par exemple)
    n'est jamais exécuté. `-I` ignore `PYTHONPATH`, `PYTHONHOME` et le site
    utilisateur. `__main__.py` retrouve `lib/` à côté du lanceur, ce qui permet
    de déplacer le dossier ;
  - limite Windows de 260 caractères par chemin : l'installeur calcule la
    longueur maximale du chemin du dossier (≈ 140 caractères), refuse de
    s'installer au-delà (sauf chemins longs activés), et l'indique dans
    `README.txt` ;
  - le zip a pour dossier racine `graphify-local-<version>-installeur/`, pour
    ne pas le confondre avec le dossier `graphify-local/` créé ;
  - remplace les essais précédents (venv dans `%LOCALAPPDATA%`, bloqué par une
    stratégie de groupe, erreur WinError 1260 ; puis `graphify.cmd`, sans
    hooks). Si un ancien `%LOCALAPPDATA%\graphify\graphify.cmd` existe,
    l'installeur le signale (il ne le supprime pas).
- **Variante légère par pip** (`install-pip.cmd`, `scripts/make-pip-zip.py`,
  dossier `paquet-pip/`, zip ≈ 2,3 Mo) : le wheel graphify-local et un
  `requirements.txt` (le `.lock` Windows, où graphify-local pointe sur le
  fichier local). `pip install --require-hashes --only-binary=:all:`
  télécharge les dépendances depuis PyPI. Testé : Linux (Python 3.10.7,
  pip 22.2.2, téléchargement PyPI réel, `kiro verify` réussi ; un wheel
  modifié est refusé et rien n'est installé) et Windows sous Wine (Python
  Windows 3.10.7, pip 22.2.2, téléchargement PyPI réel des paquets Windows,
  `kiro verify`, `graphify.exe` du dossier Scripts, `update` et
  `hook install` réussis).
- **`build_bundle.py`** (Python, fonctionne sous Windows, Linux et macOS ;
  `build-bundle.sh` n'est plus qu'une enveloppe) : reconstruction sur une
  machine connectée. Options : `--python` (défaut 3.10.7) et `--only <système>`
  pour un zip d'un seul système (Windows seul : ≈ 112 Mo). Versions figées par
  les `.lock`, complétude vérifiée, diff des empreintes affiché. Testé ici :
  reconstruction **à l'identique** (même empreinte de zip) avec un
  environnement de construction neuf.
- L'installeur distingue désormais « paquets absents » (installeur lancé
  depuis l'archive des sources, qui ne contient pas `wheelhouse/`) et
  « version de Python non prévue ».

## 10. Tests

- **`tests/test_local.py`** (nouveau, 57 tests) : verrou, commandes
  refusées, absence d'IA même avec des clés en environnement, secrets, HTML,
  pipeline Kiro de bout en bout (pièges compris), lecture partielle, `verify`,
  contenu du skill, `kiro install`, hooks du dossier portable, découpage des
  lignes de commande Windows et contrôle de `CreateProcess`. **57/57 sans
  réseau** (Python 3.10.7 et 3.13).
- **`tests-fuite/bench.py`** (nouveau), banc anti-fuite :
  - corpus canari (code, md, PDF, docx, image, `.env`, raccourci Google, vidéo) ;
  - pièges : 15 variables d'IA, proxy et fournisseur local, faux `claude`,
    `curl`, `gh`, `gws`, `ollama`, `yt-dlp` ;
  - `strace` sur 33 commandes, plus une exécution sans réseau ;
  - résultat sur graphify-local : **36/36**.
  - **Contrôle** sur graphify d'origine : 17 échecs, dont des connexions TCP
    réelles (`extract`, `label`, `clone`), du DNS (`add`) et le lancement de
    `gws` (export Google Drive).
- **Suite d'origine** (8 308 tests), lancée sans réseau :
  - origine : 7 572 réussis, 719 échecs ou erreurs dus à l'environnement de
    test (liens symboliques, fichiers absents du sdist) ;
  - fork : 6 101 réussis, 712 échecs, 922 ignorés (avec raison). **Les 712
    échecs existent tous déjà sur l'origine, dans le même environnement** :
    0 nouvel échec.
  - Même comparaison sous **Python 3.10.7** (la version de vos postes) :
    origine 7 440 réussis / 718 échecs ; fork 6 111 réussis / 702 échecs ;
    **0 nouvel échec** une fois classés 2 tests qui lancent eux-mêmes `python -c`.
  - 13 fichiers ne sont plus collectés (module supprimé) et 908 tests sont
    marqués « skip ». Chacun a sa raison dans `tests/conftest.py` et
    `tests/local_skips.json` : 508 fonctions retirées, 152 intégrations
    d'autres assistants, 71 extractions par IA, 154 tests qui lancent
    eux-mêmes `git init`, `bash`, `node` ou `python -m build` (refusés par le
    verrou), 20 messages ou textes modifiés, et 3 tests qui vérifiaient la
    présence de commandes désormais retirées de `--help`.
  - J'ai vérifié que **aucun** blocage du verrou ne venait du code de
    graphify : tous viennent de la préparation des tests.
  - `test_security.py` a été adapté (tests de `safe_fetch` retirés) : 52/52.
- **Hooks git** testés en réel avec l'installation hors ligne : la
  reconstruction après commit fonctionne avec le verrou.
- **Après les derniers changements** (installeur portable, hooks, verrou
  Windows) : suite complète relancée sous Python 3.10.7 et comparée test par
  test au rapport précédent : **0 nouvel échec** (6 108 réussis, 710 échecs
  déjà présents sur l'origine, 924 ignorés).
  Relancée après le passage des messages en anglais : **0 nouvel échec**.
- **Dossier portable, Linux (Python 3.10.7)** : installation (≈ 18 s),
  `kiro verify` 15/15, banc anti-fuite **36/36** sur le lanceur du dossier ;
  hooks dans un vrai dépôt git : reconstruction après commit, puis à nouveau
  après **déplacement du dossier** (retrouvé via le PATH).
- **Dossier portable, Windows** : testé sous **Wine 9.0 avec le Python Windows
  officiel 3.10.7** (64 bits), installé dans un chemin contenant un espace
  (`C:\Users\Test User\COTS\Python310_x64`), et avec MinGit 2.47.1 :
  - `install-windows.cmd` → dossier créé, 67 paquets vérifiés, `graphify.exe`
    (vrai lanceur distlib) fonctionne, `kiro verify` réussi ; réinstallation
    par-dessus réussie ;
  - dossier déplacé dans `C:\Mes Outils\`, ajouté au PATH : `graphify
    --version`, `graphify update .`, `graphify kiro install` fonctionnent
    depuis un autre dossier ; un faux `python.exe` placé dans le projet n'est
    pas exécuté ;
  - `graphify hook install` : 4 hooks + pilote de fusion enregistrés (c'est
    ce test qui a révélé le blocage des appels git par le verrou sous Windows,
    corrigé, voir § 3) ;
  - reconstruction lancée exactement comme par le hook (même Python, même
    `PYTHONPATH`, même code de lancement détaché), dossier déplacé :
    `graph.json` mis à jour, verrou actif.

## 11. Ce qui n'est pas couvert ou pas vérifié

- **Kiro** : ce qu'il lit (le graphe, les documents lus par ses sous-agents)
  part vers son fournisseur, selon votre contrat entreprise. C'est le périmètre
  que vous avez choisi.
- **Lecture des images et des PDF par les sous-agents Kiro** : graphify
  convertit les PDF en texte localement. La lecture d'images par un sous-agent
  n'a pas été testée dans Kiro.
- **Code natif** : le verrou couvre le code Python et les programmes lancés.
  Une extension C qui ferait des appels système réseau directs n'émettrait pas
  d'événement d'audit. Aucune des 67 dépendances n'est une bibliothèque
  réseau ; pour une garantie au niveau du système, ajoutez un pare-feu par
  application ou un conteneur sans réseau.
- **Windows** : testé sous Wine (voir § 10), pas sur un vrai poste Windows.
  Non testable sous Wine : le script shell des hooks exécuté par Git for
  Windows (le shell MSYS se bloque sous Wine dès qu'il crée un sous-shell,
  limite connue de Wine) ; seule sa partie Python a été exécutée sous Wine, le
  script lui-même a été testé sous Linux. Non testés non plus : stratégies de
  groupe / AppLocker réelles, antivirus, Windows Terminal.
- **macOS** : paquets résolus, vérifiés et verrouillés, installation non testée.
- **Provenance** : les sources viennent de PyPI (sdist identique au wheel). Je
  n'ai pas pu comparer avec le dépôt GitHub `Graphify-Labs/graphify`.
