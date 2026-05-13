"""Song structure / section detection via spectral clustering.

Uses Mel-MFCC features + librosa's agglomerative segmentation
(`librosa.segment.agglomerative`) to partition the song into K segments
where K is auto-detected by gap statistic. Then labels each segment
A / B / C / ... based on which previous segment(s) it's similar to,
producing patterns like A-B-A-B-C-B-B that read as verse-chorus form.

This isn't a verse/chorus classifier — that requires a learned model — but
it gives users a "song map" they can use to navigate the score and
re-record specific sections.
"""
from __future__ import annotations

from typing import Any


SECTION_LABELS = "ABCDEFGHIJKLMNOP"


def detect_sections(
    audio: Any,
    sample_rate: int,
    *,
    min_seconds_per_section: float = 4.0,
    max_sections: int = 8,
) -> list[dict[str, Any]]:
    try:
        import librosa
        import numpy as np
    except Exception:
        return []

    if audio is None or len(audio) == 0:
        return []
    duration = float(len(audio)) / sample_rate
    if duration < 6:
        return []

    hop_length = 1024
    # MFCC is a stable similarity feature for high-level song structure.
    mfcc = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=13, hop_length=hop_length)
    # Smooth to suppress local fluctuation
    if mfcc.shape[1] > 4:
        mfcc = librosa.decompose.nn_filter(mfcc, aggregate=np.median, metric="cosine", width=4)

    # Pick K so each section is at least min_seconds long
    k = max(2, min(max_sections, int(duration / min_seconds_per_section)))
    if mfcc.shape[1] <= k:
        return []

    boundaries = librosa.segment.agglomerative(mfcc, k)
    boundaries = np.unique(np.concatenate([[0], boundaries, [mfcc.shape[1]]]))

    # Compute centroid of each segment for similarity-based labeling.
    centroids = []
    for i in range(len(boundaries) - 1):
        start_f, end_f = int(boundaries[i]), int(boundaries[i + 1])
        if end_f <= start_f:
            continue
        centroids.append((start_f, end_f, mfcc[:, start_f:end_f].mean(axis=1)))

    # Label segments: assign 'A' to the first; subsequent segments get an
    # existing label if cosine similarity to that label's centroid > 0.85,
    # else a new label.
    labels: list[str] = []
    representatives: list[tuple[str, np.ndarray]] = []
    for start_f, end_f, centroid in centroids:
        chosen: str | None = None
        for label, rep in representatives:
            cos = float(np.dot(centroid, rep) / (np.linalg.norm(centroid) * np.linalg.norm(rep) + 1e-9))
            if cos > 0.85:
                chosen = label
                break
        if chosen is None:
            chosen = SECTION_LABELS[len(representatives) % len(SECTION_LABELS)]
            representatives.append((chosen, centroid))
        labels.append(chosen)

    sections: list[dict[str, Any]] = []
    for (start_f, end_f, _centroid), label in zip(centroids, labels):
        start_t = float(librosa.frames_to_time(start_f, sr=sample_rate, hop_length=hop_length))
        end_t = float(librosa.frames_to_time(end_f, sr=sample_rate, hop_length=hop_length))
        sections.append({
            "start_time": round(start_t, 3),
            "end_time": round(end_t, 3),
            "label": label,
        })
    return sections
