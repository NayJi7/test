@echo off
rem graphify - installation HORS LIGNE pour Windows (double-clic).
rem Cree, a cote de ce fichier, le dossier autonome graphify-local\
rem (graphify.exe + lib\). Necessite Python 3.10 64 bits dans le PATH
rem (ou le lanceur "py"). Toute la logique est dans installer.py.
setlocal
set "PY="
where python >nul 2>nul && python -c "import sys; sys.exit(sys.version_info[:2] != (3, 10))" >nul 2>nul && set "PY=python"
if not defined PY (
  where py >nul 2>nul && py -3.10 -c "" >nul 2>nul && set "PY=py -3.10"
)
if not defined PY (
  echo Python 3.10 est introuvable dans le PATH. Installez-le ou ajoutez-le au PATH, puis relancez ce fichier.
  pause
  exit /b 1
)
%PY% -I "%~dp0installer.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Echec de l'installation, code %RC%.
pause
exit /b %RC%
