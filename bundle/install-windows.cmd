@echo off
rem graphify - installation HORS LIGNE pour Windows (double-clic).
rem Necessite Python 3.10 (lanceur "py" ou "python" dans le PATH).
rem Toute la logique est dans installer.py (bibliotheque standard uniquement).
setlocal
set "PY="
where py >nul 2>nul && set "PY=py -3.10"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3.10 est introuvable. Installez-le puis relancez ce fichier.
  pause
  exit /b 1
)
%PY% -I "%~dp0installer.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" echo Echec de l'installation (code %RC%).
pause
exit /b %RC%
