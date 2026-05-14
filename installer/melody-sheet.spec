# PyInstaller spec for MelodySheet (Windows + macOS).
#
# Windows:
#   apps\api\.venv\Scripts\pyinstaller.exe installer\melody-sheet.spec
#   -> dist/MelodySheet/MelodySheet.exe (onedir, wrapped by Inno Setup)
#
# macOS:
#   apps/api/.venv/bin/pyinstaller installer/melody-sheet.spec
#   -> dist/MelodySheet.app  (bundle, wrapped by create-dmg)
from __future__ import annotations

import platform
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

IS_MAC = platform.system() == "Darwin"
IS_WIN = platform.system() == "Windows"

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
    "matplotlib",      # spectrogram rendering
    # yt_dlp removed: URL-import feature deleted (unreliable anti-bot evasion).
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
    "app.transcribe_mt3",
    "app.rhythm",
    "app.score_builder",
    "app.instrument_id",
    "app.separation",
    "app.pitch_crepe",
    "app.spectrogram",
    "app.chord_detect",
    "app.guitar_tab",
    "app.section_detect",
    "app.multi_instrument",
    "app.user_profile",
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
        # matplotlib intentionally NOT excluded — spectrogram rendering needs it
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

# Resolve the icon file per-platform. PyInstaller wants .ico for Win, .icns for Mac.
icon_path = None
if IS_WIN and (SPEC_DIR / "melody-sheet.ico").exists():
    icon_path = str(SPEC_DIR / "melody-sheet.ico")
elif IS_MAC and (SPEC_DIR / "melody-sheet.icns").exists():
    icon_path = str(SPEC_DIR / "melody-sheet.icns")

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
    # Console=True on Windows leaves a black cmd window for logs; on macOS the
    # equivalent would pop a Terminal.app which feels unprofessional, so we go
    # windowed there. The launcher tees stdout/stderr to a log file regardless.
    console=not IS_MAC,
    icon=icon_path,
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

# macOS: wrap the COLLECT output in a proper .app bundle so users get a
# double-clickable icon in /Applications instead of a raw onedir tree.
if IS_MAC:
    bundle = BUNDLE(
        coll,
        name="MelodySheet.app",
        icon=icon_path,
        bundle_identifier="com.melodysheet.app",
        version="0.1.0",
        info_plist={
            "CFBundleName": "MelodySheet",
            "CFBundleDisplayName": "小提琴旋律谱",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            # Ensure the app is treated as a regular GUI app, not a daemon.
            "LSBackgroundOnly": False,
            "LSUIElement": False,
            # Required so Apple Silicon macs treat this as a native ARM bundle
            # when the PyInstaller binary itself is arm64.
            "LSMinimumSystemVersion": "11.0",
            # Prevent the system from indexing storage / logs.
            "NSSupportsAutomaticTermination": True,
        },
    )
