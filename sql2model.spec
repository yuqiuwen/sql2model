# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['sql2model.py'],
    pathex=[],
    binaries=[],
    datas=[('/Users/admin/data/resources/app/sql2model/sql2model_release0.1.0', 'resources')],
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
    [],
    exclude_binaries=True,
    name='sql2model',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/Icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='sql2model',
)
app = BUNDLE(
    coll,
    name='sql2model.app',
    icon='./assets/Icon.icns',
    bundle_identifier=None,
)
