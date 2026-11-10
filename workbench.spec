# PyInstaller one-folder build. Runtime source is included for standalone code export.
a = Analysis(['workbench.py'], pathex=[], binaries=[],
    datas=[('engine.py','runtime'),('augmentation.py','runtime'),('dataset.py','runtime')],
    hiddenimports=['generation_ui','packaging_check'], hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=['PyQt5','PyQt6','PySide2'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='CV2Workbench',debug=False,
    bootloader_ignore_signals=False,strip=False,upx=False,console=True)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='CV2Workbench')
