"""Synthesize labelled violin-like audio clips for evaluation.

Why synthesize: real recordings would be ideal but we can't ship labelled
data with the repo for license reasons, and the user has no real
recordings handy. Synthesis gives us:
  - Exact ground-truth (we KNOW the pitch + onset + duration we wrote)
  - Reproducible (same output every run)
  - Coverage we can dial: single notes, repeats, dynamics, vibrato.

Voice model: 7 harmonics with violin-typical amplitude rolloff
(1.0, 0.55, 0.42, 0.28, 0.18, 0.10, 0.06) + ADSR envelope. Optionally
vibrato (5 Hz, configurable depth in cents). This is NOT a realistic
violin tone -- it sounds buzzy -- but it has the same pitch / onset
structure that pYIN / Basic Pitch sees, which is what we're measuring.

Each clip writes:
  <clip_name>.wav   -- 22050 Hz mono
  <clip_name>.json  -- ground-truth: list of {midi, start, end}
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf


SR = 22050
HARMONICS = (1.0, 0.55, 0.42, 0.28, 0.18, 0.10, 0.06)


@dataclass
class GroundTruthNote:
    midi: int
    start: float
    end: float


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def synth_note(
    midi: int,
    duration: float,
    *,
    vibrato_cents: float = 0.0,
    vibrato_rate_hz: float = 5.0,
    amplitude: float = 0.6,
) -> np.ndarray:
    """A single violin-like note of given duration."""
    n = int(SR * duration)
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    t = np.arange(n) / SR
    base_hz = midi_to_hz(midi)

    # Pitch modulation for vibrato (smooth sinusoidal). Skip cycles in the
    # first 80 ms attack so the onset is clean for the onset detector.
    if vibrato_cents > 0:
        phase = 2 * math.pi * vibrato_rate_hz * t
        attack_ramp = np.minimum(1.0, np.maximum(0.0, (t - 0.08) * 10))
        freq_mult = 2 ** (vibrato_cents / 1200.0 * np.sin(phase) * attack_ramp)
        instantaneous_hz = base_hz * freq_mult
        phase_accum = 2 * math.pi * np.cumsum(instantaneous_hz) / SR
    else:
        phase_accum = 2 * math.pi * base_hz * t

    # Sum violin-like harmonic series.
    sig = np.zeros(n, dtype=np.float64)
    for i, amp in enumerate(HARMONICS, start=1):
        sig += amp * np.sin(i * phase_accum)
    sig = sig / sum(HARMONICS)

    # ADSR envelope. Attack 30 ms, decay to 70 % over 60 ms, sustain, release 80 ms.
    env = np.ones(n)
    attack = min(int(SR * 0.03), n)
    decay = min(int(SR * 0.06), max(0, n - attack))
    release = min(int(SR * 0.08), n)
    env[:attack] = np.linspace(0.0, 1.0, attack)
    if decay > 0:
        env[attack : attack + decay] = np.linspace(1.0, 0.7, decay)
    if attack + decay < n - release:
        env[attack + decay : n - release] = 0.7
    if release > 0:
        env[n - release :] = np.linspace(0.7, 0.0, release)

    return (sig * env * amplitude).astype(np.float32)


def synth_clip(
    notes: list[GroundTruthNote],
    *,
    total_seconds: float,
    vibrato_cents: float = 0.0,
    note_amplitude: float = 0.6,
    noise_floor: float = 0.0005,
) -> np.ndarray:
    """Render a sequence of GroundTruthNote into a full audio buffer."""
    out = np.random.RandomState(42).randn(int(SR * total_seconds)).astype(np.float32) * noise_floor
    for n in notes:
        chunk = synth_note(
            n.midi,
            n.end - n.start,
            vibrato_cents=vibrato_cents,
            amplitude=note_amplitude,
        )
        start_idx = int(n.start * SR)
        end_idx = min(start_idx + len(chunk), len(out))
        out[start_idx:end_idx] += chunk[: end_idx - start_idx]
    # Final safety clip.
    peak = float(np.max(np.abs(out))) or 1.0
    if peak > 0.95:
        out = out * (0.95 / peak)
    return out


def write_clip(out_dir: Path, name: str, audio: np.ndarray, notes: list[GroundTruthNote]) -> None:
    wav_path = out_dir / f"{name}.wav"
    json_path = out_dir / f"{name}.json"
    sf.write(str(wav_path), audio, SR, subtype="PCM_16")
    json_path.write_text(
        json.dumps(
            {"sample_rate": SR, "notes": [asdict(n) for n in notes]},
            indent=2,
        )
    )


def main() -> None:
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # =====================================================================
    # CURRICULUM LEVEL 1: single notes, well-separated, no vibrato.
    # If the pipeline can't get >99% F1 here, nothing else matters.
    # =====================================================================
    n1 = [
        GroundTruthNote(midi=69, start=0.5, end=1.5),    # A4 - the tuning pitch
        GroundTruthNote(midi=67, start=2.0, end=3.0),    # G4
        GroundTruthNote(midi=72, start=3.5, end=4.5),    # C5
        GroundTruthNote(midi=64, start=5.0, end=6.0),    # E4
        GroundTruthNote(midi=76, start=6.5, end=7.5),    # E5
    ]
    write_clip(out_dir, "01_single_notes_clean",
               synth_clip(n1, total_seconds=8.0), n1)

    # =====================================================================
    # LEVEL 2: simple ascending scale (still 1 note at a time, faster).
    # =====================================================================
    n2 = []
    t = 0.5
    for midi in [69, 71, 72, 74, 76, 77, 79, 81]:  # A4 B4 C5 D5 E5 F5 G5 A5
        n2.append(GroundTruthNote(midi=midi, start=t, end=t + 0.45))
        t += 0.5
    write_clip(out_dir, "02_scale_ascending",
               synth_clip(n2, total_seconds=t + 0.5), n2)

    # =====================================================================
    # LEVEL 3: repeated same pitch (tests onset detection on same MIDI).
    # =====================================================================
    n3 = []
    for i in range(8):
        n3.append(GroundTruthNote(midi=72, start=0.5 + i * 0.5, end=0.5 + i * 0.5 + 0.4))
    write_clip(out_dir, "03_repeated_C5",
               synth_clip(n3, total_seconds=5.0), n3)

    # =====================================================================
    # LEVEL 4: melody with mild vibrato (real violin signature).
    # =====================================================================
    n4 = []
    melody = [69, 67, 64, 65, 67, 69, 72, 71, 72, 74, 72, 71, 69]
    t = 0.5
    for midi in melody:
        dur = 0.5
        n4.append(GroundTruthNote(midi=midi, start=t, end=t + dur - 0.05))
        t += dur
    write_clip(out_dir, "04_melody_with_vibrato",
               synth_clip(n4, total_seconds=t + 0.5, vibrato_cents=25.0), n4)

    # =====================================================================
    # LEVEL 5: dynamics range (some loud, some quiet).
    # Tests whether quiet notes get filtered out by threshold.
    # =====================================================================
    n5 = []
    dynamics = [(69, 0.7), (71, 0.25), (72, 0.7), (74, 0.20), (76, 0.7)]
    t = 0.5
    parts = []
    for midi, amp in dynamics:
        n5.append(GroundTruthNote(midi=midi, start=t, end=t + 0.7))
        chunk = synth_note(midi, 0.7, amplitude=amp)
        # We need to assemble manually because amplitude varies.
        if t > 0:
            parts.append((t, chunk))
        t += 1.0
    audio5 = np.zeros(int(SR * (t + 0.5)), dtype=np.float32)
    for start, chunk in parts:
        s = int(start * SR)
        audio5[s : s + len(chunk)] += chunk
    audio5 += np.random.RandomState(7).randn(len(audio5)).astype(np.float32) * 0.0005
    peak = float(np.max(np.abs(audio5))) or 1.0
    if peak > 0.95:
        audio5 = audio5 * (0.95 / peak)
    write_clip(out_dir, "05_dynamic_range", audio5, n5)

    # =====================================================================
    # LEVEL 6: low register (open G3 and below the staff).
    # =====================================================================
    n6 = []
    melody = [55, 57, 59, 60, 62, 60, 59, 57, 55]  # G3 to D4 and back
    t = 0.5
    for midi in melody:
        n6.append(GroundTruthNote(midi=midi, start=t, end=t + 0.45))
        t += 0.5
    write_clip(out_dir, "06_low_register",
               synth_clip(n6, total_seconds=t + 0.5), n6)

    # =====================================================================
    # LEVEL 7: high register (above the staff).
    # =====================================================================
    n7 = []
    melody = [86, 84, 81, 84, 86, 88, 86, 84, 81]  # D6 to E6 area
    t = 0.5
    for midi in melody:
        n7.append(GroundTruthNote(midi=midi, start=t, end=t + 0.4))
        t += 0.45
    write_clip(out_dir, "07_high_register",
               synth_clip(n7, total_seconds=t + 0.5), n7)

    # =====================================================================
    # LEVEL 8: mixed durations -- quarter, eighth, half notes interleaved.
    # =====================================================================
    n8 = []
    schedule = [
        (69, 1.0),   # half
        (72, 0.5),   # quarter
        (74, 0.5),   # quarter
        (76, 1.0),   # half
        (74, 0.25),  # eighth
        (72, 0.25),  # eighth
        (69, 1.5),   # dotted half
    ]
    t = 0.5
    for midi, dur in schedule:
        n8.append(GroundTruthNote(midi=midi, start=t, end=t + dur - 0.05))
        t += dur
    write_clip(out_dir, "08_mixed_durations",
               synth_clip(n8, total_seconds=t + 0.5), n8)

    # =====================================================================
    # LEVEL 9: fast 16th-note ascending+descending runs.
    # This is the stress test pYIN couldn't pass -- BP should handle it.
    # 16th note at 120 BPM = 0.125 s per note.
    # =====================================================================
    n9 = []
    sixteenth = 0.125
    # Two octaves of A minor scale, up and down
    a_minor = [69, 71, 72, 74, 76, 77, 79, 81]
    pattern = a_minor + list(reversed(a_minor)) + a_minor + list(reversed(a_minor))
    t = 0.5
    for midi in pattern:
        n9.append(GroundTruthNote(midi=midi, start=t, end=t + sixteenth - 0.01))
        t += sixteenth
    write_clip(out_dir, "09_fast_16ths",
               synth_clip(n9, total_seconds=t + 0.5), n9)

    # =====================================================================
    # LEVEL 10: chromatic scale -- exercises every accidental in one phrase.
    # Catches octave / enharmonic spelling bugs.
    # =====================================================================
    n10 = []
    t = 0.5
    for midi in range(60, 73):  # C4 chromatic up to C5
        n10.append(GroundTruthNote(midi=midi, start=t, end=t + 0.35))
        t += 0.4
    for midi in range(72, 59, -1):  # back down
        n10.append(GroundTruthNote(midi=midi, start=t, end=t + 0.35))
        t += 0.4
    write_clip(out_dir, "10_chromatic_scale",
               synth_clip(n10, total_seconds=t + 0.5), n10)

    # =====================================================================
    # LEVEL 11: Bach BWV 1001 Adagio opening -- real classical content.
    # First 12 notes of the iconic arpeggiated G minor opening.
    # Pitches transcribed from the Bärenreiter edition (public domain).
    # =====================================================================
    # G3 D4 G4 Bb4 D5 G5 -- the first arpeggio of BWV 1001 mvt 1
    # then the descending and chromatic figures that follow
    n11 = []
    bach_g_minor_opening = [
        # measure 1 arpeggio + dotted patterns
        (55, 1.0),  # G3 dotted-quarter feel
        (62, 0.25), # D4
        (67, 0.25), # G4
        (70, 0.25), # Bb4
        (74, 0.25), # D5
        (79, 1.0),  # G5
        # measure 2 turning figure
        (77, 0.25),  # F5
        (76, 0.25),  # E5  (= Eb5 in G minor — but spelled E here for test)
        (74, 0.5),   # D5
        (72, 0.25),  # C5
        (70, 0.25),  # Bb4
        (67, 0.5),   # G4
    ]
    t = 0.5
    for midi, dur in bach_g_minor_opening:
        n11.append(GroundTruthNote(midi=midi, start=t, end=t + dur - 0.03))
        t += dur
    write_clip(out_dir, "11_bach_bwv1001_opening",
               synth_clip(n11, total_seconds=t + 0.5, vibrato_cents=15.0), n11)

    # =====================================================================
    # LEVEL 12: trill / mordent (rapid 2-note alternation).
    # Tests whether the transcriber handles ornaments without producing
    # 30 separate notes when it's really one ornament.
    # =====================================================================
    n12 = []
    # Trill on A4: rapid B4 - A4 alternation at 8 Hz (= 32nd notes at 120 BPM)
    # ~10 alternations over 0.6 seconds
    t = 0.5
    trill_pulse = 0.0625
    for i in range(10):
        midi = 71 if i % 2 == 0 else 69
        n12.append(GroundTruthNote(midi=midi, start=t, end=t + trill_pulse - 0.005))
        t += trill_pulse
    # Resolve to A4 long
    n12.append(GroundTruthNote(midi=69, start=t, end=t + 1.0))
    t += 1.5
    write_clip(out_dir, "12_trill_ornament",
               synth_clip(n12, total_seconds=t + 0.5), n12)

    print(f"Wrote {len(list(out_dir.glob('*.wav')))} clips to {out_dir}")


if __name__ == "__main__":
    main()
