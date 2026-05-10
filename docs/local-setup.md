# Local Setup

## Backend

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Required Python packages include FastAPI, python-multipart, Basic Pitch, music21, pytest, and httpx.

Basic Pitch ships model files but still needs a runtime that can load one of them. macOS can use the bundled CoreML path. If your platform cannot load CoreML, install `basic-pitch[onnx]` or `basic-pitch[tf]` and set `MELODYSHEET_BASIC_PITCH_MODEL_PATH` if needed.

## ffmpeg

The backend calls `ffmpeg` as a subprocess. Install it before running a real transcription job.

macOS:

```bash
brew install ffmpeg
```

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

## Frontend

```bash
cd apps/web
npm install
npm run dev
```

The frontend defaults to `http://localhost:8000` for the API. Override it with:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## Test Audio

Generate a short synthetic WAV:

```bash
python scripts/generate-test-audio.py storage/uploads/test-melody.wav
```

Then upload that file in the web app. Synthetic sine waves are useful for testing the pipeline, but they are not a substitute for testing real user recordings.
