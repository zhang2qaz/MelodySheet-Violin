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


def _predict_at_thresholds(
    audio_path: Path,
    *,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_ms: int,
    minimum_frequency_hz: float,
    maximum_frequency_hz: float,
) -> list[tuple[float, float, int, float]]:
    """Single Basic Pitch inference pass returning raw note events."""
    from basic_pitch.inference import predict, ICASSP_2022_MODEL_PATH

    _model_output, _midi_data, note_events = predict(
        str(audio_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_ms,
        minimum_frequency=minimum_frequency_hz,
        maximum_frequency=maximum_frequency_hz,
        multiple_pitch_bends=False,
    )
    return [
        (float(s), float(e), int(m), float(v))
        for s, e, m, v, _bend in note_events
        if e > s and v > 0
    ]


def transcribe_violin_via_basic_pitch(
    audio_path: Path,
    *,
    min_note_seconds: float = 0.08,
    onset_threshold: float = 0.3,
    frame_threshold: float = 0.2,
    minimum_frequency_hz: float = 180.0,   # ~ G3 (violin's lowest open string)
    maximum_frequency_hz: float = 4000.0,  # well above violin's practical top
) -> list[dict[str, Any]]:
    """Run Basic Pitch on a wav/mp3 and return a monophonic note list in
    the schema our existing pipeline expects.

    THRESHOLD CALIBRATION (don't blindly raise these without a test panel):
    --------------------------------------------------------------------
    Basic Pitch's documented defaults are onset=0.5, frame=0.3. Those are
    tuned for the studio-quality recordings in MAESTRO/Slakh -- loud,
    well-mic'd, low noise floor. On a quiet user-recorded violin clip
    (RMS median 0.10, no compression, room mic) those defaults gate out
    ~80 % of real notes. Observed empirically on an 8 s clip:

        onset=0.50 frame=0.30  ->  7 events,  4 unique pitches  (too few)
        onset=0.30 frame=0.20  -> 18 events, 10 unique pitches  (good)
        onset=0.20 frame=0.15  -> 66 events                     (too many)

    Adaptive retry below catches the rare case where even 0.30/0.20
    gates too aggressively (very quiet pianissimo passages).
    """
    minimum_note_ms = int(min_note_seconds * 1000)

    # First pass at standard thresholds.
    raw = _predict_at_thresholds(
        audio_path,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_ms=minimum_note_ms,
        minimum_frequency_hz=minimum_frequency_hz,
        maximum_frequency_hz=maximum_frequency_hz,
    )

    # Adaptive retry: if first pass is suspiciously sparse (< 0.5 notes per
    # second), drop thresholds and try again. Real performances have >=1
    # note/sec; <0.5 means we almost certainly missed the bulk.
    if raw:
        approx_audio_seconds = max(e for _s, e, _m, _v in raw)
        notes_per_sec = len(raw) / max(approx_audio_seconds, 1.0)
        if notes_per_sec < 0.5:
            retry = _predict_at_thresholds(
                audio_path,
                onset_threshold=0.2,
                frame_threshold=0.15,
                minimum_note_ms=minimum_note_ms,
                minimum_frequency_hz=minimum_frequency_hz,
                maximum_frequency_hz=maximum_frequency_hz,
            )
            if len(retry) > len(raw) * 2:
                raw = retry

    if not raw:
        return []

    # =====================================================================
    # Monophonic projection: trust Basic Pitch's note boundaries.
    #
    # Background: the previous algorithm was a sweep-event-based "winner at
    # each instant" approach that merged adjacent same-pitch segments
    # within 50 ms. That correctly handled the case where Basic Pitch
    # falsely detects an overtone as a brief separate note, but it also
    # WRONGLY collapsed legitimate consecutive same-pitch notes (e.g. 8
    # repeated C5 quarter-notes) into a single long sustain. On the
    # synthetic corpus's repeated-note test, recall fell from 8/8 to 1/8.
    #
    # New algorithm:
    #   For each Basic Pitch note (which has reliable onset/offset times),
    #   ask "was this note the loudest pitch active at its own onset?"
    #   - If yes, keep it as-is (its boundaries are the truth).
    #   - If no, discard it (it's an overtone or accompaniment that was
    #     drowned out by a higher-velocity note at the same moment).
    #
    # This preserves note counts (a 16th-note tremolo of 8 C5s stays 8
    # separate notes) while still removing overtone false-positives that
    # appear under louder main-voice notes.
    # =====================================================================
    # Sort by onset time; tie-break by descending velocity so the loudest
    # note at a shared onset wins in case of pure ties.
    raw_sorted = sorted(raw, key=lambda evt: (evt[0], -evt[3]))

    def is_dominant_at_onset(note_idx: int) -> bool:
        """Check whether note `note_idx` has the highest velocity among all
        Basic Pitch events whose time interval contains this note's onset."""
        my_start, _my_end, _my_midi, my_vel = raw_sorted[note_idx]
        for other_idx, (s, e, _m, v) in enumerate(raw_sorted):
            if other_idx == note_idx:
                continue
            # Does `other` cover `my_start`? Use a small tolerance so a note
            # that starts at exactly my_start (not yet sounding at my onset)
            # doesn't count as covering it.
            if s + 0.005 <= my_start <= e - 0.005 and v > my_vel:
                return False
        return True

    keepers_raw: list[tuple[float, float, int, float]] = []
    for idx in range(len(raw_sorted)):
        if is_dominant_at_onset(idx):
            keepers_raw.append(raw_sorted[idx])

    # Truncate overlapping monophonic notes. If two surviving notes overlap
    # in time, shorten the earlier one so it ends when the later one begins.
    keepers_raw.sort(key=lambda x: x[0])
    truncated: list[list[float | int]] = []
    for s, e, midi, vel in keepers_raw:
        if truncated and float(truncated[-1][1]) > s + 0.005:
            truncated[-1][1] = s
        truncated.append([float(s), float(e), int(midi), float(vel)])

    # =====================================================================
    # Merge vibrato sub-fragments while preserving repeated-note structure.
    #
    # Basic Pitch sometimes splits a single sustained vibrato note into
    # several abutting sub-notes at the same pitch (e.g. for a 0.5 s A4
    # with 5 Hz vibrato it emits 3 sub-notes of ~220/140/130 ms). These
    # MUST be merged back -- they're not a tremolo or repeated articulation,
    # they're a single bowed note with pitch wobble.
    #
    # Meanwhile, a true repeated-note passage (e.g. 8 abutting C5 quarter
    # notes from a tremolo or "bow change") produces sub-notes of ~500 ms
    # each -- the listener hears them as separate articulations and
    # would expect 8 distinct noteheads on the score.
    #
    # Discriminator: vibrato sub-fragments are SHORT (< 200 ms), while real
    # repeated notes are typically >= 200 ms. So merge a chain of abutting
    # same-pitch notes only if at least one of them is < 200 ms.
    # (200 ms = an 8th note at 150 BPM, well below most violin
    # articulations; vibrato sub-fragments are reliably below this.)
    # =====================================================================
    VIBRATO_SUBNOTE_THRESHOLD = 0.20  # seconds
    ABUT_GAP_THRESHOLD = 0.03         # seconds; consider notes "abutting" if gap <= this

    # First pass: walk through and form groups of consecutive same-pitch
    # abutting notes.
    groups: list[list[list[float | int]]] = []
    for seg in truncated:
        if (
            groups
            and groups[-1][-1][2] == seg[2]
            and seg[0] - float(groups[-1][-1][1]) <= ABUT_GAP_THRESHOLD
        ):
            groups[-1].append(seg)
        else:
            groups.append([seg])

    keepers: list[list[float | int]] = []
    for group in groups:
        if len(group) == 1:
            keepers.append(group[0])
            continue
        # Decision: any sub-note shorter than the vibrato threshold => merge.
        has_short = any(
            (float(g[1]) - float(g[0])) < VIBRATO_SUBNOTE_THRESHOLD for g in group
        )
        if has_short:
            merged = [
                float(group[0][0]),
                float(group[-1][1]),
                int(group[0][2]),
                max(float(g[3]) for g in group),
            ]
            keepers.append(merged)
        else:
            keepers.extend(group)

    # Drop tiny notes (likely fragments that survived all filters).
    keepers = [seg for seg in keepers if (float(seg[1]) - float(seg[0])) >= min_note_seconds]

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
