@echo off
setlocal
cd /d %~dp0

echo ============================================================
echo  VdJ / Moerk Borg CharGen  -  EXE-Build
echo ============================================================
echo.

:: ---------------------------------------------------------
:: Pflichtdateien pruefen
:: ---------------------------------------------------------
for %%F in (
    charbogen_gui.py
    field_wizard.py
    config.json
    config_mb.json
    Charbogen_VdJ.jpg
    Charbogen_MB.jpg
    RandomTables_VdJ.csv
    RandomTables_MB.csv
) do (
    if not exist "%%F" (
        echo FEHLER: Pflichtdatei "%%F" nicht gefunden.
        pause
        exit /b 1
    )
)

:: ---------------------------------------------------------
:: Abhaengigkeiten
:: ---------------------------------------------------------
echo Installiere/aktualisiere Abhaengigkeiten...
python -m pip install --upgrade pip
if errorlevel 1 goto :build_error
python -m pip install -r requirements.txt
if errorlevel 1 goto :build_error

:: ---------------------------------------------------------
:: Alte Build-Ordner raeumen
:: ---------------------------------------------------------
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist release rmdir /s /q release

:: ---------------------------------------------------------
:: fonts/-Ordner: nur einbinden wenn vorhanden
:: ---------------------------------------------------------
set "FONTS_ARG="
if exist fonts\ (
    set "FONTS_ARG=--add-data "fonts;fonts""
)

:: ---------------------------------------------------------
:: PyInstaller-Build
:: ---------------------------------------------------------
echo Starte Build mit PyInstaller...
python -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name VdJ_CharGen ^
  --add-data "charbogen_gui.py;." ^
  --add-data "field_wizard.py;." ^
  --add-data "config.json;." ^
  --add-data "config_mb.json;." ^
  --add-data "Charbogen_VdJ.jpg;." ^
  --add-data "Charbogen_MB.jpg;." ^
  --add-data "RandomTables_VdJ.csv;." ^
  --add-data "RandomTables_MB.csv;." ^
  %FONTS_ARG% ^
  charbogen_gui.py
if errorlevel 1 goto :build_error

if not exist "dist\VdJ_CharGen.exe" (
    echo FEHLER: dist\VdJ_CharGen.exe wurde nach dem Build nicht gefunden.
    goto :build_error
)

:: ---------------------------------------------------------
:: Release-Ordner zusammenstellen
:: ---------------------------------------------------------
mkdir release

copy dist\VdJ_CharGen.exe     release\VdJ_CharGen.exe     >nul  || goto :build_error
copy config.json              release\config.json          >nul  || goto :build_error
copy config_mb.json           release\config_mb.json       >nul  || goto :build_error
copy Charbogen_VdJ.jpg        release\Charbogen_VdJ.jpg    >nul  || goto :build_error
copy Charbogen_MB.jpg         release\Charbogen_MB.jpg     >nul  || goto :build_error
copy RandomTables_VdJ.csv     release\RandomTables_VdJ.csv >nul  || goto :build_error
copy RandomTables_MB.csv      release\RandomTables_MB.csv  >nul  || goto :build_error

if exist README.md   copy README.md   release\README.md   >nul
if exist README.txt  copy README.txt  release\README.txt  >nul

:: fonts-Ordner kopieren falls vorhanden
if exist fonts\ (
    xcopy /e /i /q fonts release\fonts >nul
)

:: Output-Ordner anlegen damit er im Release vorhanden ist
if not exist release\Output mkdir release\Output

echo.
echo ============================================================
echo  BUILD ERFOLGREICH
echo  Fertige Version: %CD%\release
echo ============================================================
pause
exit /b 0

:build_error
echo.
echo ============================================================
echo  BUILD FEHLGESCHLAGEN
echo  Keine EXE erzeugt.
echo ============================================================
pause
exit /b 1
