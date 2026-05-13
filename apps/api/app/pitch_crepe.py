"""CREPE-based pitch tracking for monophonic transcription.

CREPE (https://github.com/marl/crepe) is a deep-learning pitch tracker that
significantly outperforms pYIN on fast passages and noisy audio, because it
doesn't viterbi-smooth aggressively and tracks each frame independently.
Installing it pulls TensorFlow, which is a heavy dependency, so it's optional.

When `crepe` is importable, callers should prefer `pitch_crepe.predict_f0()`
over `librosa.pyin`. The returned `(times, f0, voiced_flag, voiced_prob)`
matches the shape pYIN produces, so it slots into the existing pipeline.
"""
from __future__ import annotations

from typing import Any


def is_available() -> bool:
    try:
        import crepe  # noqa: F401
        import tensorflow  # noqa: F401
        return True
    except Exception:
        return False


def predict_f0(
    audio: Any,
    sample_rate: int,
    *,
    model_capacity: str = "tiny",
    step_size_ms: int = 10,
    confidence_threshold: float = 0.5,
    viterbi: bool = True,
) -> tuple[Any, Any, Any, Any]:
    """Run CREPE and return (times, f0_hz, voiced_flag, voiced_prob).

    `model_capacity` controls accuracy vs speed. "tiny" is fast enough for
    real-time on CPU; "full" maxes out accuracy at ~10x the cost.

    Frames where `confidence < confidence_threshold` are marked unvoiced.
    """
    import crepe
    import numpy as np

    times, frequency, confidence, _activation = crepe.predict(
        audio,
        sample_rate,
        model_capacity=model_capacity,
        viterbi=viterbi,
        step_size=step_size_ms,
        verbose=0,
    )
    voiced = confidence >= confidence_threshold
    f0 = np.where(voiced, frequency, np.nan).astype(np.float64)
    voiced_prob = confidence.astype(np.float64)
    return times.astype(np.float64), f0, voiced.astype(bool), voiced_prob


def predict_f0_on_hop_grid(
    audio: Any,
    sample_rate: int,
    hop_length: int,
    *,
    model_capacity: str = "tiny",
    confidence_threshold: float = 0.5,
) -> tuple[Any, Any, Any]:
    """Convenience wrapper that resamples CREPE's 10ms output onto the same
    frame grid pYIN uses (sample_rate / hop_length frames per second). This
    lets the downstream segmentation / onset / merge code stay identical
    between the pYIN and CREPE paths.
    """
    import numpy as np

    step_ms = max(2, int(round(1000 * hop_length / sample_rate)))
    times, f0, voiced, voiced_prob = predict_f0(
        audio,
        sample_rate,
        model_capacity=model_capacity,
        step_size_ms=step_ms,
        confidence_threshold=confidence_threshold,
    )
    expected_frames = int(np.ceil(len(audio) / hop_length))
    if len(f0) > expected_frames:
        f0 = f0[:expected_frames]
        voiced = voiced[:expected_frames]
        voiced_prob = voiced_prob[:expected_frames]
    elif len(f0) < expected_frames:
        pad = expected_frames - len(f0)
        f0 = np.concatenate([f0, np.full(pad, np.nan)])
        voiced = np.concatenate([voiced, np.zeros(pad, dtype=bool)])
        voiced_prob = np.concatenate([voiced_prob, np.zeros(pad)])
    return f0, voiced, voiced_prob
