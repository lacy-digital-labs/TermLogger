# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for TermLogger.

This creates a single-file executable for the terminal-based amateur radio
logging application.

Usage:
    pyinstaller termlogger.spec
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# Get the project root directory
project_root = Path(SPECPATH)

# Collect all textual resources
datas = [(str(project_root / 'src' / 'termlogger' / 'termlogger.css'), 'termlogger')]
binaries = []
hiddenimports = [
    'pydantic',
    'pydantic_core',
    'httpx',
    'httpcore',
    'h11',
    'anyio',
    'sniffio',
    'certifi',
    'idna',
    'dateutil',
    'xmltodict',
    'rich',
    'markdown_it',
    'pygments',
]

# Collect all textual data
tmp_ret = collect_all('textual')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    [str(project_root / 'src' / 'termlogger' / '__main__.py')],
    pathex=[str(project_root / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL'],
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
    name='termlogger',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
