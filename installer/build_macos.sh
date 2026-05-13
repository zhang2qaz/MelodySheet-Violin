#!/usr/bin/env bash
# Build the MelodySheet macOS installer (.dmg) end-to-end.
#
# Run from the repo root on a Mac:
#   bash installer/build_macos.sh
#
# Outputs:
#   dist/MelodySheet.app                       (PyInstaller bundle)
#   installer/out/MelodySheet-macOS.dmg        (final installer)
#
# Prerequisites (one-time install):
#   brew install python@3.11 node ffmpeg create-dmg
#
# Optional env vars:
#   SKIP_FFMPEG=1     # reuse already-vendored ffmpeg
#   SKIP_WEB=1        # reuse apps/web/out
#   SKIP_BACKEND=1    # reuse dist/MelodySheet.app
set -euo pipefail

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
WEB_DIR="$REPO_ROOT/apps/web"
VENV="$API_DIR/.venv-build"
FFMPEG_DIR="$SCRIPT_DIR/vendored/ffmpeg"
OUT_DIR="$SCRIPT_DIR/out"
mkdir -p "$OUT_DIR"

section() {
    echo
    echo "==> $1"
}

require() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required tool: $1" >&2
        echo "Install with: $2" >&2
        exit 1
    }
}

section "Verifying build prerequisites"
require python3 "brew install python@3.11"
require npm "brew install node"
require create-dmg "brew install create-dmg"

# ---------------------------------------------------------------------------
section "Preparing Python venv"
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools >/dev/null
"$VENV/bin/python" -m pip install -r "$API_DIR/requirements.txt"
"$VENV/bin/python" -m pip install pyinstaller "basic-pitch[onnx]"

# ---------------------------------------------------------------------------
if [[ -z "${SKIP_FFMPEG:-}" && ! -x "$FFMPEG_DIR/ffmpeg" ]]; then
    section "Vendoring ffmpeg (static macOS binary)"
    mkdir -p "$FFMPEG_DIR"
    # evermeet.cx publishes static macOS ffmpeg builds for both arm64 and x86_64.
    case "$(uname -m)" in
        arm64)  FFMPEG_URL="https://www.osxexperts.net/ffmpeg71arm.zip" ;;
        x86_64) FFMPEG_URL="https://www.osxexperts.net/ffmpeg71intel.zip" ;;
        *) echo "Unsupported arch $(uname -m)"; exit 1 ;;
    esac
    tmp=$(mktemp -d)
    echo "  downloading $FFMPEG_URL"
    curl -L "$FFMPEG_URL" -o "$tmp/ffmpeg.zip"
    unzip -q "$tmp/ffmpeg.zip" -d "$tmp/extract"
    cp "$tmp/extract/ffmpeg" "$FFMPEG_DIR/ffmpeg"
    chmod +x "$FFMPEG_DIR/ffmpeg"
    rm -rf "$tmp"
    echo "  vendored at $FFMPEG_DIR/ffmpeg"
fi

# ---------------------------------------------------------------------------
if [[ -z "${SKIP_WEB:-}" ]]; then
    section "Building frontend (Next.js static export)"
    pushd "$WEB_DIR" >/dev/null
    npm ci
    NEXT_OUTPUT=export NEXT_PUBLIC_API_BASE_URL="" npm run build
    popd >/dev/null
fi

# ---------------------------------------------------------------------------
if [[ -z "${SKIP_BACKEND:-}" ]]; then
    section "Freezing backend with PyInstaller (.app bundle)"
    pushd "$REPO_ROOT" >/dev/null
    rm -rf build dist
    "$VENV/bin/python" -m PyInstaller --clean --noconfirm "$SCRIPT_DIR/melody-sheet.spec"
    popd >/dev/null
fi

APP_PATH="$REPO_ROOT/dist/MelodySheet.app"
if [[ ! -d "$APP_PATH" ]]; then
    echo "ERROR: PyInstaller did not produce $APP_PATH" >&2
    exit 1
fi
echo "  built $APP_PATH"

# ---------------------------------------------------------------------------
section "Building DMG installer"
DMG_OUT="$OUT_DIR/MelodySheet-macOS.dmg"
rm -f "$DMG_OUT"
create-dmg \
    --volname "MelodySheet" \
    --volicon "$SCRIPT_DIR/melody-sheet.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "MelodySheet.app" 150 200 \
    --app-drop-link 450 200 \
    --no-internet-enable \
    "$DMG_OUT" \
    "$APP_PATH" \
    || {
        # create-dmg sometimes exits non-zero on cosmetic warnings; verify the
        # output file exists before declaring failure.
        if [[ ! -f "$DMG_OUT" ]]; then
            echo "ERROR: create-dmg failed to produce $DMG_OUT" >&2
            exit 1
        fi
    }

size_mb=$(du -m "$DMG_OUT" | awk '{print $1}')
echo
echo "Built: $DMG_OUT  (${size_mb} MB)"
echo
echo "To distribute:"
echo "  1) (optional) Code-sign + notarize for Gatekeeper-clean install"
echo "     codesign --deep --force --options runtime --sign 'Developer ID Application: NAME' $APP_PATH"
echo "     xcrun notarytool submit $DMG_OUT --keychain-profile mynotary --wait"
echo "  2) Upload $DMG_OUT to 闲鱼 / 微信小商店 / GitHub Releases"
