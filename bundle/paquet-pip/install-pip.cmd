@echo off
rem graphify - installation par pip (Windows, Python 3.10 64 bits), double-clic.
rem Installe graphify-local (le fichier .whl a cote de ce fichier) et ses 66
rem dependances, telechargees par pip depuis PyPI (ou le miroir de pip.ini).
rem Versions et empreintes sha256 figees dans requirements.txt : tout fichier
rem different est refuse. La commande graphify est creee dans le dossier
rem Scripts de ce Python, comme pour tout pip install.
setlocal
pushd "%~dp0"
set "PY="
where python >nul 2>nul && python -c "import sys; sys.exit(sys.version_info[:2] != (3, 10))" >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && py -3.10 -c "" >nul 2>nul && set "PY=py -3.10"
)
if not defined PY (
  echo Python 3.10 est introuvable dans le PATH. Installez-le ou ajoutez-le au PATH, puis relancez ce fichier.
  goto :fin
)
%PY% -m pip install --require-hashes --only-binary=:all: --disable-pip-version-check --no-warn-script-location -r requirements.txt
if errorlevel 1 (
  echo Echec de l'installation par pip.
  goto :fin
)
%PY% -m graphify verify
if errorlevel 1 (
  echo Auto-controle en echec : ne pas utiliser cette installation.
  goto :fin
)
echo.
echo Installe. La commande graphify est dans :
%PY% -c "import sysconfig; print('  ' + sysconfig.get_path('scripts'))"
echo Si "graphify" n'est pas reconnu, ajoutez ce dossier au PATH puis ouvrez un nouveau terminal.
:fin
popd
pause
