# API Contract

Base URL in local development: `http://localhost:8000`.

## POST `/api/jobs`

Accepts an uploaded audio file and creates a processing job.

Request:

```http
POST /api/jobs
Content-Type: multipart/form-data
```

Multipart field:

- `file`: `mp3`, `wav`, or `m4a`

Success response:

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "uploaded"
}
```

Validation errors:

- Unsupported extension.
- Empty file.
- File over configured max size.

## GET `/api/jobs/{job_id}`

Returns status and result links.

Response:

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "completed",
  "progress": 100,
  "error": null,
  "result": {
    "original_audio_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/original.wav",
    "midi_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.mid",
    "musicxml_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.musicxml",
    "numbered_json_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/numbered.json",
    "notes_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/notes.json",
    "detected_key": "C",
    "estimated_tempo": 90,
    "note_count": 24,
    "violin_range_warning": false,
    "violin_range_message": null
  }
}
```

Statuses:

- `uploaded`
- `converting`
- `transcribing`
- `postprocessing`
- `completed`
- `failed`

## GET `/api/files/{job_id}/{filename}`

Safely serves job files. Allowed filenames are:

- `original.{ext}`
- `melody.mid`
- `melody.musicxml`
- `numbered.json`
- `notes.json`

The endpoint rejects arbitrary paths and unknown filenames.

## POST `/api/jobs/{job_id}/regenerate`

Accepts edited notes and regenerates MusicXML, MIDI, numbered notation JSON, and notes JSON.

Request:

```json
{
  "notes": [
    {
      "index": 1,
      "start_time": 0.0,
      "end_time": 0.5,
      "pitch": "C4",
      "midi_number": 60,
      "duration_seconds": 0.5,
      "duration_label": "quarter",
      "confidence": 0.87
    }
  ]
}
```

Success response:

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "completed",
  "result": {
    "original_audio_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/original.wav",
    "midi_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.mid",
    "musicxml_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.musicxml",
    "numbered_json_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/numbered.json",
    "notes_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/notes.json",
    "detected_key": "C",
    "estimated_tempo": 90,
    "note_count": 1,
    "violin_range_warning": false,
    "violin_range_message": null
  }
}
```
