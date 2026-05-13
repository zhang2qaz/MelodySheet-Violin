# PyInstaller spec for MelodySheet Windows builds.
#
# Run on a Windows machine inside the repo root:
#   apps\api\.venv\Scripts\pyinstaller.exe installer\melody-sheet.spec
#
# Output: dist/MelodySheet/MelodySheet.exe + dist/MelodySheet/_internal/...
# Inno Setup then wraps this directory into a one-file Windows installer.
# (See installer/melody-sheet.iss and installer/build.ps1.)
from __future__ import annotations

import os
import sys
from pathlib import Path

# `__file__` isn't defined when PyInstaller runs a spec, so resolve via argv.
SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821  — PyInstaller injects SPECPATH
REPO_ROOT = SPEC_DIR.parent
API_ROOT = REPO_ROOT / "apps" / "api"
WEB_OUT = REPO_ROOT / "apps" / "web" / "out"
FFMPEG_DIR = REPO_ROOT / "installer" / "vendored" / "ffmpeg"

# Bundled data files (web frontend + optional ffmpeg). When ffmpeg isn't
# vendored the librosa fallback in music_processing.py still handles common
# formats, but bundling makes mp3/m4a uploads first-class.
datas = []
if WEB_OUT.exists():
    datas.append((str(WEB_OUT), "web"))
else:
    print(
        "WARNING: Next.js static export missing at apps/web/out — frontend "
        "will not be bundled. Run `NEXT_OUTPUT=export npm run build` first.",
        file=sys.stderr,
    )
if FFMPEG_DIR.exists():
    datas.append((str(FFMPEG_DIR), "ffmpeg"))
# Include the api package source so `from app...` imports resolve at runtime.
datas.append((str(API_ROOT / "app"), "apps/api/app"))
datas.append((str(API_ROOT / "main.py"), "apps/api"))

# Heavy native libraries that pyinstaller's analyser sometimes misses.
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "librosa",
    "librosa.core",
    "librosa.feature",
    "librosa.onset",
    "librosa.beat",
    "librosa.effects",
    "soundfile",
    "scipy",
    "scipy.signal",
    "scipy.fft",
    "numpy",
    "music21",
    "music21.stream",
    "music21.note",
    "music21.musicxml.m21ToXml",
    "basic_pitch",
    "basic_pitch.inference",
    "sklearn",
    "sklearn.utils._weight_vector",
    "app.music_processing",
    "app.audio_io",
    "app.transcribe_mono",
    "app.transcribe_poly",
    "app.rhythm",
    "app.score_builder",
    "app.instrument_id",
    "app.separation",
    "app.pitch_crepe",
]

# music21 ships a `corpus` directory; older versions had musicxml/xsd too.
# Only include what actually exists at build time so PyInstaller doesn't bail.
try:
    import music21

    music21_root = Path(music21.__file__).parent
    for sub in ("corpus", "musicxml/xsd"):
        candidate = music21_root / Path(sub)
        if candidate.exists():
            datas.append((str(candidate), f"music21/{sub}"))
except Exception:
    pass

# librosa ships .npz tables; PyInstaller hooks usually cover these.
block_cipher = None

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(API_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "PyQt5",
        "PyQt6",
        "PySide6",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MelodySheet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # keep console visible so users can see startup logs
    icon=str(SPEC_DIR / "melody-sheet.ico") if (SPEC_DIR / "melody-sheet.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MelodySheet",
)
