#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Setting up MelodySheet Violin"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg was not found in PATH. Install it before running real transcription jobs." >&2
fi

cd "$ROOT_DIR/apps/api"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd "$ROOT_DIR"
npm install

mkdir -p storage/uploads storage/converted storage/outputs storage/jobs

echo "Setup complete."
echo "Backend: cd apps/api && source .venv/bin/activate && uvicorn main:app --reload --port 8000"
echo "Frontend: npm --prefix apps/web run dev"
