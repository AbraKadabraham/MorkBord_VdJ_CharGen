# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['charbogen_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('charbogen_gui.py', '.'), ('field_wizard.py', '.'), ('config.json', '.'), ('config_mb.json', '.'), ('Charbogen_VdJ.jpg', '.'), ('Charbogen_MB.jpg', '.'), ('RandomTables_VdJ.csv', '.'), ('RandomTables_MB.csv', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VdJ_CharGen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
