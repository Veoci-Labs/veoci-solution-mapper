# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for veoci-map standalone executable."""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all submodules for packages that use dynamic imports
hiddenimports = collect_submodules('questionary') + collect_submodules('prompt_toolkit') + [
    # veoci_mapper package
    'veoci_mapper',
    'veoci_mapper.config',
    'veoci_mapper.version',
    'veoci_mapper.cli',
    'veoci_mapper.client',
    'veoci_mapper.analyzer',
    'veoci_mapper.fetcher',
    'veoci_mapper.graph',
    # output subpackage
    'veoci_mapper.output',
    'veoci_mapper.output.dashboard',
    'veoci_mapper.output.json',
    'veoci_mapper.output.markdown',
    'veoci_mapper.output.mermaid',
    # Dependencies that may have hidden imports
    'google.genai',
    'google.ai.generativelanguage',
    'networkx',
    'markdown',
    'typer',
    'click',
    'rich',
]

# Collect package data files if any
datas = []
datas += collect_data_files('google.genai', include_py_files=True)
datas += collect_data_files('questionary')

# Exclude unnecessary packages to reduce size
excludes = [
    # GUI frameworks (we're CLI-only)
    'tkinter',
    'tk',
    # Data science libs we don't use
    'matplotlib',
    'PIL',
    'numpy',
    'scipy',
    'pandas',
    # Testing
    'pytest',
    'unittest',
    # Development tools
    'IPython',
    'jupyter',
]

a = Analysis(
    ['src/veoci_mapper/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='veoci-map',
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
