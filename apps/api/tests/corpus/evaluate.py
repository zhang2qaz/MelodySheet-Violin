"""Note-level F1 evaluation against the synthetic corpus.

A predicted note matches a ground-truth note when BOTH:
  - same MIDI number (exact -- no octave grace)
  - onset within MATCH_ONSET_TOLERANCE_SEC of GT onset

Standard "transcription accuracy" metric. We don't grade durations
beyond requiring overlap-in-time, because durations are noisy under
quantization but the listener cares mostly about pitch sequence.

Run as a script:
    python -m tests.corpus.evaluate                 # baseline (current pipeline)
    python -m tests.corpus.evaluate --verbose       # show per-note matching
    python -m tests.corpus.evaluate --pitch-only    # ignore onsets (loose)

Exits 0 (the script just prints a table; CI gating to come later).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import soundfile as sf


MATCH_ONSET_TOLERANCE_SEC = 0.1  # 100 ms wiggle room


@dataclass
class EvalResult:
    clip: str
    gt_count: int
    pred_count: int
    tp: int
    fp: int
    fn: int

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) > 0 else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) > 0 else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def transcribe(wav_path: Path) -> list[dict[str, Any]]:
    """Run the pipeline's monophonic-violin transcriber on a wav file.

    We call transcribe_violin_via_basic_pitch directly rather than going
    through the full process_job_v2 because we want to measure the
    transcription quality in isolation, without confounders from
    quantization or instrument-range filtering.
    """
    from app.transcribe_violin_bp import transcribe_violin_via_basic_pitch
    return transcribe_violin_via_basic_pitch(wav_path)


def match_notes(
    gt: list[dict[str, Any]],
    pred: list[dict[str, Any]],
    *,
    onset_tol_sec: float,
    pitch_only: bool,
) -> tuple[int, int, int, list[str]]:
    """Greedy bipartite match -- each prediction can match at most one GT."""
    matched_gt = set()
    matched_pred = set()
    explain: list[str] = []

    # Sort GT by start time, then try to match each
    for gi, g in enumerate(sorted(gt, key=lambda n: n["start"])):
        g_midi = int(g["midi"])
        g_start = float(g["start"])
        best_pi = None
        best_gap = float("inf")
        for pi, p in enumerate(pred):
            if pi in matched_pred:
                continue
            if int(p["midi_number"]) != g_midi:
                continue
            p_start = float(p["start_time"])
            gap = abs(p_start - g_start)
            if pitch_only or gap <= onset_tol_sec:
                if gap < best_gap:
                    best_gap = gap
                    best_pi = pi
        if best_pi is not None:
            matched_gt.add(gi)
            matched_pred.add(best_pi)
            explain.append(f"  OK  midi={g_midi:3d}  gt={g_start:5.2f}s  pred={float(pred[best_pi]['start_time']):5.2f}s  Δ={best_gap*1000:+.0f}ms")
        else:
            explain.append(f"  ✗   midi={g_midi:3d}  gt={g_start:5.2f}s  (no match)")

    tp = len(matched_gt)
    fn = len(gt) - tp
    fp = len(pred) - len(matched_pred)
    for pi, p in enumerate(pred):
        if pi not in matched_pred:
            explain.append(f"  +   midi={int(p['midi_number']):3d}  pred={float(p['start_time']):5.2f}s  (extra)")
    return tp, fp, fn, explain


def evaluate_clip(wav_path: Path, gt_path: Path, *, pitch_only: bool = False, verbose: bool = False) -> EvalResult:
    gt_data = json.loads(gt_path.read_text())
    gt_notes = gt_data["notes"]
    pred_notes = transcribe(wav_path)
    tp, fp, fn, explain = match_notes(
        gt_notes, pred_notes,
        onset_tol_sec=MATCH_ONSET_TOLERANCE_SEC,
        pitch_only=pitch_only,
    )
    result = EvalResult(
        clip=wav_path.stem,
        gt_count=len(gt_notes),
        pred_count=len(pred_notes),
        tp=tp, fp=fp, fn=fn,
    )
    if verbose:
        print(f"\n=== {result.clip} ===")
        for line in explain:
            print(line)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the violin transcription pipeline on the synthetic corpus.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-note matching for each clip.")
    parser.add_argument("--pitch-only", action="store_true", help="Match only on pitch (ignore onset timing).")
    parser.add_argument("--filter", "-f", default=None, help="Only run clips matching this substring.")
    args = parser.parse_args()

    corpus_dir = Path(__file__).parent
    wavs = sorted(corpus_dir.glob("*.wav"))
    if args.filter:
        wavs = [w for w in wavs if args.filter in w.name]
    if not wavs:
        print("No corpus clips found. Run `python -m tests.corpus._synth` first.", file=sys.stderr)
        return 1

    results: list[EvalResult] = []
    t0 = time.time()
    for wav in wavs:
        gt = wav.with_suffix(".json")
        result = evaluate_clip(wav, gt, pitch_only=args.pitch_only, verbose=args.verbose)
        results.append(result)

    elapsed = time.time() - t0

    print()
    print(f"{'clip':36s}  {'gt':>4s}  {'pred':>4s}  {'tp':>3s}  {'fp':>3s}  {'fn':>3s}  {'prec':>5s}  {'rec':>5s}  {'F1':>5s}")
    print("-" * 88)
    for r in results:
        print(f"{r.clip:36s}  {r.gt_count:>4d}  {r.pred_count:>4d}  {r.tp:>3d}  {r.fp:>3d}  {r.fn:>3d}  "
              f"{r.precision*100:>4.0f}%  {r.recall*100:>4.0f}%  {r.f1*100:>4.0f}%")
    print("-" * 88)
    # Aggregate (micro)
    total_tp = sum(r.tp for r in results)
    total_fp = sum(r.fp for r in results)
    total_fn = sum(r.fn for r in results)
    prec = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    rec = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    print(f"{'MICRO TOTAL':36s}  {sum(r.gt_count for r in results):>4d}  {sum(r.pred_count for r in results):>4d}  "
          f"{total_tp:>3d}  {total_fp:>3d}  {total_fn:>3d}  "
          f"{prec*100:>4.0f}%  {rec*100:>4.0f}%  {f1*100:>4.0f}%")
    print(f"\nElapsed: {elapsed:.1f}s  ({elapsed/len(wavs):.1f}s per clip)")
    if args.pitch_only:
        print("(pitch-only matching -- onsets ignored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
