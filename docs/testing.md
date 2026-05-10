# Testing

## Automated Backend Tests

Run:

```bash
cd apps/api
pytest
```

Covered cases:

- Upload form validation.
- Unsupported file type rejection.
- Empty file rejection.
- Job creation.
- Job metadata creation.
- ffmpeg missing dependency handling.
- MIDI-to-MusicXML conversion with music21.
- Numbered notation generation.
- Regenerate endpoint.

## Manual Frontend QA Checklist

- Upload form renders on the home page.
- Drag-and-drop highlights the upload box.
- Invalid file type shows a warning before upload.
- Accepted file types are shown: `mp3`, `wav`, `m4a`.
- Max file size and short-clip recommendation are visible.
- Legal copy says users should upload audio they have the right to use.
- Uploading creates a job and navigates to the job page.
- Processing states show progress, step, and friendly message.
- Failed jobs show: “Transcription failed. Try a shorter, clearer recording with less background accompaniment.”
- Completed result shows original audio player when available.
- MusicXML renders in OpenSheetMusicDisplay.
- If MusicXML rendering fails, the page still provides a MusicXML download.
- Numbered notation displays key, meter, tempo, and scale-degree rows.
- Generated melody playback starts and stops.
- Download links render for MIDI, MusicXML, numbered JSON, and editable notes JSON.
- Note editor updates local state for pitch and duration changes.
- Delete removes a note from the local table.
- Transpose up/down changes pitch names and MIDI numbers.
- Regenerate Sheet posts edited notes to the backend and reloads updated files.
- Violin range warning appears when any note is below G3.

## Sample Audio Recommendations

Best MVP inputs:

- Clear violin melody.
- Clear vocal melody.
- Single instrument melody.
- Humming or singing recording.
- Short clip under 60 seconds with an obvious lead melody.

Avoid:

- Dense full-band mixes.
- Heavy reverb or noise.
- Long files.
- Protected or encrypted platform audio.

## Expected MVP Limitations

- Transcription may split or merge notes incorrectly.
- Key detection is approximate.
- Numbered notation is simplified.
- Browser playback uses the extracted note sequence rather than a full MIDI synthesizer.
- End-to-end audio processing requires local ffmpeg and Basic Pitch installation.
