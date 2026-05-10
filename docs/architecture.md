# Architecture

## Frontend

The frontend is a Next.js App Router application in `apps/web`.

- `app/page.tsx` renders the upload workflow.
- `app/jobs/[jobId]/page.tsx` renders processing and completed job states.
- `components/` contains upload, status, notation, playback, numbered notation, downloads, and note editor components.
- `lib/api.ts` centralizes backend calls.
- `lib/music.ts` contains browser-safe note helpers for MIDI number, pitch name, and transposition.

The frontend polls `GET /api/jobs/{job_id}` until the job is completed or failed. It does not invent successful output. Result views are shown only when backend-generated files are present.

## Backend

The backend is a FastAPI app in `apps/api`.

- `main.py` exposes HTTP endpoints.
- `app/config.py` loads environment configuration.
- `app/job_store.py` creates folders and reads/writes job metadata.
- `app/music_processing.py` owns ffmpeg conversion, Basic Pitch transcription, music21 parsing/export, numbered notation, and regeneration from edited notes.
- `app/models.py` defines request/response schemas.

## Processing Pipeline

1. Upload is validated and saved to `storage/uploads/{job_id}/original.{ext}`.
2. Job metadata is created in `storage/jobs/{job_id}.json`.
3. Background processing updates status and progress:
   - `uploaded`
   - `converting`
   - `transcribing`
   - `postprocessing`
   - `completed`
   - `failed`
4. ffmpeg converts the original file to mono WAV at `storage/converted/{job_id}/input.wav`.
5. Spotify Basic Pitch transcribes the WAV and writes MIDI to `storage/outputs/{job_id}/melody.mid`.
6. music21 parses MIDI, estimates tempo and key, extracts notes, writes MusicXML, writes editable notes JSON, and writes numbered notation JSON.
7. Completed jobs expose safe file URLs through `GET /api/files/{job_id}/{filename}`.

Basic Pitch stdout/stderr is captured to `storage/outputs/{job_id}/basic_pitch.log` for local troubleshooting. The log is not exposed through the public file endpoint.

## Storage Structure

```text
storage/
  uploads/{job_id}/original.{ext}
  converted/{job_id}/input.wav
  outputs/{job_id}/melody.mid
  outputs/{job_id}/melody.musicxml
  outputs/{job_id}/numbered.json
  outputs/{job_id}/notes.json
  jobs/{job_id}.json
```

## Known Limitations

- Basic Pitch is strongest with clear lead melodies; dense accompaniment may produce noisy output.
- Basic Pitch MIDI does not always provide a reliable confidence score, so the backend derives confidence from MIDI velocity when available.
- Key analysis is approximate and deterministic, not a full harmonic analysis.
- Numbered notation is simplified and currently optimized for readable practice output, not publication-grade engraving.
- ffmpeg and Basic Pitch are local dependencies and must be installed before end-to-end transcription works.
- Basic Pitch model loading depends on the local runtime. macOS can use CoreML; Linux deployments should install a supported runtime such as ONNX or TensorFlow and can override the model path with `MELODYSHEET_BASIC_PITCH_MODEL_PATH`.
