# graphify - bundle interne d'installation hors ligne (graphify-local 0.9.93.1)

Fork de `graphifyy` 0.9.93 qui **ne peut rien envoyer hors de la machine** :
aucun appel à une IA externe, aucun téléchargement, aucun serveur, et un verrou
anti-fuite actif dans chaque processus graphify. L'intelligence (lecture des
documents, nommage des communautés) est assurée par **Kiro**, à qui graphify
fournit un skill et des missions d'extraction. Kiro lui-même n'est ni bridé ni
reconfiguré.

## Contenu

| Élément | Rôle |
|---|---|
| `install-windows.cmd` | Installation Windows : double-clic (pas de PowerShell) |
| `install-offline.sh` | Installation Linux / macOS |
| `installer.py` | L'installeur lui-même (bibliothèque standard Python uniquement), appelé par les deux fichiers ci-dessus |
| `wheelhouse/<plateforme>-py310/` | Les 67 paquets nécessaires (graphify + dépendances), précompilés pour Python 3.10, pour Linux x86_64, Windows x64 et macOS Apple Silicon |
| `requirements/<plateforme>-py310.lock` | Version exacte et empreinte sha256 de chacun de ces 67 fichiers |
| `outils/banc-anti-fuite.py` | Banc anti-fuite (Linux, `strace`) |

Aucune des 67 dépendances n'est une bibliothèque réseau : pas de `requests`,
`httpx`, `urllib3`, `openai`, `anthropic`, `boto3`, `mcp`, `huggingface_hub`,
`yt-dlp`…

## 1. Installer (sur chaque poste, sans réseau)

Prérequis : **Python 3.10** (testé avec 3.10.7). Tout Python 3.10.x convient.

**Windows** : décompresser le zip, puis **double-cliquer sur
`install-windows.cmd`**. Par défaut (mode « dossier »), l'installeur :
- installe les paquets dans `%LOCALAPPDATA%\graphify\lib` ;
- crée `%LOCALAPPDATA%\graphify\graphify.cmd`, qui lance **le Python déjà
  présent sur le poste** (`python -m graphify`) : aucun `python.exe` n'est
  copié, aucun exécutable n'est créé, le Python du poste n'est pas modifié.
  C'est compatible avec les stratégies de groupe qui interdisent d'exécuter
  des programmes depuis le profil utilisateur (erreur « WinError 1260 »);
- ajoute ce dossier au PATH de l'utilisateur (sans droits administrateur).
  Ouvrez ensuite un nouveau terminal.

Options : `--dest D:\Outils\graphify` (autre dossier, par ex. si les scripts
`.cmd` sont bloqués dans le profil), `--no-path`, `--mode venv` (environnement
Python dédié, si votre poste l'autorise). Limite du mode dossier : les hooks
git automatiques (`graphify hook install`) ne sont pas pris en charge ; mettez
le graphe à jour avec `/graphify --update` dans Kiro ou `graphify update .`.

**Linux / macOS** :

```bash
unzip graphify-local-0.9.93.1.zip && cd graphify-local
bash install-offline.sh                          # installe dans ~/.local/graphify
export PATH="$HOME/.local/graphify/bin:$PATH"    # à ajouter à ~/.bashrc ou ~/.zshrc
```

Option commune : `--dest <dossier>` pour choisir le dossier d'installation.
Pour forcer un Python précis : `PYTHON=/chemin/python3.10 bash install-offline.sh`
(Linux/macOS) ou `py -3.10 -I installer.py` (Windows).

L'installeur :
1. choisit les paquets correspondant au système et à la version de Python du
   poste (message clair si la version n'est pas prévue dans le bundle) ;
2. installe dans un dossier dédié (mode « dossier », défaut Windows) ou dans un
   environnement Python dédié (mode « venv », défaut Linux/macOS), sans jamais
   modifier le Python du système ;
3. installe uniquement depuis `wheelhouse/` (`--no-index` : PyPI n'est jamais contacté) ;
4. refuse tout fichier dont l'empreinte diffère du `.lock` (`--require-hashes`) ;
5. termine par `graphify kiro verify`, qui doit afficher « vérification réussie ».

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
graphify kiro verify                          # auto-contrôle de l'installation
python3 -I outils/banc-anti-fuite.py $(which graphify)   # banc anti-fuite complet (Linux, strace)
```

## 6. Construire ou mettre à jour le bundle

Sur une machine **connectée** (Windows, Linux ou macOS, Python ≥ 3.10), depuis
le dossier source complet `graphify-local/` (archive des sources : `fork/` +
`bundle/`) :

```bash
cd bundle
python build_bundle.py                        # zip pour les 3 systèmes (≈ 350 Mo)
python build_bundle.py --only windows-amd64   # zip Windows seul (≈ 110 Mo)
python build_bundle.py --python 3.10.7        # version de Python des postes (défaut 3.10.7)
```

Le zip produit (`graphify-local-<version>.zip` ou
`graphify-local-<version>-windows-amd64-py310.zip`) est celui à diffuser aux
postes : lui seul contient les paquets (`wheelhouse/`). **L'archive des
sources ne contient pas les paquets** ; l'installeur le signale si on la lance
par erreur.

Les versions des dépendances restent figées par les `.lock` existants ; le
script vérifie que toutes les dépendances requises pour la version de Python
et chaque système sont présentes, puis affiche les différences d'empreintes
(« aucune » = fichiers identiques). Pour changer volontairement une
dépendance, supprimez le `.lock` concerné, relancez, relisez le diff, puis
relancez le banc anti-fuite.

## Documents qui contiennent un secret

`graphify kiro prepare` liste les documents écartés (règle et numéro de ligne,
jamais la valeur). Ils n'entrent pas dans le graphe. Si c'est un faux positif,
un humain peut approuver **cette version exacte** du fichier :

```bash
echo "$(sha256sum docs/fichier.md | cut -d' ' -f1)  docs/fichier.md" >> .graphify-secrets-allow
```

Toute modification ultérieure du fichier invalide l'approbation.
