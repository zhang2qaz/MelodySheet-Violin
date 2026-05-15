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


def _crepe_cross_validate(
    notes: list[dict[str, Any]],
    audio_path: Path,
    *,
    pitch_disagreement_semitones: float = 1.0,
    crepe_min_periodicity: float = 0.7,
) -> list[dict[str, Any]]:
    """Ensemble pitch correction: run CREPE on the audio, and for each
    Basic-Pitch note check whether CREPE's median pitch over that note's
    window agrees. When they disagree by more than `pitch_disagreement_
    semitones` AND CREPE has high confidence at that window, OVERRIDE the
    Basic-Pitch pitch with CREPE's reading.

    Why "override" not "drop": dropping reduces recall. CREPE is generally
    more accurate than BP on monophonic solo violin (it's specifically
    trained on monophonic f0 contours, while BP is polyphonic-by-default
    and sometimes locks onto the wrong overtone). When the two SOTA
    models disagree on a clearly-voiced note, CREPE's vote usually wins
    on solo instruments. When CREPE is unsure (low periodicity), defer
    to BP's choice.

    Falls back silently to passing notes through unchanged if torchcrepe
    isn't installed.
    """
    if not notes:
        return notes
    try:
        import torch
        import torchcrepe
        import numpy as np
        import soundfile as sf
    except ImportError:
        return notes

    try:
        audio, sr = sf.read(str(audio_path))
    except Exception:
        return notes
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio_tensor = torch.tensor(audio.astype("float32")).unsqueeze(0)

    hop_length = int(sr * 0.01)  # 10 ms grid
    try:
        pitch, periodicity = torchcrepe.predict(
            audio_tensor, sr,
            hop_length=hop_length,
            fmin=180.0, fmax=4000.0,
            model="tiny",
            decoder=torchcrepe.decode.viterbi,
            return_periodicity=True,
            batch_size=2048,
            device="cpu",
        )
    except Exception:
        return notes

    pitch_np = pitch[0].numpy()
    period_np = periodicity[0].numpy()
    # Convert Hz to MIDI
    valid = (pitch_np > 0) & np.isfinite(pitch_np)
    midi_np = np.full_like(pitch_np, np.nan)
    midi_np[valid] = 69 + 12 * np.log2(pitch_np[valid] / 440.0)
    frame_times = np.arange(len(pitch_np)) * hop_length / sr

    corrected = []
    for note in notes:
        start = float(note["start_time"])
        end = float(note["end_time"])
        # Frames whose center is inside [start+10ms, end-10ms] -- skip the
        # attack/release transients which CREPE handles less reliably.
        margin = 0.01
        mask = (frame_times >= start + margin) & (frame_times <= end - margin)
        if not mask.any():
            corrected.append(note)
            continue
        period_in_window = period_np[mask]
        midi_in_window = midi_np[mask]
        confident = period_in_window > crepe_min_periodicity
        if not confident.any():
            corrected.append(note)
            continue
        crepe_midi = float(np.median(midi_in_window[confident]))
        if not np.isfinite(crepe_midi):
            corrected.append(note)
            continue
        bp_midi = int(note["midi_number"])
        diff = crepe_midi - bp_midi
        if abs(diff) >= pitch_disagreement_semitones:
            # Override with CREPE's rounded midi.
            new_midi = int(round(crepe_midi))
            new_note = {
                **note,
                "midi_number": new_midi,
                "pitch": _midi_to_name(new_midi),
                "crepe_override": True,
                "crepe_midi_float": round(crepe_midi, 2),
            }
            corrected.append(new_note)
        else:
            corrected.append(note)
    return corrected


def _predict_at_thresholds(
    audio_path: Path,
    *,
    onset_threshold: float,
    frame_threshold: float,
    minimum_note_ms: int,
    minimum_frequency_hz: float,
    maximum_frequency_hz: float,
) -> list[tuple[float, float, int, float]]:
    """Single Basic Pitch inference pass returning raw note events.

    Prefers the ONNX model. Background: when we installed TensorFlow for
    CREPE, the newer TF version (2.20+) couldn't load Basic Pitch's
    saved-model format from disk (AttributeError on add_slot). Basic
    Pitch's predict() tries TF first by default and we'd never get to
    the working ONNX fallback. Pass the .onnx file path explicitly so
    it short-circuits to onnxruntime, which is stable across TF versions.
    """
    from basic_pitch.inference import predict, ICASSP_2022_MODEL_PATH

    # Prefer ONNX path if it exists (it almost always does in our installs).
    model_path = ICASSP_2022_MODEL_PATH
    onnx_path = Path(str(ICASSP_2022_MODEL_PATH) + ".onnx")
    if onnx_path.exists():
        model_path = onnx_path

    _model_output, _midi_data, note_events = predict(
        str(audio_path),
        model_or_model_path=model_path,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=minimum_note_ms,
        minimum_frequency=minimum_frequency_hz,
        maximum_frequency=maximum_frequency_hz,
        multiple_pitch_bends=False,
    )
    # Velocity floor 0.30: Basic Pitch's velocity is well-calibrated and
    # anything below 0.30 is almost certainly an overtone / noise / weak
    # secondary harmonic. Filtering at this layer prevents stray low-velocity
    # high-pitched notes (e.g. an octave-above-tonic overtone in vibrato)
    # from interrupting the downstream same-pitch grouping logic.
    return [
        (float(s), float(e), int(m), float(v))
        for s, e, m, v, _bend in note_events
        if e > s and v >= 0.30
    ]


def transcribe_violin_via_basic_pitch(
    audio_path: Path,
    *,
    min_note_seconds: float = 0.05,  # 50 ms: 32nd note at 150 BPM, faster than that is implausible for a violin player
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
    # SuperFlux onset cross-check (madmom DAFx 2013, Boeck & Widmer).
    #
    # Basic Pitch sometimes invents notes mid-sustain (vibrato / release
    # tail). SuperFlux uses max-filtering to suppress those false
    # vibrato onsets, so it's a useful "no-fire-here" complement: if a
    # BP note's onset has no nearby SuperFlux onset AND its velocity is
    # low AND we're confident SuperFlux is producing reliable output on
    # this audio, drop the note.
    #
    # Activation gate: only filter if SuperFlux onset density is at least
    # 0.5 onsets/sec. Below that we assume SuperFlux is silent on this
    # audio (e.g. clean synthetic test clips with soft attacks) and
    # filtering by it would hurt recall.
    # =====================================================================
    try:
        from madmom.features.onsets import SuperFluxProcessor, OnsetPeakPickingProcessor

        sf_proc = SuperFluxProcessor()
        sf_picker = OnsetPeakPickingProcessor(threshold=0.5, fps=100)
        sf_acts = sf_proc(str(audio_path))
        sf_onsets_sec = sf_picker(sf_acts)
        # How long is the audio? Use the last raw BP note's end as proxy.
        approx_duration = max(e for _s, e, _m, _v in raw) if raw else 1.0
        sf_density = len(sf_onsets_sec) / max(approx_duration, 1.0)

        if sf_density >= 0.5:
            # SuperFlux is producing onsets -- enable cross-check.
            import bisect

            def _has_sf_support(t: float, tol: float = 0.08) -> bool:
                idx = bisect.bisect_left(sf_onsets_sec, t)
                for k in (idx - 1, idx):
                    if 0 <= k < len(sf_onsets_sec) and abs(float(sf_onsets_sec[k]) - t) <= tol:
                        return True
                return False

            raw_after_sf = []
            for s, e, midi, vel in raw:
                if vel < 0.45 and not _has_sf_support(s):
                    continue
                raw_after_sf.append((s, e, midi, vel))
            # Don't let it strand us with nothing.
            if len(raw_after_sf) >= max(3, len(raw) // 3):
                raw = raw_after_sf
    except Exception:
        pass

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
        """Drop notes that are likely OVERTONES of a longer, louder note.

        A note is considered an overtone false-positive when ANOTHER note
        STRICTLY CONTAINS it in time (starts before AND ends after with
        margin) AND has noticeably higher velocity. Genuine overlapping
        notes (e.g. fast trills where Basic Pitch's onset slop causes the
        previous note's end to spill into the next note's start) are
        kept because neither contains the other -- they overlap by < 80ms.

        Velocity gap requirement (0.15) prevents dropping legitimate
        parallel notes with similar loudness; only suppresses notes where
        another is clearly the louder voice.
        """
        my_start, my_end, _my_midi, my_vel = raw_sorted[note_idx]
        for other_idx, (s, e, _m, v) in enumerate(raw_sorted):
            if other_idx == note_idx:
                continue
            strictly_contains = (
                s + 0.005 <= my_start
                and e >= my_end + 0.005
            )
            if strictly_contains and v > my_vel + 0.15:
                return False
        return True

    keepers_raw: list[tuple[float, float, int, float]] = []
    for idx in range(len(raw_sorted)):
        if is_dominant_at_onset(idx):
            keepers_raw.append(raw_sorted[idx])

    # Truncate overlapping notes -- but only when the later note clearly
    # supersedes the earlier one (significantly higher velocity). Two
    # similar-velocity notes that overlap are a DOUBLE STOP (the violin
    # convention of bowing two strings at once); both must survive.
    #
    # Without this exception the monophonic projection collapses every
    # double-stop to a single voice and the score loses half its harmony.
    DOUBLE_STOP_VEL_TOLERANCE = 0.20
    keepers_raw.sort(key=lambda x: x[0])
    truncated: list[list[float | int]] = []
    for s, e, midi, vel in keepers_raw:
        if truncated and float(truncated[-1][1]) > s + 0.005:
            prev_vel = float(truncated[-1][3])
            if vel >= prev_vel - DOUBLE_STOP_VEL_TOLERANCE:
                # Comparable velocity -> treat as double-stop, keep both at
                # their natural boundaries. Do NOT truncate previous note.
                pass
            else:
                # New note is meaningfully quieter -- it's likely an overtone
                # or accompaniment under the dominant voice. Truncate prev
                # at the new onset to preserve the monophonic line.
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

    # =====================================================================
    # CREPE ensemble cross-validation.
    #
    # Basic Pitch is the strongest open polyphonic transcriber but it
    # sometimes locks onto the wrong overtone or misses a fundamental.
    # CREPE is purpose-built for monophonic f0 tracking and is widely
    # benchmarked as more accurate than BP on solo melodic instruments.
    #
    # We use CREPE as a SECOND OPINION: for each BP note, check whether
    # CREPE's median pitch over the same time window agrees. When they
    # disagree by >=1 semitone AND CREPE is confident (periodicity >0.7),
    # override BP's pitch with CREPE's reading.
    #
    # Cost: ~3 s of CREPE inference per 5 s of audio on CPU (tiny model).
    # Skipped silently if torchcrepe isn't installed.
    # =====================================================================
    notes = _crepe_cross_validate(notes, audio_path)
    return notes


if __name__ == "__main__":
    import sys, json
    audio_path = Path(sys.argv[1])
    notes = transcribe_violin_via_basic_pitch(audio_path)
    print(f"{len(notes)} notes")
    for n in notes[:30]:
        print(f"  t={n['start_time']:5.2f}s  midi={n['midi_number']:3d} ({n['pitch']:4s})  dur={n['duration_seconds']:.2f}s  conf={n['confidence']:.2f}")
