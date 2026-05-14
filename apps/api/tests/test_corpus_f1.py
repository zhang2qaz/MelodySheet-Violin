"""Pytest gating: violin transcription F1 must stay at 100% on the synthetic
curriculum-level-1 corpus.

Why this is a pytest test (not just an offline script):
  - The curriculum strategy says level 1 (single notes / simple melody /
    repeated / vibrato / dynamics / range / mixed durations) must be
    "near 100%" before we move to harder material.
  - Currently we're AT 100%. Any future change that drops this below 95%
    should fail CI so we know immediately, not after the user complains.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.corpus.evaluate import evaluate_clip


CORPUS_DIR = Path(__file__).parent / "corpus"
WAVS = sorted(CORPUS_DIR.glob("*.wav"))

# Hard floor: any clip dropping below this means the change probably
# regressed the model and shouldn't ship. 95% leaves room for noisy real
# recordings later -- the synthetic corpus should hit 100% as a baseline.
PER_CLIP_F1_FLOOR = 0.95
TOTAL_F1_FLOOR = 0.95


@pytest.mark.parametrize("wav_path", WAVS, ids=lambda p: p.stem)
def test_violin_transcription_f1(wav_path: Path) -> None:
    gt_path = wav_path.with_suffix(".json")
    assert gt_path.exists(), f"missing ground truth for {wav_path.name}"
    result = evaluate_clip(wav_path, gt_path)
    assert result.f1 >= PER_CLIP_F1_FLOOR, (
        f"{result.clip} F1={result.f1:.2%} "
        f"(precision={result.precision:.2%} recall={result.recall:.2%}); "
        f"floor is {PER_CLIP_F1_FLOOR:.0%}"
    )


def test_violin_transcription_total_f1() -> None:
    """Micro-averaged F1 across the corpus."""
    total_tp = total_fp = total_fn = 0
    for wav in WAVS:
        result = evaluate_clip(wav, wav.with_suffix(".json"))
        total_tp += result.tp
        total_fp += result.fp
        total_fn += result.fn
    prec = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    rec = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    assert f1 >= TOTAL_F1_FLOOR, (
        f"corpus F1={f1:.2%} (precision={prec:.2%} recall={rec:.2%}); "
        f"floor is {TOTAL_F1_FLOOR:.0%}"
    )
