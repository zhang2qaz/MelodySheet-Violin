"""Render a spectrogram PNG from an audio array.

Used by the v2 pipeline to give users a visual feedback of what the AI
analysed — an "X-ray" of the audio that builds trust ("see, the bright
horizontal lines are the actual pitches the model picked up").
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def render_spectrogram_png(
    audio: Any,
    sample_rate: int,
    out_path: Path,
    *,
    width_px: int = 1600,
    height_px: int = 540,
) -> Path | None:
    """Save a mel-scaled log-power spectrogram to `out_path`.

    Returns the path on success or None if matplotlib/librosa aren't
    available (kept optional so the eval harness doesn't require matplotlib).
    """
    try:
        import librosa
        import matplotlib
        matplotlib.use("Agg")  # headless backend (PyInstaller + GH runner safe)
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return None

    if audio is None or len(audio) == 0:
        return None

    n_fft = 2048
    hop_length = 512
    # Use mel spectrogram — better visual contrast for music than linear STFT.
    mel = librosa.feature.melspectrogram(
        y=audio,
        sr=sample_rate,
        n_fft=n_fft,
        hop_length=hop_length,
        n_mels=128,
        fmin=55,         # A1 - covers violin/cello/bass range
        fmax=min(sample_rate // 2, 8000),
    )
    log_mel = librosa.power_to_db(mel, ref=np.max)

    fig, ax = plt.subplots(figsize=(width_px / 100, height_px / 100), dpi=100)
    librosa.display.specshow(
        log_mel,
        sr=sample_rate,
        hop_length=hop_length,
        x_axis="time",
        y_axis="mel",
        fmin=55,
        fmax=min(sample_rate // 2, 8000),
        cmap="magma",
        ax=ax,
    )
    ax.set_title("")
    ax.set_xlabel("时间 (秒)", fontsize=10)
    ax.set_ylabel("频率 (mel)", fontsize=10)
    fig.tight_layout(pad=1.5)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out_path), dpi=100, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    return None
