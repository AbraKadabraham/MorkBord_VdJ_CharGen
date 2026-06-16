@echo off
setlocal
cd /d %~dp0

if not exist "Charbogen.jpg" (
  echo FEHLER: Charbogen.jpg wurde im Projektordner nicht gefunden.
  pause
  exit /b 1
)

if not exist "RandomTables.csv" (
  echo FEHLER: RandomTables.csv wurde im Projektordner nicht gefunden.
  pause
  exit /b 1
)

if not exist "config.json" (
  echo FEHLER: config.json wurde im Projektordner nicht gefunden.
  pause
  exit /b 1
)

echo Installiere/aktualisiere Abhaengigkeiten...
python -m pip install --upgrade pip
if errorlevel 1 goto :build_error
python -m pip install -r requirements.txt
if errorlevel 1 goto :build_error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist release rmdir /s /q release

set "PYI_CMD=python -m PyInstaller"

echo Starte Build mit PyInstaller...
%PYI_CMD% --noconfirm --clean --windowed --onefile ^
  --name VdJ_CharGen ^
  --add-data "Charbogen.jpg;." ^
  --add-data "RandomTables.csv;." ^
  --add-data "config.json;." ^
  charbogen_gui.py
if errorlevel 1 goto :build_error

if not exist "dist\VdJ_CharGen.exe" (
  echo FEHLER: Build abgeschlossen, aber dist\VdJ_CharGen.exe wurde nicht gefunden.
  goto :build_error
)

mkdir release
copy dist\VdJ_CharGen.exe release\VdJ_CharGen.exe >nul
if errorlevel 1 goto :build_error
copy Charbogen.jpg release\Charbogen.jpg >nul
if errorlevel 1 goto :build_error
copy RandomTables.csv release\RandomTables.csv >nul
if errorlevel 1 goto :build_error
copy config.json release\config.json >nul
if errorlevel 1 goto :build_error
copy start_generator.bat release\start_generator.bat >nul
if errorlevel 1 goto :build_error
copy README.txt release\README.txt >nul
if errorlevel 1 goto :build_error

echo.
echo Fertig. Die ausfuehrbare Version liegt in:
echo %CD%\release
pause
exit /b 0

:build_error
echo.
echo BUILD FEHLGESCHLAGEN.
echo Es wurde keine fertige EXE erzeugt.
echo.
echo Tipp: Diese Version nutzt "python -m PyInstaller", damit auch User-Installationen funktionieren.
pause
exit /b 1
