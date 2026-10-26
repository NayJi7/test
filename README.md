# graphify-local

Fork de graphify (`graphifyy` 0.9.93) sans aucune sortie de données, utilisable
depuis n'importe quel assistant IA (Kiro, Claude Code, Codex…) par son skill.

| Dossier | Contenu |
|---|---|
| `fork/` | Sources du fork (paquet Python `graphify`, distribution `graphify-local` 0.9.93.1) et ses tests (`fork/tests/test_local.py` + suite d'origine adaptée) |
| `upstream/` | Sources d'origine `graphifyy` 0.9.93, pour comparaison (non incluses dans l'archive des sources : `pip download --no-deps --no-binary :all: graphifyy==0.9.93`) |
| `bundle/` | Installation par pip (Windows, Python 3.10) : `paquet-pip/` (le paquet à livrer : wheel graphify-local + `requirements.txt` à versions et empreintes figées + `install-pip.cmd`), fichier de verrouillage, scripts de reconstruction (`build_bundle.py`) |
| `tests-fuite/bench.py` | Banc anti-fuite (strace + corpus canari + pièges) |
| `docs/MODIFICATIONS.md` | **Explication détaillée de chaque modification** |
| `docs/PATCH-COMPLET.diff` | Diff complet origine → fork |

Démarrage rapide : voir `bundle/README.md`.

Nom interne : `graphify-local` (dossier, zip, nom du paquet pip). Pour les utilisateurs, la commande et le skill s'appellent `graphify`.
