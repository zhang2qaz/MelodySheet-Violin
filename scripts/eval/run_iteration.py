#!/usr/bin/env python3
"""Run one evaluation iteration of the MelodySheet-Violin transcription pipeline.

For each case in the test panel:
  1. Synthesize a deterministic violin-like WAV from a seed (generate_test_audio).
  2. Load the audio via app.audio_io, run transcribe_monophonic, quantize to grid.
  3. Compare the result with the ground-truth notes using onset+pitch matching.
  4. Aggregate metrics across the panel.

Writes one JSON record per case + one summary record to scripts/eval/log.jsonl.
The summary is what the /loop driver reads to decide what to tune next.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
EVAL_DIR = Path(__file__).resolve().parent
for path in (str(API_ROOT), str(EVAL_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from generate_test_audio import write_dataset  # noqa: E402


# A fixed panel of test cases. Each iteration regenerates them deterministically so
# improvements show up as monotonic metric changes instead of seed noise.
TEST_PANEL: list[dict[str, Any]] = [
    # Baseline panel (solved at iter 18, F1=1.0)
    {"name": "g_major_short_slow", "seed": 1001, "num_notes": 12, "tempo": 70, "key": "G major"},
    {"name": "d_major_medium", "seed": 1002, "num_notes": 16, "tempo": 90, "key": "D major"},
    {"name": "a_major_brisk", "seed": 1003, "num_notes": 20, "tempo": 120, "key": "A major"},
    {"name": "c_major_compact", "seed": 1004, "num_notes": 18, "tempo": 100, "key": "C major"},
    {"name": "f_major_long", "seed": 1005, "num_notes": 24, "tempo": 80, "key": "F major"},
    {"name": "a_minor_lyrical", "seed": 1006, "num_notes": 16, "tempo": 75, "key": "A minor"},
    {"name": "e_minor_fast", "seed": 1007, "num_notes": 22, "tempo": 132, "key": "E minor"},
    {"name": "d_minor_dense", "seed": 1008, "num_notes": 26, "tempo": 96, "key": "D minor"},
    # Hard panel added after iter 18 (sixteenths, trills, ornaments, high noise).
    {"name": "hard_sixteenths_160bpm", "seed": 2001, "num_notes": 24, "tempo": 160,
     "key": "G major", "duration_pool": [0.25, 0.25, 0.5, 0.5]},
    {"name": "hard_sixteenths_140bpm", "seed": 2002, "num_notes": 28, "tempo": 140,
     "key": "D major", "duration_pool": [0.25, 0.25, 0.5, 0.5, 1.0]},
    {"name": "hard_trill_quarters", "seed": 2003, "num_notes": 20, "tempo": 100,
     "key": "G major", "pattern": "trill"},
    {"name": "hard_arpeggio", "seed": 2004, "num_notes": 24, "tempo": 110,
     "key": "C major", "pattern": "arpeggio"},
    {"name": "hard_high_noise", "seed": 2005, "num_notes": 18, "tempo": 100,
     "key": "G major", "noise_level": 0.015},
    {"name": "hard_low_register", "seed": 2006, "num_notes": 16, "tempo": 90,
     "key": "G major", "midi_range": (55, 70)},
]


def match_notes(
    gt_notes: list[dict[str, Any]],
    pred_notes: list[dict[str, Any]],
    *,
    onset_tolerance_seconds: float = 0.10,
    pitch_tolerance_semitones: float = 0.5,
) -> dict[str, Any]:
    """Greedy nearest-onset matching with pitch constraint, mir_eval-flavoured."""
    matched_gt_indices: set[int] = set()
    matched_pred_indices: set[int] = set()
    matches: list[tuple[int, int]] = []
    sorted_gt = sorted(enumerate(gt_notes), key=lambda pair: pair[1]["start_time"])
    for gt_index, gt_note in sorted_gt:
        best_pred_index = None
        best_diff = float("inf")
        for pred_index, pred_note in enumerate(pred_notes):
            if pred_index in matched_pred_indices:
                continue
            onset_diff = abs(pred_note["start_time"] - gt_note["start_time"])
            if onset_diff > onset_tolerance_seconds:
                continue
            pitch_diff = abs(pred_note["midi_number"] - gt_note["midi_number"])
            if pitch_diff > pitch_tolerance_semitones:
                continue
            if onset_diff < best_diff:
                best_diff = onset_diff
                best_pred_index = pred_index
        if best_pred_index is not None:
            matched_gt_indices.add(gt_index)
            matched_pred_indices.add(best_pred_index)
            matches.append((gt_index, best_pred_index))

    onset_errors = [
        abs(pred_notes[p]["start_time"] - gt_notes[g]["start_time"]) for g, p in matches
    ]
    duration_errors = [
        abs(
            float(pred_notes[p].get("duration_seconds", 0.0))
            - float(gt_notes[g].get("duration_seconds", 0.0))
        )
        for g, p in matches
    ]
    pitch_errors = [
        abs(int(pred_notes[p]["midi_number"]) - int(gt_notes[g]["midi_number"])) for g, p in matches
    ]
    precision = len(matches) / max(len(pred_notes), 1)
    recall = len(matches) / max(len(gt_notes), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    pitch_correct = sum(1 for err in pitch_errors if err == 0)
    pitch_accuracy = pitch_correct / max(len(matches), 1)
    octave_errors = sum(
        1
        for g, p in matches
        if (pred_notes[p]["midi_number"] - gt_notes[g]["midi_number"]) % 12 == 0
        and pred_notes[p]["midi_number"] != gt_notes[g]["midi_number"]
    )

    missed_gt = [
        {
            "start_time": gt_notes[i]["start_time"],
            "duration_seconds": gt_notes[i].get("duration_seconds"),
            "midi_number": gt_notes[i]["midi_number"],
            "pitch": gt_notes[i].get("pitch"),
        }
        for i in range(len(gt_notes))
        if i not in matched_gt_indices
    ]
    extra_pred = [
        {
            "start_time": pred_notes[j]["start_time"],
            "duration_seconds": pred_notes[j].get("duration_seconds"),
            "midi_number": pred_notes[j]["midi_number"],
            "pitch": pred_notes[j].get("pitch"),
            "confidence": pred_notes[j].get("confidence"),
        }
        for j in range(len(pred_notes))
        if j not in matched_pred_indices
    ]

    return {
        "gt_count": len(gt_notes),
        "pred_count": len(pred_notes),
        "matches": len(matches),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "pitch_accuracy_among_matches": round(pitch_accuracy, 4),
        "onset_mae_seconds": round(statistics.mean(onset_errors), 4) if onset_errors else None,
        "duration_mae_seconds": round(statistics.mean(duration_errors), 4) if duration_errors else None,
        "octave_errors": octave_errors,
        "missed_gt": missed_gt,
        "extra_pred": extra_pred,
    }


def run_pipeline_on_audio(audio_path: Path, target_instrument: str = "violin") -> dict[str, Any]:
    """Invoke the v2 pipeline (load → mono transcribe → quantize) without going through
    the FastAPI job system. This keeps the eval fast and isolated from the HTTP layer.
    """
    from app.audio_io import load_audio_mono
    from app.music_processing import prepare_notes_for_target
    from app.rhythm import estimate_tempo_and_beats, quantize_notes_to_grid
    from app.transcribe_mono import transcribe_monophonic

    audio, sample_rate = load_audio_mono(audio_path)
    tempo_bpm, beats = estimate_tempo_and_beats(audio, sample_rate)
    raw_notes = transcribe_monophonic(audio, sample_rate, target_instrument)
    filtered_notes, filtered_count = prepare_notes_for_target(raw_notes, target_instrument)
    quantized = quantize_notes_to_grid(filtered_notes, tempo_bpm=tempo_bpm, beats=beats)
    return {
        "tempo_bpm": float(tempo_bpm),
        "raw_note_count": len(raw_notes),
        "filtered_note_count": filtered_count,
        "notes": quantized,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iteration", type=int, default=0)
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "audio",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path(__file__).resolve().parent / "log.jsonl",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "runs",
    )
    parser.add_argument("--cases", nargs="*", default=None, help="Filter to a subset of panel names")
    args = parser.parse_args()

    args.audio_dir.mkdir(parents=True, exist_ok=True)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    args.log_path.parent.mkdir(parents=True, exist_ok=True)

    panel = TEST_PANEL if not args.cases else [case for case in TEST_PANEL if case["name"] in args.cases]
    started_at = datetime.now(timezone.utc).isoformat()
    case_records: list[dict[str, Any]] = []

    for case in panel:
        case_dir = args.audio_dir / case["name"]
        write_kwargs: dict[str, Any] = {
            "num_notes": case["num_notes"],
            "tempo_bpm": case["tempo"],
            "key": case["key"],
        }
        for optional_key in ("duration_pool", "pattern", "midi_range", "noise_level"):
            if optional_key in case:
                write_kwargs[optional_key] = case[optional_key]
        write_dataset(case_dir, case["seed"], **write_kwargs)
        ground_truth = json.loads((case_dir / "ground_truth.json").read_text(encoding="utf-8"))

        t0 = time.time()
        try:
            pipeline = run_pipeline_on_audio(case_dir / "audio.wav")
            pipeline_error = None
        except Exception as exc:  # pragma: no cover - reported in log
            pipeline = {"tempo_bpm": None, "raw_note_count": 0, "filtered_note_count": 0, "notes": []}
            pipeline_error = f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - t0

        metrics = match_notes(ground_truth["notes"], pipeline["notes"])
        record = {
            "case": case["name"],
            "seed": case["seed"],
            "tempo_bpm_truth": case["tempo"],
            "tempo_bpm_pred": pipeline.get("tempo_bpm"),
            "key": case["key"],
            "elapsed_seconds": round(elapsed, 3),
            "pipeline_error": pipeline_error,
            "metrics": metrics,
        }
        case_records.append(record)
        print(
            f"[case {case['name']}] f1={metrics['f1']} p={metrics['precision']} r={metrics['recall']}"
            f" gt={metrics['gt_count']} pred={metrics['pred_count']} pitch_acc={metrics['pitch_accuracy_among_matches']}"
            f" onset_mae={metrics['onset_mae_seconds']} octave_err={metrics['octave_errors']}"
            + (f" ERR={pipeline_error}" if pipeline_error else "")
        )

    summary = {
        "iteration": args.iteration,
        "label": args.label,
        "started_at": started_at,
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "cases": case_records,
        "aggregate": {
            "mean_f1": round(statistics.mean(case["metrics"]["f1"] for case in case_records), 4),
            "mean_precision": round(statistics.mean(case["metrics"]["precision"] for case in case_records), 4),
            "mean_recall": round(statistics.mean(case["metrics"]["recall"] for case in case_records), 4),
            "mean_pitch_accuracy": round(
                statistics.mean(case["metrics"]["pitch_accuracy_among_matches"] for case in case_records), 4
            ),
            "mean_onset_mae_seconds": round(
                statistics.mean(
                    case["metrics"]["onset_mae_seconds"] or 0.0
                    for case in case_records
                ),
                4,
            ),
            "total_octave_errors": sum(case["metrics"]["octave_errors"] for case in case_records),
            "total_gt_notes": sum(case["metrics"]["gt_count"] for case in case_records),
            "total_pred_notes": sum(case["metrics"]["pred_count"] for case in case_records),
        },
    }

    with args.log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")

    run_path = args.run_dir / f"iter_{args.iteration:04d}.json"
    run_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("---")
    print(json.dumps(summary["aggregate"], ensure_ascii=False))
    print(f"Logged to {args.log_path} and {run_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
