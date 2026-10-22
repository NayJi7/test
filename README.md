# graphify-local

## Installer sur Windows depuis ce depot (sans reseau ensuite)

```
git clone --branch graphify-local --single-branch https://github.com/NayJi7/test graphify-local
```

Puis double-cliquer sur `graphify-local\bundle\install-windows.cmd` (Python 3.10 requis).
Les paquets Windows sont dans `bundle/wheelhouse/windows-amd64-py310/` ; leurs
empreintes sont verifiees a l'installation. Pour Linux/macOS, reconstruire les
paquets avec `python bundle/build_bundle.py --only linux-x86_64` (ou `macos-arm64`)
sur une machine connectee.


Fork de graphify (`graphifyy` 0.9.93) sans aucune sortie de données, intégré à
Kiro par un skill.

| Dossier | Contenu |
|---|---|
| `fork/` | Sources du fork (paquet Python `graphify`, distribution `graphify-local` 0.9.93.1) et ses tests (`fork/tests/test_local.py` + suite d'origine adaptée) |
| `bundle/` | Installation hors ligne (Python 3.10) : `install-windows.cmd`, `install-offline.sh`, `installer.py`, fichiers de verrouillage, scripts de reconstruction. Le dossier `wheelhouse/` (≈ 350 Mo pour les 3 plateformes) se régénère avec `python bundle/build_bundle.py` (option `--only windows-amd64` pour Windows seul) |
| `tests-fuite/bench.py` | Banc anti-fuite (strace + corpus canari + pièges) |
| `docs/MODIFICATIONS.md` | **Explication détaillée de chaque modification** |
| `docs/PATCH-COMPLET.diff` | Diff complet origine → fork |

Démarrage rapide : voir `bundle/README.md`.

Nom interne : `graphify-local` (dossier, zip, nom du paquet pip). Pour les utilisateurs, la commande et le skill s'appellent `graphify`.
