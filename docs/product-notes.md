# Product Notes

## Product Goal

MelodySheet Violin helps users upload an audio file and automatically generate a readable melody sheet for violin or single-line melody practice. The MVP prioritizes a real audio-to-melody-sheet pipeline over visual polish.

## User Personas

- Violin beginners who need simple practice material from a melody recording.
- Music teachers who want a quick first draft of a melody sheet for students.
- Parents helping children practice familiar melodies.
- Students who want to turn humming, singing, or a solo melody clip into notes they can edit.

## MVP Scope

- User-uploaded audio only.
- Supported input formats: `mp3`, `wav`, `m4a`.
- Local FastAPI processing jobs.
- ffmpeg conversion to WAV.
- Spotify Basic Pitch transcription to MIDI.
- music21 MIDI parsing and MusicXML export.
- Simplified numbered notation JSON.
- Editable notes JSON.
- Staff notation rendering in the frontend.
- Note-sequence playback in the browser.
- Basic note correction and regeneration.
- Violin range warning for notes below G3.

## Non-Goals

- No QQ Music, Spotify streaming, Apple Music, NetEase Cloud Music, or external music platform integration.
- No DRM bypassing.
- No processing encrypted or protected streaming audio.
- No claim that the product can legally transcribe any commercial song from a streaming platform.
- No violin fingering, bowing marks, string suggestions, or advanced engraving in the MVP.
- No full polyphonic score extraction promise.

## Copyright and Platform Limitations

The UI should tell users to upload audio they have the right to use. MelodySheet Violin is designed for user-provided files, such as personal recordings, lessons, humming, singing, or licensed material. The app should not imply that users can upload protected commercial songs without permission.

## Future Roadmap

- System audio capture with explicit user permission.
- Authorized music platform integrations where licensing and API terms allow.
- Better melody isolation for vocals or lead instruments.
- Vocal/accompaniment separation.
- Violin fingering suggestions.
- Sheet editing UI.
- PDF export.
- Practice mode with looping and tempo control.
- Teacher/student workflow for assignments and corrections.
