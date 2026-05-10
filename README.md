# MelodySheet Violin

MelodySheet Violin turns a clear melody recording into an editable violin practice sheet. The MVP accepts user-uploaded audio, runs a local audio-to-MIDI transcription pipeline, generates MusicXML and simplified numbered notation, renders staff notation in the browser, supports playback, and lets users correct notes before exporting.

This is a music-learning tool for violin beginners, teachers, parents, and students who want to turn a short melody recording into a readable practice sheet.

## MVP Scope

What the app can do:

- Accept uploaded `mp3`, `wav`, and `m4a` files.
- Convert audio to mono WAV with `ffmpeg`.
- Run Spotify Basic Pitch to generate MIDI.
- Parse MIDI with `music21`.
- Export `melody.mid`, `melody.musicxml`, `numbered.json`, and `notes.json`.
- Render MusicXML in the browser with OpenSheetMusicDisplay.
- Play back the generated melody using the editable note sequence.
- Edit pitch and duration labels, delete notes, transpose by semitone, and regenerate notation.
- Warn when detected notes are below standard violin range around G3.

What the app cannot do:

- It does not integrate QQ Music, Spotify streaming, Apple Music, NetEase Cloud Music, or any other music platform.
- It does not bypass DRM or process encrypted/protected streams.
- It does not claim legal permission to transcribe commercial songs.
- It does not guarantee perfect transcription, especially for dense accompaniment or polyphonic recordings.
- It does not yet provide violin fingering, bowing marks, PDF export, or advanced sheet editing.

Upload an audio file you have the right to use. AI transcription may not be perfect, so review and correct notes before exporting.

## Repository Layout

```text
apps/
  api/   FastAPI backend and audio processing pipeline
  web/   Next.js frontend
docs/    Product, architecture, API, setup, and testing notes
scripts/ Developer helper scripts
storage/ Local uploads, converted files, outputs, and job metadata
```

## Requirements

- Python 3.9 or newer
- Node.js 20 or newer
- `ffmpeg` installed and available in `PATH`
- Spotify Basic Pitch Python package
- `music21` Python package

On macOS, install ffmpeg with:

```bash
brew install ffmpeg
```

## Backend Setup

One-command setup:

```bash
./scripts/setup.sh
```

Manual backend setup:

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

The backend uses local file storage under `storage/` by default. You can override it:

```bash
export MELODYSHEET_STORAGE_PATH=/absolute/path/to/storage
```

`requirements.txt` installs Spotify Basic Pitch, `music21`, and the supporting audio stack. On macOS, Basic Pitch can use its bundled CoreML model. On Linux or other environments, if Basic Pitch reports that no model runtime can load, install a supported runtime such as `basic-pitch[onnx]` or `basic-pitch[tf]` and optionally set `MELODYSHEET_BASIC_PITCH_MODEL_PATH` to the packaged ONNX/TF model path.

## Frontend Setup

```bash
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

If your API runs somewhere else:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## Tests

Backend:

```bash
cd apps/api
pytest
```

End-to-end API smoke test against a running backend:

```bash
python3 scripts/e2e-api-smoke.py http://127.0.0.1:8000
```

Frontend practical checks are documented in [docs/testing.md](docs/testing.md). The MVP currently favors backend automated coverage because the audio-to-sheet pipeline is the critical product risk.

## Troubleshooting

- `ffmpeg is not installed or not available in PATH.`  
  Install ffmpeg and restart the backend process.

- `Spotify Basic Pitch is not installed or could not be imported.`  
  Activate the backend virtual environment and run `pip install -r requirements.txt`.

- `Basic Pitch transcription failed.`  
  Check `storage/outputs/{job_id}/basic_pitch.log`, confirm a Basic Pitch model runtime is installed, and try a shorter, clearer melody recording.

- MusicXML download exists but staff rendering fails.  
  Download the MusicXML file and inspect it in MuseScore or another notation app. The browser renderer may reject malformed or unsupported notation, but the backend will still expose the generated file.

- Transcription quality is poor.  
  Try a shorter clip under 60 seconds with a clear single-line melody, humming, singing, or solo instrument and less background accompaniment.
