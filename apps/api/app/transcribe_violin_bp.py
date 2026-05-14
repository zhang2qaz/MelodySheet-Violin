"""Transcribe a violin recording using Basic Pitch + greedy monophonic
melody extraction.

This is the replacement for the pYIN-based monophonic path in
transcribe_mono.py. pYIN works on clean synthetic audio but degrades
sharply on real recordings with vibrato, reverb, and bow noise --
voiced_prob drops to 0.3 on the most important notes (the accents
with strong vibrato), so any voicing-prob-based filter loses them.

Basic Pitch is a CNN trained by Spotify on real-world recordings
(MAESTRO, MedleyDB, Slakh, GuitarSet etc.). It outputs a polyphonic
note list with per-note confidence and velocity. We post-process
to a single monophonic line by sweeping through time and at each
moment keeping the note with the highest velocity among those
currently sounding.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _midi_to_name(midi_number: int) -> str:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return f"{names[midi_number % 12]}{midi_number // 12 - 1}"


def transcribe_violin_via_basic_pitch(
    audio_path: Path,
    *,
    min_note_seconds: float = 0.08,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_frequency_hz: float = 180.0,   # ~ G3 (violin's lowest open string)
    maximum_frequency_hz: float = 4000.0,  # well above violin's practical top
) -> list[dict[str, Any]]:
    """Run Basic Pitch on a wav/mp3 and return a monophonic note list in
    the schema our existing pipeline expects (pitch, midi_number,
    start_time, end_time, duration_seconds, duration_label, confidence).
    """
    from basic_pitch.inference import predict, ICASSP_2022_MODEL_PATH

    _model_output, _midi_data, note_events = predict(
        str(audio_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=int(min_note_seconds * 1000),
        minimum_frequency=minimum_frequency_hz,
        maximum_frequency=maximum_frequency_hz,
        multiple_pitch_bends=False,
    )

    # note_events: list of (start_sec, end_sec, midi, velocity, pitch_bend_array)
    raw = [
        (float(s), float(e), int(m), float(v))
        for s, e, m, v, _bend in note_events
        if e > s and v > 0
    ]
    if not raw:
        return []

    # =====================================================================
    # Greedy monophonic melody extraction.
    #
    # Basic Pitch is polyphonic. For a target like violin (monophonic by
    # nature) we collapse the output to a single voice by sweeping a
    # cursor through time and, at each moment, keeping the loudest
    # currently-active note. This naturally captures the "lead voice"
    # in a recording even when overtones / accompaniment are detected
    # by Basic Pitch as additional notes.
    # =====================================================================
    events: list[tuple[float, str, int, float]] = []
    for s, e, midi, vel in raw:
        events.append((s, "on", midi, vel))
        events.append((e, "off", midi, vel))
    # 'off' before 'on' at the same timestamp so a note that ends exactly
    # when another starts doesn't drag.
    events.sort(key=lambda x: (x[0], 0 if x[1] == "off" else 1))

    active: dict[int, float] = {}  # midi -> velocity
    segments: list[tuple[float, float, int, float]] = []
    prev_t: float | None = None
    prev_winner: tuple[int, float] | None = None
    for t, kind, midi, vel in events:
        if prev_winner is not None and prev_t is not None and t > prev_t + 1e-4:
            segments.append((prev_t, t, prev_winner[0], prev_winner[1]))
        if kind == "on":
            active[midi] = vel
        else:
            active.pop(midi, None)
        if active:
            winner_midi = max(active.keys(), key=lambda m: active[m])
            prev_winner = (winner_midi, active[winner_midi])
        else:
            prev_winner = None
        prev_t = t

    # Merge consecutive same-pitch segments (the "winner" can flicker on
    # near-simultaneous note onsets at the same pitch).
    merged: list[list[float | int]] = []
    for s, e, midi, vel in segments:
        if merged and merged[-1][2] == midi and float(merged[-1][1]) >= s - 0.05:
            merged[-1][1] = e
            merged[-1][3] = max(float(merged[-1][3]), vel)
        else:
            merged.append([s, e, midi, vel])

    # Drop tiny fragments (< min_note_seconds). These are usually
    # transient overtone catches that the merge step couldn't absorb.
    keepers = [seg for seg in merged if (seg[1] - seg[0]) >= min_note_seconds]

    # Convert to the pipeline's note schema.
    notes: list[dict[str, Any]] = []
    for index, (s, e, midi, vel) in enumerate(keepers, start=1):
        midi_i = int(midi)
        notes.append(
            {
                "index": index,
                "start_time": round(float(s), 4),
                "end_time": round(float(e), 4),
                "duration_seconds": round(float(e) - float(s), 4),
                "duration_label": "quarter",
                "pitch": _midi_to_name(midi_i),
                "midi_number": midi_i,
                # Use Basic Pitch's velocity as our confidence proxy.
                # Velocity is well-calibrated to "how loud / how sure".
                "confidence": round(min(max(float(vel), 0.0), 1.0), 3),
                "pitch_bend_cents": 0.0,
                "pitch_bend_direction": None,
            }
        )
    return notes


if __name__ == "__main__":
    import sys, json
    audio_path = Path(sys.argv[1])
    notes = transcribe_violin_via_basic_pitch(audio_path)
    print(f"{len(notes)} notes")
    for n in notes[:30]:
        print(f"  t={n['start_time']:5.2f}s  midi={n['midi_number']:3d} ({n['pitch']:4s})  dur={n['duration_seconds']:.2f}s  conf={n['confidence']:.2f}")
