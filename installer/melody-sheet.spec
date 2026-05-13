# PyInstaller spec for MelodySheet Windows builds.
#
# Run on a Windows machine inside the repo root:
#   apps\api\.venv\Scripts\pyinstaller.exe installer\melody-sheet.spec
#
# Output: dist/MelodySheet/MelodySheet.exe + dist/MelodySheet/_internal/...
# Inno Setup then wraps this directory into a one-file Windows installer.
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()  # noqa: F821 — PyInstaller injects SPECPATH
REPO_ROOT = SPEC_DIR.parent
API_ROOT = REPO_ROOT / "apps" / "api"
WEB_OUT = REPO_ROOT / "apps" / "web" / "out"
FFMPEG_DIR = REPO_ROOT / "installer" / "vendored" / "ffmpeg"

# --- Data files bundled into _MEIPASS ---
datas = []
binaries = []
hiddenimports = []

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

# Bundle our own backend source files
datas.append((str(API_ROOT / "app"), "apps/api/app"))
datas.append((str(API_ROOT / "main.py"), "apps/api"))

# --- Use collect_all for heavy third-party deps with lots of lazy imports ---
# This is the "shotgun" approach: pulls in EVERY submodule + data file of each
# package. Bundle gets bigger but no more random ImportError at runtime.
for pkg in (
    "librosa",
    "soundfile",
    "scipy",
    "numpy",
    "numba",
    "music21",
    "basic_pitch",
    "sklearn",
    "fastapi",
    "starlette",
    "pydantic",
    "uvicorn",
    "anyio",
    "h11",
    "httptools",
    "websockets",
    "watchfiles",
    "click",
    "audioread",
    "soxr",
    "pooch",
    "resampy",
    "lazy_loader",
    "joblib",
    "msgpack",
    "decorator",
    "llvmlite",
    "onnxruntime",
):
    try:
        sub_datas, sub_binaries, sub_hidden = collect_all(pkg)
        datas += sub_datas
        binaries += sub_binaries
        hiddenimports += sub_hidden
        print(f"[spec] collect_all({pkg!r}) +{len(sub_datas)} datas, "
              f"+{len(sub_binaries)} binaries, +{len(sub_hidden)} hidden")
    except Exception as exc:
        print(f"[spec] collect_all({pkg!r}) skipped: {exc}", file=sys.stderr)

# Application-internal submodules (small, but explicit so launcher's
# `from main import app` doesn't fail).
hiddenimports += [
    "main",
    "app",
    "app.config",
    "app.job_store",
    "app.models",
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

# uvicorn auto-detector specifically loads protocol modules by name at runtime.
hiddenimports += collect_submodules("uvicorn")

block_cipher = None

a = Analysis(
    [str(SPEC_DIR / "launcher.py")],
    pathex=[str(API_ROOT)],
    binaries=binaries,
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
    # UPX can mangle some scientific libraries' DLLs (numpy, scipy, onnxruntime)
    # and cause "DLL load failed" at runtime. Safer to leave them untouched.
    upx=False,
    console=True,
    icon=str(SPEC_DIR / "melody-sheet.ico") if (SPEC_DIR / "melody-sheet.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="MelodySheet",
)
