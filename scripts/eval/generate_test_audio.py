#!/usr/bin/env python3
"""Synthesize a deterministic violin-like melody from a seed.

Output:
  <out_dir>/audio.wav        — rendered 44.1 kHz mono PCM-16 WAV
  <out_dir>/ground_truth.json — {tempo_bpm, key, meter, notes:[{midi, start_time, duration_seconds, pitch}]}

The synthesis uses additive harmonics with vibrato and a simple ADSR envelope —
not a real violin, but good enough to exercise pYIN's pitch tracking and the
onset detector. For higher-fidelity tests, render the emitted MIDI with
FluidSynth + a violin SoundFont (see scripts/eval/README.md).
"""
from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import soundfile as sf


KEY_PITCH_CLASSES: dict[str, list[int]] = {
    "C major": [0, 2, 4, 5, 7, 9, 11],
    "G major": [7, 9, 11, 0, 2, 4, 6],
    "D major": [2, 4, 6, 7, 9, 11, 1],
    "A major": [9, 11, 1, 2, 4, 6, 8],
    "F major": [5, 7, 9, 10, 0, 2, 4],
    "A minor": [9, 11, 0, 2, 4, 5, 7],
    "E minor": [4, 6, 7, 9, 11, 0, 2],
    "D minor": [2, 4, 5, 7, 9, 10, 0],
}

VIOLIN_MIDI_MIN = 55  # G3 — lowest violin open string
VIOLIN_MIDI_MAX = 88  # E6 — comfortable upper bound for tests

DURATION_CHOICES_QUARTERS = [0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0, 2.0]
FAST_DURATION_CHOICES_QUARTERS = [0.25, 0.25, 0.5, 0.5, 0.5, 1.0]
DURATION_NAMES = {0.25: "sixteenth", 0.5: "eighth", 1.0: "quarter", 2.0: "half", 4.0: "whole"}

NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def midi_to_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def generate_melody(
    seed: int,
    *,
    num_notes: int = 20,
    tempo_bpm: int = 90,
    key: str = "G major",
    meter: str = "4/4",
    midi_range: tuple[int, int] = (VIOLIN_MIDI_MIN, VIOLIN_MIDI_MAX),
    duration_pool: list[float] | None = None,
    pattern: str = "random",
) -> dict:
    rng = random.Random(seed)
    seconds_per_quarter = 60.0 / tempo_bpm
    pitch_classes = KEY_PITCH_CLASSES[key]
    candidate_midis = [m for m in range(midi_range[0], midi_range[1] + 1) if (m % 12) in pitch_classes]
    if not candidate_midis:
        raise ValueError("no MIDI numbers fit the chosen key and range")
    pool = duration_pool if duration_pool is not None else DURATION_CHOICES_QUARTERS

    prev_midi = min(candidate_midis, key=lambda m: abs(m - 69))
    current_time = 0.0
    notes: list[dict] = []

    if pattern == "trill":
        anchor_pc = pitch_classes[2]
        anchor_midi = min((m for m in candidate_midis if (m % 12) == anchor_pc), key=lambda m: abs(m - 72))
        upper_midi = anchor_midi + 1  # half-step trill above
        trill_dur = 0.25 * seconds_per_quarter
        for index in range(num_notes):
            midi = upper_midi if index % 2 == 1 else anchor_midi
            notes.append(
                {
                    "midi_number": int(midi),
                    "pitch": midi_to_name(int(midi)),
                    "start_time": round(current_time, 4),
                    "duration_seconds": round(trill_dur, 4),
                    "duration_quarters": 0.25,
                    "duration_label": DURATION_NAMES[0.25],
                }
            )
            current_time += trill_dur
        return {
            "seed": seed,
            "tempo_bpm": tempo_bpm,
            "key": key,
            "meter": meter,
            "num_notes": len(notes),
            "duration_seconds": round(current_time, 4),
            "notes": notes,
        }

    if pattern == "arpeggio":
        anchor_pc = pitch_classes[0]
        triad_offsets = [0, 4, 7, 12]  # root, third, fifth, octave (semitone offsets)
        anchor_midi = min(candidate_midis, key=lambda m: abs(m - 64))
        chord_midis = [anchor_midi + offset for offset in triad_offsets if anchor_midi + offset <= midi_range[1]]
        if not chord_midis:
            chord_midis = [anchor_midi]
        arp_dur = 0.5 * seconds_per_quarter
        for index in range(num_notes):
            midi = chord_midis[index % len(chord_midis)]
            notes.append(
                {
                    "midi_number": int(midi),
                    "pitch": midi_to_name(int(midi)),
                    "start_time": round(current_time, 4),
                    "duration_seconds": round(arp_dur, 4),
                    "duration_quarters": 0.5,
                    "duration_label": DURATION_NAMES[0.5],
                }
            )
            current_time += arp_dur
        return {
            "seed": seed,
            "tempo_bpm": tempo_bpm,
            "key": key,
            "meter": meter,
            "num_notes": len(notes),
            "duration_seconds": round(current_time, 4),
            "notes": notes,
        }

    for _ in range(num_notes):
        # Bias toward small intervals: prefer nearby candidates.
        candidate = min(
            rng.sample(candidate_midis, k=min(6, len(candidate_midis))),
            key=lambda m: abs(m - prev_midi) + rng.random() * 3,
        )
        duration_quarters = rng.choice(pool)
        duration_seconds = duration_quarters * seconds_per_quarter
        notes.append(
            {
                "midi_number": int(candidate),
                "pitch": midi_to_name(int(candidate)),
                "start_time": round(current_time, 4),
                "duration_seconds": round(duration_seconds, 4),
                "duration_quarters": float(duration_quarters),
                "duration_label": DURATION_NAMES.get(duration_quarters, "quarter"),
            }
        )
        current_time += duration_seconds
        prev_midi = candidate

    return {
        "seed": seed,
        "tempo_bpm": tempo_bpm,
        "key": key,
        "meter": meter,
        "num_notes": len(notes),
        "duration_seconds": round(current_time, 4),
        "notes": notes,
    }


def render_violin_audio(
    notes: list[dict],
    *,
    sample_rate: int = 44100,
    tail_seconds: float = 0.5,
    harmonic_amplitudes: tuple[float, ...] = (1.0, 0.55, 0.32, 0.18, 0.09, 0.05),
    vibrato_hz: float = 5.5,
    vibrato_cents: float = 18.0,
    attack_seconds: float = 0.04,
    release_seconds: float = 0.08,
    noise_level: float = 0.0035,
) -> np.ndarray:
    if not notes:
        return np.zeros(int(sample_rate * tail_seconds), dtype=np.float32)
    total_seconds = notes[-1]["start_time"] + notes[-1]["duration_seconds"] + tail_seconds
    audio = np.zeros(int(total_seconds * sample_rate), dtype=np.float64)
    rng = np.random.default_rng(0)

    for note in notes:
        f0 = 440.0 * (2.0 ** ((note["midi_number"] - 69) / 12.0))
        n_samples = int(note["duration_seconds"] * sample_rate)
        if n_samples <= 0:
            continue
        start_idx = int(note["start_time"] * sample_rate)
        time_axis = np.arange(n_samples, dtype=np.float64) / sample_rate
        vibrato_depth_ratio = (2.0 ** (vibrato_cents / 1200.0)) - 1.0
        vibrato = vibrato_depth_ratio * np.sin(2.0 * math.pi * vibrato_hz * time_axis)
        instantaneous_phase = 2.0 * math.pi * f0 * np.cumsum(1.0 + vibrato) / sample_rate
        signal = np.zeros(n_samples, dtype=np.float64)
        for harmonic_index, amplitude in enumerate(harmonic_amplitudes, start=1):
            signal += amplitude * np.sin(harmonic_index * instantaneous_phase)
        attack_samples = max(1, int(attack_seconds * sample_rate))
        release_samples = max(1, int(release_seconds * sample_rate))
        envelope = np.ones(n_samples, dtype=np.float64)
        attack_samples = min(attack_samples, n_samples // 2)
        release_samples = min(release_samples, n_samples - attack_samples)
        if attack_samples > 0:
            envelope[:attack_samples] = np.linspace(0.0, 1.0, attack_samples)
        if release_samples > 0:
            envelope[-release_samples:] = np.linspace(1.0, 0.0, release_samples)
        signal *= envelope
        end_idx = min(start_idx + n_samples, len(audio))
        audio[start_idx:end_idx] += signal[: end_idx - start_idx]

    if noise_level > 0.0:
        audio += rng.normal(0.0, noise_level, size=audio.shape)

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.9
    return audio.astype(np.float32)


def write_dataset(out_dir: Path, seed: int, *, noise_level: float = 0.0035, **kwargs) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ground_truth = generate_melody(seed, **kwargs)
    audio = render_violin_audio(ground_truth["notes"], noise_level=noise_level)
    audio_path = out_dir / "audio.wav"
    sf.write(str(audio_path), audio, 44100, subtype="PCM_16")
    gt_path = out_dir / "ground_truth.json"
    gt_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")
    return audio_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-notes", type=int, default=20)
    parser.add_argument("--tempo", type=int, default=90)
    parser.add_argument("--key", default="G major")
    parser.add_argument("--meter", default="4/4")
    args = parser.parse_args()

    audio_path = write_dataset(
        args.out_dir,
        args.seed,
        num_notes=args.num_notes,
        tempo_bpm=args.tempo,
        key=args.key,
        meter=args.meter,
    )
    print(f"Wrote {audio_path} and ground_truth.json")


if __name__ == "__main__":
    main()
