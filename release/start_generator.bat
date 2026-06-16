@echo off
cd /d %~dp0
if exist "VdJ_CharGen.exe" (
  start "" "VdJ_CharGen.exe"
) else (
  python charbogen_gui.py
)
