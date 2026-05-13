from __future__ import annotations

from typing import Any


# Quarter-length values for note durations we know how to render and the matching
# duration_label that EditableNote's pydantic validator accepts.
DURATION_QUARTERS_TO_LABEL: list[tuple[float, str]] = [
    (4.0, "whole"),
    (2.0, "half"),
    (1.0, "quarter"),
    (0.5, "eighth"),
    (0.25, "sixteenth"),
]


def estimate_tempo_and_beats(audio: Any, sample_rate: int) -> tuple[float, list[float]]:
    import librosa
    import numpy as np

    onset_env = librosa.onset.onset_strength(y=audio, sr=sample_rate, aggregate=np.median)
    tempo, beats = librosa.beat.beat_track(
        onset_envelope=onset_env, sr=sample_rate, units="time", tightness=120
    )
    tempo_value = float(np.atleast_1d(tempo)[0])
    if tempo_value <= 0 or not np.isfinite(tempo_value):
        tempo_value = 90.0
    return tempo_value, [float(t) for t in beats]


def quantize_notes_to_grid(
    notes: list[dict[str, Any]],
    *,
    tempo_bpm: float,
    beats: list[float],
    subdivisions_per_beat: int = 4,
) -> list[dict[str, Any]]:
    """Snap note onsets and durations to a tempo-locked grid.

    Strategy: derive a uniform grid from detected beats; one beat is one quarter note.
    Each beat is subdivided into `subdivisions_per_beat` equal slots (16ths by default).
    Triplets are detected when the residual onset offset is closer to a third of a beat.
    """
    if not notes:
        return notes
    if tempo_bpm <= 0:
        tempo_bpm = 90.0
    if not beats or len(beats) < 2:
        # Fall back to a uniform grid from BPM.
        seconds_per_quarter = 60.0 / tempo_bpm
        beats = [i * seconds_per_quarter for i in range(0, 1024)]

    seconds_per_quarter = 60.0 / tempo_bpm
    # Build grid points as (time_seconds, quarter_position_from_start).
    grid_step_seconds = seconds_per_quarter / subdivisions_per_beat
    triplet_step_seconds = seconds_per_quarter / 3.0

    quantized: list[dict[str, Any]] = []
    for original in notes:
        start_time = float(original["start_time"])
        end_time = float(original["end_time"])
        duration_seconds = max(end_time - start_time, grid_step_seconds * 0.5)

        # Snap start time
        grid_index = round(start_time / grid_step_seconds)
        snapped_start_grid = grid_index * grid_step_seconds
        triplet_index = round(start_time / triplet_step_seconds)
        snapped_start_triplet = triplet_index * triplet_step_seconds

        residual_grid = abs(start_time - snapped_start_grid)
        residual_triplet = abs(start_time - snapped_start_triplet)
        if residual_triplet + 1e-6 < residual_grid * 0.75:
            snapped_start = snapped_start_triplet
            quarter_unit = triplet_step_seconds
            snap_residual = residual_triplet
        else:
            snapped_start = snapped_start_grid
            quarter_unit = grid_step_seconds
            snap_residual = residual_grid

        # Safety: if the snap would move the onset by more than 50 ms, the
        # tempo estimate is probably wrong (e.g. librosa returned 2× the true
        # BPM on a slow piece). Keep the raw onset instead of slamming it onto
        # a mis-aligned grid point.
        if snap_residual > 0.05:
            snapped_start = start_time

        # Snap duration to nearest whole-grid multiple, minimum 1 unit.
        duration_units = max(1, round(duration_seconds / quarter_unit))
        snapped_duration_seconds = duration_units * quarter_unit
        duration_quarters = snapped_duration_seconds / seconds_per_quarter

        # Map duration_quarters to the closest renderable label.
        duration_label = _nearest_duration_label(duration_quarters)

        quantized.append(
            {
                **original,
                "start_time": round(snapped_start, 4),
                "end_time": round(snapped_start + snapped_duration_seconds, 4),
                "duration_seconds": round(snapped_duration_seconds, 4),
                "duration_label": duration_label,
                "duration_quarters": round(duration_quarters, 4),
            }
        )

    quantized.sort(key=lambda item: (item["start_time"], item["midi_number"]))
    return quantized


def _nearest_duration_label(duration_quarters: float) -> str:
    if duration_quarters <= 0:
        return "sixteenth"
    return min(
        DURATION_QUARTERS_TO_LABEL,
        key=lambda pair: abs(pair[0] - duration_quarters),
    )[1]


def estimate_meter(beats: list[float], audio: Any, sample_rate: int) -> str:
    """Meter detection over the candidate set {2/4, 3/4, 4/4, 6/8}.

    Uses periodicity of accented beats (every 2nd / 3rd / 4th beat) measured
    against the onset envelope. Falls back to 4/4 on insufficient data.
    """
    try:
        import librosa
        import numpy as np

        if not beats or len(beats) < 6:
            return "4/4"
        onset_env = librosa.onset.onset_strength(y=audio, sr=sample_rate, aggregate=np.median)
        beat_frames = librosa.time_to_frames(beats, sr=sample_rate)
        beat_frames = beat_frames[beat_frames < len(onset_env)]
        if len(beat_frames) < 6:
            return "4/4"
        strengths = onset_env[beat_frames]

        # Score each candidate by the mean accent strength at its downbeat positions.
        # The meter whose downbeat strikes are loudest wins.
        candidates = {
            "2/4": float(np.mean(strengths[::2])),
            "3/4": float(np.mean(strengths[::3])),
            "4/4": float(np.mean(strengths[::4])),
            "6/8": float(np.mean(strengths[::6])) if len(strengths) >= 12 else 0.0,
        }
        # Slight bias toward 4/4 — most popular music is in 4. Without this
        # almost-equal candidates flip-flop run-to-run.
        candidates["4/4"] *= 1.05

        best = max(candidates, key=candidates.get)
        # Sanity: require the best to beat the runner-up by at least 8% or
        # fall back to 4/4 to avoid spurious 3/4 reads on near-uniform pieces.
        sorted_scores = sorted(candidates.values(), reverse=True)
        if sorted_scores[0] < sorted_scores[1] * 1.08:
            return "4/4"
        return best

    except Exception:
        return "4/4"
