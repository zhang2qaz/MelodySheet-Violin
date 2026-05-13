#!/usr/bin/env python3
"""Run the v2 mono pipeline against a real-world recording and report results.

Default input: apps/api/storage/realtest/nocturne_first20s.wav
(decoded from the 1897 Wikimedia Commons CC0 nocturne FLAC).

Usage:
  apps/api/.venv/bin/python scripts/eval/realtest.py [path/to/audio.wav]

Outputs MusicXML + MIDI alongside the input file with prefix `out_`.
"""
from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_ROOT = REPO / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def run(audio_path: Path) -> None:
    from app.audio_io import load_audio_mono
    from app.transcribe_mono import transcribe_monophonic
    from app.rhythm import estimate_tempo_and_beats, quantize_notes_to_grid, estimate_meter
    from app.music_processing import prepare_notes_for_target
    from app.score_builder import Track, build_multitrack_score, write_score_outputs

    audio, sr = load_audio_mono(audio_path)
    tempo, beats = estimate_tempo_and_beats(audio, sr)
    meter = estimate_meter(beats, audio, sr)
    raw = transcribe_monophonic(audio, sr, "violin")
    filtered, removed = prepare_notes_for_target(raw, "violin")
    quantized = quantize_notes_to_grid(filtered, tempo_bpm=tempo, beats=beats)

    pitches = collections.Counter(item["pitch"] for item in quantized)
    midis = [item["midi_number"] for item in quantized]
    mean_conf = sum(item["confidence"] for item in quantized) / max(len(quantized), 1)

    print(f"=== {audio_path.name} ({len(audio)/sr:.2f}s) ===")
    print(f"tempo: {tempo:.1f} BPM   meter: {meter}")
    print(f"raw notes: {len(raw)}   after range/melody filter: {len(quantized)} (removed {removed})")
    print(f"MIDI range: {min(midis) if midis else 'n/a'}..{max(midis) if midis else 'n/a'}")
    print(f"mean confidence: {mean_conf:.2f}")
    print(f"top pitches: {dict(pitches.most_common(8))}")

    out_dir = audio_path.parent / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    track = Track(
        target_instrument="violin",
        notes=quantized,
        detected_key="C major",
        tempo_bpm=int(round(tempo)),
        meter=meter,
    )
    score = build_multitrack_score([track], title=f"Real recording: {audio_path.name}")
    written = write_score_outputs(score, out_dir, prefix=audio_path.stem)
    print(f"wrote: {written['musicxml']}\n       {written['midi']}")

    # Also write a high-confidence subset
    hi_notes = [n for n in quantized if n["confidence"] >= 0.4]
    if hi_notes:
        hi_track = Track(
            target_instrument="violin",
            notes=hi_notes,
            detected_key="C major",
            tempo_bpm=int(round(tempo)),
            meter=meter,
        )
        hi_score = build_multitrack_score([hi_track], title=f"Real recording (conf>=0.4): {audio_path.name}")
        hi_written = write_score_outputs(hi_score, out_dir, prefix=f"{audio_path.stem}_hiconf")
        print(f"wrote (hi-conf only, {len(hi_notes)} notes): {hi_written['musicxml']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    default = REPO / "apps" / "api" / "storage" / "realtest" / "nocturne_first20s.wav"
    parser.add_argument("audio_path", nargs="?", type=Path, default=default)
    args = parser.parse_args()
    if not args.audio_path.exists():
        print(f"audio not found: {args.audio_path}", file=sys.stderr)
        return 1
    run(args.audio_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
