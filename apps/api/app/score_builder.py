from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Mapping from our internal target_instrument names to (music21 Instrument factory key,
# clef preference). The Instrument factory mapping is resolved lazily inside the
# builder because music21 is an optional import in tests.
TARGET_TO_CLEF: dict[str, str] = {
    "violin": "treble",
    "vocal": "treble",
    "flute": "treble",
    "guitar": "treble",
    "erhu": "treble",
    "trumpet": "treble",
    "saxophone": "treble",
    "piano": "treble",
    "bass": "bass",
    "cello": "bass",
    "drums": "percussion",
}

TARGET_LABELS: dict[str, str] = {
    "violin": "小提琴",
    "vocal": "人声",
    "flute": "长笛",
    "guitar": "吉他",
    "piano": "钢琴",
    "erhu": "二胡",
    "bass": "贝斯",
    "cello": "大提琴",
    "drums": "鼓",
    "trumpet": "小号",
    "saxophone": "萨克斯",
}


@dataclass
class Track:
    target_instrument: str
    notes: list[dict[str, Any]] = field(default_factory=list)
    detected_key: str = "C major"
    tempo_bpm: int = 90
    meter: str = "4/4"


def _make_music21_instrument(instrument_module: Any, target_instrument: str) -> Any:
    mapping = {
        "violin": instrument_module.Violin,
        "vocal": instrument_module.Vocalist,
        "flute": instrument_module.Flute,
        "guitar": instrument_module.Guitar,
        "piano": instrument_module.Piano,
        "trumpet": instrument_module.Trumpet,
        "saxophone": instrument_module.Saxophone,
        "bass": instrument_module.AcousticBass,
        "cello": instrument_module.Violoncello,
        "drums": instrument_module.UnpitchedPercussion,
    }
    factory = mapping.get(target_instrument)
    if factory is not None:
        return factory()
    generated = instrument_module.Instrument()
    generated.instrumentName = TARGET_LABELS.get(target_instrument, target_instrument.title())
    return generated


def _make_clef(clef_module: Any, target_instrument: str) -> Any:
    name = TARGET_TO_CLEF.get(target_instrument, "treble")
    if name == "bass":
        return clef_module.BassClef()
    if name == "percussion":
        return clef_module.PercussionClef()
    return clef_module.TrebleClef()


def _make_music21_key(key_module: Any, key_name: str) -> Any:
    parts = (key_name or "C major").strip().split()
    if len(parts) == 1:
        parts.append("major")
    tonic = parts[0]
    mode = parts[1].lower()
    return key_module.Key(tonic, mode)


def _build_part(track: Track) -> Any:
    from music21 import clef, duration, instrument, key, meter as m21_meter, note, stream, tempo, tie

    label = TARGET_LABELS.get(track.target_instrument, track.target_instrument.title())
    part = stream.Part(id=label)
    part.partName = label
    part.insert(0, _make_music21_instrument(instrument, track.target_instrument))
    part.insert(0, _make_clef(clef, track.target_instrument))
    part.insert(0, tempo.MetronomeMark(number=int(max(track.tempo_bpm, 30))))
    part.insert(0, m21_meter.TimeSignature(track.meter or "4/4"))
    try:
        part.insert(0, _make_music21_key(key, track.detected_key))
    except Exception:
        part.insert(0, key.Key("C", "major"))

    seconds_per_quarter = 60.0 / max(track.tempo_bpm, 1)
    cursor_quarters = 0.0

    # MusicXML can't express arbitrary quarter-lengths, only standard note types
    # plus dotted variants. We pre-compute the set of representable durations so
    # leading rests and split rests use values that round-trip cleanly.
    standard_quarter_lengths = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.375, 0.25, 0.125, 0.0625)

    def split_into_standard(total_quarters: float) -> list[float]:
        result: list[float] = []
        remaining = total_quarters
        while remaining > 0.0625 - 1e-6:
            for candidate in standard_quarter_lengths:
                if remaining + 1e-6 >= candidate:
                    result.append(candidate)
                    remaining -= candidate
                    break
            else:
                break
        return result

    for raw in sorted(track.notes, key=lambda item: (item["start_time"], item["midi_number"])):
        start_quarters = float(raw["start_time"]) / seconds_per_quarter
        duration_quarters = float(
            raw.get("duration_quarters")
            or (raw.get("duration_seconds", 1.0) / seconds_per_quarter)
        )
        if duration_quarters <= 0:
            continue

        if start_quarters - cursor_quarters > 0.125:
            for piece in split_into_standard(start_quarters - cursor_quarters):
                rest = note.Rest()
                rest.duration = duration.Duration(piece)
                part.append(rest)
            cursor_quarters = start_quarters

        # Split notes into tied pieces of standard quarter-lengths so that
        # MusicXML export doesn't fail on values like 2.24 quarters that come
        # out of beat-grid quantization.
        pieces = split_into_standard(duration_quarters) or [0.25]
        first_note = None
        last_note = None
        for piece in pieces:
            try:
                generated = note.Note(raw["pitch"])
            except Exception:
                generated = None
            if generated is None:
                break
            generated.duration = duration.Duration(piece)
            if "confidence" in raw:
                try:
                    generated.editorial.comment = str(raw["confidence"])
                except Exception:
                    pass
            if first_note is None:
                first_note = generated
            if last_note is not None:
                last_note.tie = tie.Tie("continue") if last_note.tie else tie.Tie("start")
                generated.tie = tie.Tie("stop")
            part.append(generated)
            last_note = generated
        cursor_quarters = start_quarters + duration_quarters

    try:
        part.makeMeasures(inPlace=True)
        part.makeAccidentals(inPlace=True)
        # makeNotation handles "inexpressible" durations (e.g. a leading rest of
        # 2.24 quarters) by tying notes/rests across barlines into standard
        # note types. Without this MusicXML export raises on real recordings
        # where the first note doesn't land on a beat.
        part.makeNotation(inPlace=True)
    except Exception:
        pass
    return part


def build_multitrack_score(tracks: list[Track], *, title: str = "MelodySheet 多轨乐谱") -> Any:
    from music21 import metadata, stream

    if not tracks:
        raise ValueError("至少需要一个 Track 才能构建乐谱。")

    score = stream.Score(id="MelodySheetMultiTrack")
    score.insert(0, metadata.Metadata())
    score.metadata.title = title
    score.metadata.composer = "MelodySheet 自动扒谱"
    for track in tracks:
        score.insert(0, _build_part(track))
    return score


def write_score_outputs(score: Any, output_dir: Path, *, prefix: str = "melody") -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    musicxml_path = output_dir / f"{prefix}.musicxml"
    midi_path = output_dir / f"{prefix}.mid"
    score.write("musicxml", fp=str(musicxml_path))
    score.write("midi", fp=str(midi_path))
    return {"musicxml": musicxml_path, "midi": midi_path}
