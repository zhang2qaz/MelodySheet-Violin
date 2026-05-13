"""Drum transcription via spectral-band onset detection.

We don't have a dedicated drum model (MT3-style); instead we use the
classical 3-band onset trick that's been the default for indie music
transcribers since the 2000s:

  - kick:  20-150 Hz dominant transient (low band)
  - snare: 150-800 Hz, plus high-frequency noise burst (mid band)
  - hat:   5000-12000 Hz transient (high band)

For each onset we measure energy in each band; whichever band peaks
classifies the hit. Output: list of {time, instrument, confidence}.

This works well when you've already separated the drums stem (Demucs
htdemucs_6s gives us drums.wav). If you call it on a full mix, accuracy
drops but it still picks up most kicks.
"""
from __future__ import annotations

from typing import Any


DRUM_BANDS = {
    "kick":  (30, 150),
    "snare": (150, 1200),
    "hat":   (5000, 12000),
}


def transcribe_drums(
    audio: Any,
    sample_rate: int,
    *,
    onset_delta: float = 0.07,
    min_seconds_per_hit: float = 0.04,
) -> list[dict[str, Any]]:
    try:
        import librosa
        import numpy as np
    except Exception:
        return []

    if audio is None or len(audio) == 0:
        return []

    hop_length = 256
    onset_env = librosa.onset.onset_strength(y=audio, sr=sample_rate, hop_length=hop_length)
    onset_frames = librosa.onset.onset_detect(
        onset_envelope=onset_env,
        sr=sample_rate,
        hop_length=hop_length,
        wait=1,
        delta=onset_delta,
        units="frames",
    )
    if len(onset_frames) == 0:
        return []

    # Band-pass each region around the onset to classify
    stft = np.abs(librosa.stft(audio, n_fft=2048, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sample_rate, n_fft=2048)
    band_indices = {
        name: np.where((freqs >= lo) & (freqs < hi))[0]
        for name, (lo, hi) in DRUM_BANDS.items()
    }

    hits: list[dict[str, Any]] = []
    last_time: float | None = None
    for onset_frame in onset_frames:
        # Energy across 3 frames at the onset
        start_f = max(0, int(onset_frame))
        end_f = min(stft.shape[1], start_f + 3)
        window = stft[:, start_f:end_f]
        if window.size == 0:
            continue
        energies = {
            name: float(window[idx, :].sum()) if len(idx) > 0 else 0.0
            for name, idx in band_indices.items()
        }
        total = sum(energies.values()) or 1.0
        # Pick band with highest *relative* energy
        ratios = {name: energy / total for name, energy in energies.items()}
        winner = max(ratios, key=ratios.get)
        confidence = ratios[winner]
        # Skip noisy / weak hits
        if confidence < 0.4:
            continue
        time_s = float(librosa.frames_to_time(start_f, sr=sample_rate, hop_length=hop_length))
        if last_time is not None and time_s - last_time < min_seconds_per_hit:
            continue
        hits.append({
            "time": round(time_s, 4),
            "instrument": winner,
            "confidence": round(confidence, 3),
        })
        last_time = time_s

    return hits
