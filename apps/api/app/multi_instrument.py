"""Transcribe every Demucs-separated stem in parallel into its own Part.

Returns a list of `Track` instances ready to be combined into a multi-Part
music21 score. Each Track is keyed by the original stem name (vocals, drums,
bass, guitar, piano, other) so the frontend can show per-instrument outputs.

Routing rules:
- vocals  → transcribe as monophonic (target_instrument="vocal")
- bass    → transcribe as monophonic (target_instrument="bass")
- piano   → transcribe as polyphonic
- guitar  → transcribe as polyphonic
- other   → transcribe as monophonic with violin profile (most likely strings)
- drums   → skipped (handled by drum_transcribe.py separately)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Mapping from Demucs stem → (target_instrument, transcription_mode).
STEM_ROUTING: dict[str, tuple[str, str]] = {
    "vocals": ("vocal", "mono"),
    "bass": ("bass", "mono"),
    "piano": ("piano", "poly"),
    "guitar": ("guitar", "poly"),
    "other": ("violin", "mono"),  # best default for orchestral / strings / wind
}


def transcribe_all_stems(
    stems_dir: Path,
    sample_rate_hint: int = 22050,
) -> dict[str, list[dict[str, Any]]]:
    """Run the appropriate transcriber for each stem.

    Returns: dict mapping stem_name -> list of note dicts (one per detected note).
    Stems that produce no notes are still included with an empty list so the UI
    can show 'no notes detected' for that instrument.
    """
    from app.audio_io import load_audio_mono
    from app.transcribe_mono import transcribe_monophonic
    from app.transcribe_poly import transcribe_polyphonic_to_notes

    per_stem_notes: dict[str, list[dict[str, Any]]] = {}
    for stem_name, (target, mode) in STEM_ROUTING.items():
        stem_wav = stems_dir / f"{stem_name}.wav"
        if not stem_wav.exists():
            continue
        try:
            if mode == "mono":
                audio, sr = load_audio_mono(stem_wav, sample_rate=sample_rate_hint)
                notes = transcribe_monophonic(audio, sr, target)
            else:  # poly
                notes = transcribe_polyphonic_to_notes(stem_wav, target)
            per_stem_notes[stem_name] = notes
        except Exception:
            per_stem_notes[stem_name] = []
    return per_stem_notes
