# graphify-local 0.9.93.1 - modifications détaillées de A à Z

> **Nom** : `graphify-local` est un nom **interne**, utilisé pour le dossier,
> l'archive zip et le nom de paquet pip. Pour les utilisateurs, l'outil
> s'appelle simplement **graphify** : la commande, les messages, le skill
> `/graphify` et `graphify --version`. Le nom de paquet pip reste
> différent de `graphifyy` pour qu'un `pip install -U graphifyy` tapé par
> erreur ne puisse pas remplacer cette version par celle d'origine. Rien n'est
> publié sur PyPI : la diffusion se fait par le zip interne.

Fork de **graphifyy 0.9.93** (PyPI), licence Apache-2.0 / MIT conservée
(fichiers `LICENSE`, `LICENSE-MIT`, `NOTICE` inchangés).

**Objectif unique : graphify ne doit pouvoir envoyer aucune donnée hors de la
machine.** L'assistant IA utilisé (Kiro, Claude Code, Codex…) n'est pas
modifié : aucune permission, aucun réglage, aucune restriction. On lui ajoute
seulement son skill et ses consignes, comme le faisait graphify d'origine.

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
  sortie de données le sont.

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

Avec des documents dans le corpus, elle indexe le code seul et indique que les
documents sont lus par l'assistant IA (« run /graphify in your AI assistant »).
Elle ne cherche plus de clé d'API.

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
(message `graphify: feature disabled - … (disabled by the anti-leak guard).`,
code de sortie 2) :

- les commandes `provider`, `prs`, `add`, `clone`, `global`, `label` (les
  communautés sont nommées par l'assistant quand il exécute `/graphify`) ;
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

## 6. Suites des assistants IA (restaurées, nettoyées)

> **Historique** : une première version ne gardait que Kiro, avec un skill
> réécrit en français et un pipeline propre (`graphify kiro prepare`,
> `finalize`, `labels`, `verify`, module `kiro_pipeline.py`). À votre demande,
> cette approche est **abandonnée** : comme dans graphify d'origine,
> `graphify kiro install` installe la suite Kiro, `graphify codex install` celle
> de Codex, etc. `kiro_pipeline.py` est supprimé ; seul l'auto-contrôle est
> conservé, sous le nom `graphify verify` (§ 7).

**Restauré depuis l'original** : les 16 skills (`skill.md`, `skill-codex.md`,
`skill-kiro.md`, `skill-vscode.md`, …, `skill-windows.md`), `command-kilo.md`,
les 6 blocs `always_on/*.md`, l'extension `pi/`, et les 8 références de chacun
des 14 assistants (`skills/<assistant>/references/*.md`). Les textes restent
en anglais, comme l'original ; seuls les passages qui pouvaient faire sortir
des données sont retirés ou remplacés par une courte note.

**Retiré de chaque skill** (13 skills découpés, les monolithes aider et devin,
et la variante PowerShell `skill-windows.md`) :
- l'installation et la mise à jour automatiques depuis PyPI
  (`uv tool install graphifyy`, `pip install graphifyy --break-system-packages`,
  `pipx`…). L'étape 1 vérifie seulement que graphify est importable et
  s'arrête sinon : « Install the internal graphify-local package (never
  'pip install graphifyy') » ;
- l'utilisation de Gemini ou d'une autre IA si une clé d'API est présente
  (`extract_corpus_parallel`, astuce `GEMINI_API_KEY`) : l'extraction
  sémantique est toujours faite par les sous-agents de l'assistant hôte, et
  aucune clé d'API n'est lue ;
- le clonage d'une URL GitHub, `add <url>`, la transcription vidéo/audio
  (whisper), `--mcp`, `--neo4j-push`, `--falkordb-push` ;
- les liens de sponsoring et vers docs.graphify.com.

**Références** :
- `transcribe.md` : remplacé par une note (transcription indisponible ;
  ajouter une transcription `.txt` ou `.md`) ;
- `add-watch.md` : section `add` retirée, `--watch` conservé ;
- `github-and-merge.md` : clonage retiré, fusion de plusieurs dossiers
  conservée ;
- `exports.md` : envois Neo4j/FalkorDB et MCP remplacés par une note ;
- `update.md` : les vidéos sont écartées au lieu d'être transcrites ;
  `cluster-only` garde les noms de communautés existants et ne demande jamais
  de noms à une IA.

**Autres fichiers** : `always_on/antigravity-rules.md` ne mentionne plus les
outils MCP ; `install.py` n'écrit plus la configuration MCP d'Antigravity
(`uv run --with graphifyy … graphify.serve`).

**Hooks des assistants** (Claude Code, Codex, Gemini, CodeBuddy, plugins
OpenCode et Kilo, extension Pi) : ils n'appellent que `graphify hook-guard` /
`graphify hook-check`, en local, et aucun ne contacte le réseau (vérifié dans
le code des plugins).

**Vérifié** :
- installation de chaque assistant (23 plateformes, globale et `--project`,
  plus les 21 sous-commandes `graphify <assistant> install`) : 432 fichiers
  écrits, analysés à la recherche de `pip install graphifyy`, `uv tool`,
  `GEMINI_API_KEY`, `extract_corpus_parallel`, `--mcp`, `git clone`,
  `yt-dlp`, `whisper`… : ces mots n'apparaissent que dans les notes qui
  expliquent qu'ils sont indisponibles ;
- tests de sécurité d'origine sur les skills (chemin d'entrée hostile,
  substitution par accents graves) : **193/193** sur les skills nettoyés.

**Conséquence** : les JSON écrits par les sous-agents passent par la
validation d'origine de graphify (`validate.py`). La validation renforcée du
pipeline Kiro (clés inconnues retirées, texte ressemblant à une commande
écarté, limites de taille par lot) n'existe plus.

## 7. `graphify verify` (`_selfcheck.py`, nouveau)

Ancien `graphify kiro verify`. Lancé dans un processus graphify, il vérifie
15 points et sort avec le code 1 si l'un échoue :
- verrou anti-fuite actif ; création de socket TCP, DNS, `curl`, `git push` et
  urllib bloqués ;
- aucun fournisseur d'IA dans graphify ;
- modules `prs`, `transcribe`, `pg_introspect` et `global_graph` absents ;
  serveur MCP absent ;
- bibliothèques HTML embarquées (vis-network, d3, mermaid) intactes.

Il signale aussi, pour information, les bibliothèques réseau présentes dans
l'environnement Python (`openai`, `requests`…), que graphify n'utilise pas.
`install-pip.cmd` le lance à la fin de l'installation.

## 8. Intégration et nettoyage

- **`__main__.py`** (repris de l'original, puis modifié) :
  - version lue sur la distribution `graphify-local` ; message « reinstall
    the internal graphify-local package » ;
  - route `graphify verify` ;
  - toutes les intégrations d'assistants sont disponibles, comme dans
    l'original ;
  - **rafraîchissement automatique des skills installés** conservé, comme
    dans l'original : après une mise à jour de graphify-local, les skills déjà
    installés sont réécrits au lancement suivant de `graphify` ;
  - aide : commandes et options refusées retirées (voir ci-dessous) ;
    publicité app.graphify.com retirée.
- **`install.py`** : publicités app.graphify.com retirées, configuration MCP
  d'Antigravity retirée. `graphify pi guard install|uninstall` ne lance plus
  le programme `pi` (refusé par le verrou) : la commande affiche
  `pi install <chemin>` à lancer soi-même et sort avec le code 2.
  `graphify pi guard path` est conservé.
- **`hooks.py`** :
  - suppression de la sonde qui exécutait l'interpréteur indiqué dans
    `graphify-out/.graphify_python` (fichier commitable par un tiers). Seuls
    l'interpréteur figé à l'installation ou le lanceur du PATH sont utilisés ;
  - **prise en charge du dossier portable** (voir § 9) : graphify n'y est pas
    dans le site-packages du Python. Quand `graphify hook install` est lancé
    depuis ce dossier (reconnu à son `graphify-local.json`), les hooks
    reçoivent le chemin de `graphify-local/lib` (`_GFY_LIB`) et l'exportent
    dans `PYTHONPATH`. Ce code reste mais est **inactif** avec l'installation
    par pip (aucun `graphify-local.json`).
- **Aide (`graphify --help`)** : les commandes et options refusées n'y
  figurent plus (clone, add, label, prs, provider, global, `pi guard
  install|uninstall`, `--backend`, `--model`, `--postgres`,
  `--google-workspace`, `--global`, `--push`, options propres aux appels LLM).
  `export neo4j` et `export falkordb` y sont décrits comme écrivant seulement
  un fichier Cypher. Ajout de `verify`.
- **Langue** : l'aide et les messages de la ligne de commande sont en
  anglais, comme graphify d'origine ; les skills et leurs références gardent
  le texte anglais d'origine. Restent en français : les `.cmd`, les README et
  cette documentation.
- **Messages** : retrait de « Tip: set GEMINI_API_KEY… » après
  `graphify update`, et des renvois à `graphify label` (refusé dans ce fork),
  remplacés par `/graphify --update in your AI assistant`.
- **`cli.py`** : `_print_cloud_cta` (publicité Graphify Cloud) neutralisé.
- **Nom de distribution** `graphify-local` (interne) : lecture de version
  (`__main__.py`, `install.py`, `export.py`, `cache.py`). Messages d'aide
  (`extract.py`, `detect.py`, `manifest_ingest.py`) qui renvoient au paquet
  interne au lieu de `pip install graphifyy[...]`.
- **`README.md`** du fork remplacé par une courte présentation (l'original
  décrivait l'installation depuis PyPI et le service hébergé). `PKG-INFO`
  (métadonnées générées du sdist d'origine) retiré.
- **`pyproject.toml`** :
  - nom `graphify-local`, version `0.9.93.1` ;
  - options conservées : pdf, office, leiden, watch, svg, sql, terraform,
    ocaml, pascal, commonlisp, dm, robot, solidity, vbnet, r, erlang, chinese,
    plus un méta-groupe `local` ;
  - options retirées : mcp, neo4j, falkordb, google, postgres, video, kimi,
    ollama, bedrock, anthropic, gemini, openai, all ;
  - point d'entrée `graphify-mcp` supprimé ;
  - fichiers embarqués : les 16 skills, `command-kilo.md`, les références,
    `always_on/`, `pi/`, `vendor/` (comme l'original, plus `vendor/`).

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

> **État actuel** (après le retour des suites de tous les assistants, Python
> 3.10.7, sans réseau) :
> - **`tests/test_local.py` : 66/66**. En plus des contrôles ci-dessous : les
>   16 skills et leurs fichiers sont livrés ; aucun skill, référence ou bloc
>   permanent ne contient d'installation depuis PyPI, d'appel à une IA externe
>   ou d'accès réseau (hors notes d'indisponibilité) ; `graphify install
>   --platform X --project` (12 assistants) et `graphify claude|codex|vscode|kiro
>   install` écrivent des suites propres ; `graphify verify` réussit ;
>   `graphify pi guard install` ne lance jamais `pi`, même présent dans le
>   PATH ; l'aide ne contient ni commande désactivée ni publicité.
> - **Suite d'origine** : origine 7 463 réussis, 695 échecs ou erreurs (dus à
>   l'environnement de test), 150 ignorés ; fork 6 582 réussis, 691 échecs ou
>   erreurs, 828 ignorés. **Les 691 échecs du fork échouent tous déjà sur
>   l'origine : 0 nouvel échec.**
> - 811 tests marqués « skip », chacun avec sa raison dans
>   `tests/local_skips.json` : 376 fonctions retirées, 344 tests qui lancent
>   eux-mêmes `git init`, `bash`, `node` ou `python -m build` (refusés par le
>   verrou), 71 extractions par IA, 6 messages d'aide, 6 sonde
>   `.graphify_python`, 3 `pi guard`, 2 publicité, 1 aide, 1 Google
>   Workspace, 1 faux positif mermaid. 11 fichiers ne sont plus collectés
>   (module supprimé, voir `tests/conftest.py`). `test_claude_md.py` et
>   `test_install_strings.py` sont de nouveau collectés (résultats identiques
>   à l'origine).
> - Tests de sécurité d'origine sur les skills (chemin d'entrée hostile,
>   substitution par accents graves), qui lancent `bash` et sont donc bloqués
>   dans le processus de test : exécutés à part, hors de ce processus,
>   **193/193**. Contenu du wheel vérifié à la main (équivalent de
>   `test_wheel_packaging.py`) : les 136 fichiers de skills, références, blocs
>   permanents et `pi/` sont présents et identiques aux sources.
> - **Banc anti-fuite : 38/38** sur une installation neuve (Python 3.10.7,
>   paquet pip), dont l'installation des suites Claude Code, Codex, Kiro,
>   Gemini et Copilot et le déroulé du skill (détection, exclusion des
>   secrets, extraction du code, graphe, rapport).
> - **Windows (Wine, Python Windows officiel 3.10.7 neuf)** : `install-pip.cmd`
>   (téléchargement PyPI réel), `graphify verify` 15/15, `graphify kiro
>   install`, `graphify install --platform codex --project`, `graphify update`,
>   refus de `graphify pi guard install`.
>
> Les paragraphes suivants décrivent les essais des versions précédentes.

- **`tests/test_local.py`** (nouveau ; 57 tests dans la version Kiro seule) : verrou, commandes
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

- **L'assistant IA** (Kiro aujourd'hui, un autre demain) : ce qu'il lit (le
  graphe, les documents lus par ses sous-agents) part vers son fournisseur,
  selon votre contrat entreprise. C'est le périmètre que vous avez choisi :
  graphify n'ajoute aucune autre destination.
- **Skills dans les assistants réels** : les skills nettoyés ont été installés
  et vérifiés pour chaque assistant (fichiers écrits, contenu, tests de
  sécurité d'origine), mais pas exécutés dans Kiro, Codex ou les autres
  assistants depuis cet environnement.
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
