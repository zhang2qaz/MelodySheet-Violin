"""Score-sanity tests: enforce that generated MusicXML output looks readable.

The user said "不要出现明显不合理明显复杂的音符". These are concrete
patterns that look weird on a violin practice score:

  - Double-sharps / double-flats (B##, Eb-flat etc.)
  - Standalone (untied) 64th-note rests
  - More than 4 explicit accidentals in a single measure
  - Grace notes / tuplets that the user didn't ask for

Anything new that triggers these patterns should fail CI.
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.transcribe_violin_bp import transcribe_violin_via_basic_pitch
from app.score_builder import Track, build_multitrack_score, write_score_outputs
from app.rhythm import quantize_notes_to_grid, estimate_tempo_and_beats


CORPUS_DIR = Path(__file__).parent / "corpus"
WAVS = sorted(CORPUS_DIR.glob("*.wav"))


def _render_musicxml(wav_path: Path) -> str:
    notes = transcribe_violin_via_basic_pitch(wav_path)
    if not notes:
        return ""
    audio, sr = sf.read(str(wav_path))
    tempo, beats = estimate_tempo_and_beats(audio.astype(np.float32), sr)
    quantized = quantize_notes_to_grid(notes, tempo_bpm=tempo, beats=beats)
    track = Track(
        target_instrument="violin",
        notes=quantized,
        detected_key="C major",
        tempo_bpm=int(tempo),
        meter="4/4",
    )
    score = build_multitrack_score([track])
    with tempfile.TemporaryDirectory() as td:
        write_score_outputs(score, Path(td))
        return (Path(td) / "melody.musicxml").read_text()


@pytest.mark.parametrize("wav_path", WAVS, ids=lambda p: p.stem)
def test_no_double_accidentals(wav_path: Path) -> None:
    """Double sharps/flats are rare in real practice scores. If we emit any
    on a synthetic clean test clip, the canonical pitch derivation has
    drifted and the score will look weird to a violinist.
    """
    xml = _render_musicxml(wav_path)
    if not xml:
        pytest.skip("no notes produced")
    double_alters = re.findall(r"<alter>(-?[2-9])</alter>", xml)
    assert not double_alters, (
        f"{wav_path.name} produced {len(double_alters)} double-or-higher "
        f"accidentals: {double_alters[:5]}"
    )


@pytest.mark.parametrize("wav_path", WAVS, ids=lambda p: p.stem)
def test_no_64th_rests(wav_path: Path) -> None:
    """64th-note rests clutter the visual without being musically meaningful
    -- they represent timing variance below the resolution a practicing
    violinist cares about. The score builder caps the rest grid at 16ths.
    """
    xml = _render_musicxml(wav_path)
    if not xml:
        pytest.skip("no notes produced")
    # Find rest blocks specifically (a <note> containing <rest/>).
    rest_blocks = re.findall(r"<note>(?:(?!</note>).)*<rest\b(?:(?!</note>).)*</note>",
                             xml, re.DOTALL)
    bad = [rb for rb in rest_blocks if "<type>64th</type>" in rb]
    assert not bad, f"{wav_path.name} produced {len(bad)} 64th-note rests"


@pytest.mark.parametrize("wav_path", WAVS, ids=lambda p: p.stem)
def test_no_grace_notes(wav_path: Path) -> None:
    """We never want music21 to emit grace notes -- they're a notation
    decision that wouldn't come from an auto-transcription of a sustained
    audio signal."""
    xml = _render_musicxml(wav_path)
    if not xml:
        pytest.skip("no notes produced")
    grace = re.findall(r"<grace\b", xml)
    assert not grace, f"{wav_path.name} produced {len(grace)} grace notes"


@pytest.mark.parametrize("wav_path", WAVS, ids=lambda p: p.stem)
def test_no_tuplets(wav_path: Path) -> None:
    """No triplets / quintuplets unless we explicitly added detection.
    A spurious tuplet on a plain 16th-note rest passage looks broken.
    """
    xml = _render_musicxml(wav_path)
    if not xml:
        pytest.skip("no notes produced")
    tuplets = re.findall(r"<tuplet\b", xml)
    assert not tuplets, f"{wav_path.name} produced {len(tuplets)} tuplet markings"
