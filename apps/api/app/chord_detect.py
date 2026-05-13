"""Chord detection via chroma + template matching.

Inputs: audio array + sample rate + beats (for beat-synchronous chord changes).
Output: a list of {start_time, end_time, chord, root, quality, confidence}.

The algorithm:
  1. Compute CQT-based chroma (12-bin pitch class energy over time)
  2. Median-filter chroma along the time axis so transient noise doesn't
     trigger spurious chord changes
  3. Aggregate chroma to beat windows (one chord per beat by default)
  4. For each beat window, score it against 24 chord templates
     (12 major + 12 minor) plus optional dim/aug/sus2/sus4/7
  5. Pick the highest-scoring template; merge consecutive identical chords

This is a deliberately simple, robust approach. It matches what tools like
chordino / autochord use, with similar accuracy on common pop/rock music.
"""
from __future__ import annotations

from typing import Any


NOTE_NAMES = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")


def _chord_templates() -> list[tuple[str, list[float]]]:
    """Return (label, 12-bin template) pairs covering common qualities."""
    # Base pitch-class sets for each quality (root = 0)
    base = {
        "":      [0, 4, 7],          # major triad
        "m":     [0, 3, 7],          # minor triad
        "7":     [0, 4, 7, 10],
        "maj7":  [0, 4, 7, 11],
        "m7":    [0, 3, 7, 10],
        "sus2":  [0, 2, 7],
        "sus4":  [0, 5, 7],
        "dim":   [0, 3, 6],
        "aug":   [0, 4, 8],
    }
    templates: list[tuple[str, list[float]]] = []
    for root in range(12):
        for quality, intervals in base.items():
            template = [0.0] * 12
            for interval in intervals:
                template[(root + interval) % 12] = 1.0
            label = f"{NOTE_NAMES[root]}{quality}"
            templates.append((label, template))
    return templates


_TEMPLATES = _chord_templates()


def detect_chords(
    audio: Any,
    sample_rate: int,
    beats: list[float] | None = None,
    *,
    min_seconds_per_chord: float = 0.3,
    confidence_floor: float = 0.4,
) -> list[dict[str, Any]]:
    try:
        import librosa
        import numpy as np
    except Exception:
        return []

    if audio is None or len(audio) == 0:
        return []

    hop_length = 512
    chroma = librosa.feature.chroma_cqt(
        y=audio, sr=sample_rate, hop_length=hop_length, n_chroma=12, n_octaves=6, bins_per_octave=36
    )
    # Smooth across time (median filter ~250 ms)
    smooth_window = max(1, int(0.25 * sample_rate / hop_length))
    if smooth_window > 1 and chroma.shape[1] > smooth_window:
        from scipy.ndimage import median_filter

        chroma = median_filter(chroma, size=(1, smooth_window))

    # Beat-synchronous segmentation. Fall back to a uniform 1-second grid.
    if beats and len(beats) >= 2:
        beat_frames = librosa.time_to_frames(beats, sr=sample_rate, hop_length=hop_length)
        beat_frames = np.unique(np.clip(beat_frames, 0, chroma.shape[1] - 1))
    else:
        step = max(1, int(0.5 * sample_rate / hop_length))
        beat_frames = np.arange(0, chroma.shape[1], step)

    if len(beat_frames) < 2:
        return []

    segments: list[dict[str, Any]] = []
    template_matrix = np.array([tpl for _, tpl in _TEMPLATES])  # (N_templates, 12)
    template_labels = [lbl for lbl, _ in _TEMPLATES]

    for idx in range(len(beat_frames) - 1):
        start_f = int(beat_frames[idx])
        end_f = int(beat_frames[idx + 1])
        if end_f - start_f < 1:
            continue
        segment_chroma = chroma[:, start_f:end_f].mean(axis=1)
        norm = float(np.linalg.norm(segment_chroma))
        if norm < 1e-6:
            continue
        segment_chroma = segment_chroma / norm
        # Cosine similarity vs each template (templates are 0/1, normalize too)
        template_norms = np.linalg.norm(template_matrix, axis=1, keepdims=True)
        normalized_templates = template_matrix / np.clip(template_norms, 1e-6, None)
        scores = normalized_templates @ segment_chroma  # (N_templates,)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])
        if best_score < confidence_floor:
            continue
        label = template_labels[best_idx]
        root, quality = _split_label(label)
        start_t = float(librosa.frames_to_time(start_f, sr=sample_rate, hop_length=hop_length))
        end_t = float(librosa.frames_to_time(end_f, sr=sample_rate, hop_length=hop_length))
        segments.append({
            "start_time": round(start_t, 4),
            "end_time": round(end_t, 4),
            "chord": label,
            "root": root,
            "quality": quality,
            "confidence": round(best_score, 3),
        })

    # Merge consecutive identical chords + drop micro-chords below threshold.
    merged: list[dict[str, Any]] = []
    for seg in segments:
        if merged and merged[-1]["chord"] == seg["chord"]:
            merged[-1]["end_time"] = seg["end_time"]
            merged[-1]["confidence"] = round(max(merged[-1]["confidence"], seg["confidence"]), 3)
        else:
            merged.append(dict(seg))
    merged = [m for m in merged if (m["end_time"] - m["start_time"]) >= min_seconds_per_chord]
    return merged


def _split_label(label: str) -> tuple[str, str]:
    for cut in range(len(label), 0, -1):
        head = label[:cut]
        if head in NOTE_NAMES:
            return head, label[cut:] or "maj"
    return label, "maj"
