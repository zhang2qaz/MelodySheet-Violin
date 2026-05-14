from __future__ import annotations

from typing import Any


YAMNET_TO_INTERNAL = {
    "Violin, fiddle": "violin",
    "Cello": "cello",
    "Double bass": "bass",
    "Flute": "flute",
    "Piano": "piano",
    "Electric piano": "piano",
    "Acoustic guitar": "guitar",
    "Electric guitar": "guitar",
    "Bass guitar": "bass",
    "Singing": "vocal",
    "Male singing": "vocal",
    "Female singing": "vocal",
    "Child singing": "vocal",
    "Drum": "drums",
    "Drum kit": "drums",
    "Snare drum": "drums",
    "Trumpet": "trumpet",
    "Saxophone": "saxophone",
    "Erhu": "erhu",
}


def _identify_with_yamnet(audio: Any, sample_rate: int) -> list[dict[str, Any]] | None:
    try:
        import numpy as np
        import tensorflow as tf  # noqa: F401  (ensures tf is importable)
        import tensorflow_hub as hub
        import librosa
    except Exception:
        return None

    try:
        model = hub.load("https://tfhub.dev/google/yamnet/1")
        target_sr = 16000
        if sample_rate != target_sr:
            audio_resampled = librosa.resample(audio, orig_sr=sample_rate, target_sr=target_sr)
        else:
            audio_resampled = audio
        scores, _embeddings, _spectrogram = model(audio_resampled)
        scores_np = scores.numpy()  # (frames, 521)
        mean_scores = scores_np.mean(axis=0)

        class_map_path = model.class_map_path().numpy().decode("utf-8")
        labels: list[str] = []
        with open(class_map_path) as handle:
            handle.readline()
            for line in handle:
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    labels.append(parts[2].strip('"'))

        ranked = sorted(
            ((labels[i], float(mean_scores[i])) for i in range(len(labels))),
            key=lambda item: item[1],
            reverse=True,
        )
        detected: dict[str, float] = {}
        for label, score in ranked[:30]:
            internal = YAMNET_TO_INTERNAL.get(label)
            if internal and score > 0.05:
                detected[internal] = max(detected.get(internal, 0.0), score)
        return [
            {"instrument": instrument, "confidence": round(score, 3), "source": "yamnet"}
            for instrument, score in sorted(detected.items(), key=lambda item: item[1], reverse=True)
        ]
    except Exception:
        return None


def _identify_with_heuristic(audio: Any, sample_rate: int) -> list[dict[str, Any]]:
    try:
        import librosa
        import numpy as np
    except Exception:
        return []

    if audio is None or len(audio) == 0:
        return []

    harmonic, percussive = librosa.effects.hpss(audio)
    rms = float(np.sqrt(np.mean(audio ** 2)) + 1e-9)
    perc_rms = float(np.sqrt(np.mean(percussive ** 2)) + 1e-9)
    perc_ratio = perc_rms / rms

    spectral_centroid = float(np.mean(librosa.feature.spectral_centroid(y=audio, sr=sample_rate)))
    zero_crossing_rate = float(np.mean(librosa.feature.zero_crossing_rate(audio)))
    f0, voiced_flag, _ = librosa.pyin(
        audio,
        fmin=float(librosa.note_to_hz("C2")),
        fmax=float(librosa.note_to_hz("C7")),
        sr=sample_rate,
    )
    voiced_ratio = float(np.mean(voiced_flag)) if voiced_flag is not None else 0.0
    valid_f0 = f0[~np.isnan(f0)] if f0 is not None else np.array([])
    median_f0 = float(np.median(valid_f0)) if valid_f0.size else 0.0

    candidates: list[dict[str, Any]] = []

    def add(instrument: str, score: float, reason: str) -> None:
        candidates.append(
            {
                "instrument": instrument,
                "confidence": round(max(0.0, min(score, 1.0)), 3),
                "source": "heuristic",
                "reason": reason,
            }
        )

    if perc_ratio > 0.45:
        add("drums", 0.6, "强冲击瞬态成分占比高")

    if voiced_ratio > 0.35 and 1500 < spectral_centroid < 4500 and 196 <= median_f0 <= 1500:
        add("violin", 0.55 + min(voiced_ratio, 0.3), "明亮中高频且有连续 f0 轨迹")

    if voiced_ratio > 0.4 and 2500 < spectral_centroid and 261 <= median_f0 <= 2100:
        add("flute", 0.5, "高频纯净且 f0 稳定")

    if voiced_ratio > 0.4 and 800 < spectral_centroid < 3000 and 80 <= median_f0 <= 1100:
        add("vocal", 0.55, "f0 范围与人声吻合")

    if perc_ratio > 0.25 and 1000 < spectral_centroid < 4500:
        add("piano", 0.45, "强瞬态混合中频含量")

    if 800 < spectral_centroid < 2800 and zero_crossing_rate < 0.08 and voiced_ratio > 0.2:
        add("guitar", 0.4, "中频含量、低过零率")

    if voiced_ratio > 0.35 and 1200 < spectral_centroid < 3500 and 220 <= median_f0 <= 1200:
        add("erhu", 0.4, "中高频且有连续 f0 轨迹")

    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        key = item["instrument"]
        existing = deduped.get(key)
        if not existing or item["confidence"] > existing["confidence"]:
            deduped[key] = item
    # Sort by confidence then take ONLY the top candidate that crosses the
    # plausibility threshold. The heuristic conditions overlap heavily
    # (violin's spectral centroid range subsumes flute, guitar, erhu) so
    # without this filter a single violin recording surfaces 3-4 wrong
    # labels on the UI. Cap at 1 and require >=0.55 confidence so the
    # frontend only shows results that are at least a marginal commitment.
    ordered = sorted(deduped.values(), key=lambda item: item["confidence"], reverse=True)
    return [ordered[0]] if ordered and ordered[0]["confidence"] >= 0.55 else []


def identify_instruments(audio: Any, sample_rate: int) -> list[dict[str, Any]]:
    yamnet_result = _identify_with_yamnet(audio, sample_rate)
    if yamnet_result:
        # YAMNet results: trust the model, but still cap at top-3 so the UI
        # doesn't show every instrument in the orchestra for a single track.
        return yamnet_result[:3]
    return _identify_with_heuristic(audio, sample_rate)
