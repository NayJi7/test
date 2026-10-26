# graphify - installation interne par pip (graphify-local 0.9.93.1)

Fork de `graphifyy` 0.9.93 qui **ne peut rien envoyer hors de la machine** :
aucun appel à une IA externe, aucun téléchargement, aucun serveur, et un verrou
anti-fuite actif dans chaque processus graphify. L'intelligence (lecture des
documents, nommage des communautés) est assurée par **l'assistant IA dans
lequel vous tapez `/graphify`** (Kiro, Claude Code, Codex, Copilot…) et par ses
propres sous-agents : graphify ne fait jamais appel à une autre IA. L'assistant
lui-même n'est ni bridé ni reconfiguré.

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

puis `python -m graphify verify`, qui doit afficher « verification passed ».

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
  `graphify verify` échoue alors. D'autres installations pip peuvent
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

## 2. Brancher graphify sur votre assistant IA

Comme dans graphify d'origine, chaque assistant a sa propre suite (skill
`/graphify`, références, consignes permanentes, hook éventuel). On installe
celle de l'assistant utilisé, et seulement celle-là :

| Assistant | Commande | Fichiers écrits |
|---|---|---|
| Kiro (IDE/CLI) | `graphify kiro install` (dans le projet) | `.kiro/skills/graphify/` (skill + références), `.kiro/steering/graphify.md` |
| Claude Code | `graphify install --platform claude` puis, dans le projet, `graphify claude install` | `~/.claude/skills/graphify/`, `~/.claude/CLAUDE.md` ; dans le projet : `CLAUDE.md`, hook `PreToolUse` dans `.claude/settings.json` |
| Codex | `graphify install --platform codex` puis, dans le projet, `graphify codex install` | `~/.codex/skills/graphify/` ; dans le projet : `AGENTS.md`, `.codex/hooks.json` |
| GitHub Copilot CLI | `graphify copilot install` | `~/.copilot/skills/graphify/` |
| VS Code Copilot Chat | `graphify vscode install` (dans le projet) | `~/.copilot/skills/graphify/`, `.github/copilot-instructions.md` |
| Gemini CLI | `graphify gemini install` (dans le projet) | `~/.gemini/skills/graphify/`, `GEMINI.md`, hook dans `.gemini/settings.json` |
| Cursor | `graphify cursor install` (dans le projet) | `.cursor/rules/graphify.mdc` |
| Autres (OpenCode, Kilo, Aider, Amp, OpenClaw, Droid, Trae, Antigravity, Hermes, Pi, Devin, CodeBuddy…) | `graphify <assistant> install` ou `graphify install --platform <assistant>` | voir `graphify --help` |

- `graphify install --platform X` installe le skill dans le profil de
  l'utilisateur ; ajouter `--project` pour l'installer dans le dossier courant
  (fichiers à commiter avec le projet). `graphify <assistant> install` écrit
  les consignes permanentes du projet (et le hook pour Claude Code, Codex et
  Gemini) ;
- les hooks n'appellent que `graphify hook-guard` / `graphify hook-check`, en
  local : ils rappellent à l'assistant d'interroger le graphe avant de fouiller
  les fichiers ;
- Kiro : aucun réglage ni aucune permission de Kiro n'est modifié ;
- Codex : la commande s'appelle `$graphify`, et l'extraction en parallèle
  demande `multi_agent = true` sous `[features]` dans `~/.codex/config.toml` ;
- Pi : graphify ne lance pas Pi lui-même (verrou anti-fuite). Pour le
  garde-fou natif de Pi, lancer à la main `pi install <chemin>`, où
  `<chemin>` est affiché par `graphify pi guard path` ;
- désinstaller : `graphify <assistant> uninstall`, ou `graphify uninstall`
  pour tous les assistants détectés ;
- après une mise à jour de graphify-local, les skills déjà installés sont
  rafraîchis au lancement suivant de `graphify` (comme dans l'original).

Les skills sont ceux de graphify d'origine (en anglais), nettoyés de tout ce
qui pouvait faire sortir des données : jamais d'installation depuis PyPI,
aucune clé d'API lue, aucune IA externe (Gemini, API Claude…), pas de
clonage d'URL, pas de transcription vidéo, pas de serveur MCP, pas d'envoi
vers Neo4j/FalkorDB.

## 3. Construire le graphe (dans l'assistant)

Dans l'assistant, tapez `/graphify` (ou `/graphify <dossier>` ; `$graphify`
dans Codex). Le skill enchaîne, comme l'original :

1. détection des fichiers et exclusion des documents contenant un secret ;
2. analyse locale du code (tree-sitter, sans IA) ;
3. lecture des documents, PDF et images par **les sous-agents de l'assistant
   lui-même** (un lot de fichiers par sous-agent) ;
4. assemblage du graphe, communautés, rapport `GRAPH_REPORT.md` et
   `graph.html` dans `graphify-out/` ;
5. nommage des communautés par l'assistant.

Mise à jour : `/graphify --update`. Le code seul se met aussi à jour sans
assistant : `graphify update .` ou les hooks git (`graphify hook install`).

## 4. Interroger

L'assistant le fait de lui-même grâce aux consignes installées. À la main :

```bash
graphify query "qui travaille sur la facturation ?"
graphify path "Projet Atlas" "facturer"
graphify explain "Client"
```

## 5. Vérifier à tout moment

```bash
graphify verify                                        # auto-contrôle de l'installation
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

`/graphify` affiche la liste des documents écartés. Le détail (règle et numéro
de ligne, jamais la valeur) est dans `secret_findings` de
`graphify-out/.graphify_detect.json`. Ces documents n'entrent pas dans le
graphe et ne sont jamais proposés aux sous-agents. Si c'est un faux positif,
un humain peut approuver **cette version exacte** du fichier :

```bash
echo "$(sha256sum docs/fichier.md | cut -d' ' -f1)  docs/fichier.md" >> .graphify-secrets-allow
```

```powershell
"$((Get-FileHash docs\fichier.md).Hash.ToLower())  docs/fichier.md" | Add-Content .graphify-secrets-allow
```

Toute modification ultérieure du fichier invalide l'approbation.
