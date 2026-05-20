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


# Tonic pitch classes used to decide whether a key prefers sharp- or
# flat-spellings for chromatic notes. Anything in SHARP_KEY_TONICS prefers
# sharps (C# rather than Db), anything in FLAT_KEY_TONICS prefers flats.
# C major / A minor are neutral -- we default to flats there (matches the
# spelling _midi_to_name uses internally in transcribe_mono.py, so the
# round-trip stays consistent).
_SHARP_KEY_TONICS = {"G", "D", "A", "E", "B", "F#", "C#"}
_FLAT_KEY_TONICS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"}

# Two spellings of the 12-tone chromatic scale -- pick one based on the
# detected key. This is what guarantees 简谱 (which uses
# scale_degree_for_pitch) and 五线谱 (built here) agree on every
# accidental: BOTH derive from the same MIDI number through the same
# key-context spelling, instead of two parallel paths through music21
# that can disagree under enharmonic respelling.
_SHARP_SPELLINGS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_SPELLINGS  = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def _midi_to_canonical_pitch_string(midi: int, detected_key: str) -> str:
    """Convert a MIDI number to a pitch string (e.g. 'Bb4') using the
    detected key's accidental preference.

    Why this exists: the audio pipeline writes each note's 'pitch' as a
    string produced by transcribe_mono's `_midi_to_name`, which uses a
    FIXED hybrid spelling (C, C#, D, Eb, E, F, F#, G, Ab, A, Bb, B).
    That spelling is inconsistent with most keys -- e.g. it always writes
    'Bb' even in B major (where it would clash with the F# / C# / etc
    in the key signature) or in G major (where 'A#' is more natural in
    a melodic context). When music21 then renders this through
    makeAccidentals, it sometimes respells the note to fit the key,
    causing the staff view to show different accidentals than the
    numbered notation derived from the SAME MIDI number.

    Fix: derive the pitch string here, from MIDI + key tonic, using the
    same accidental-direction preference the key signature shows. Both
    the staff and the numbered notation now derive from MIDI through
    this single canonical path, so they cannot disagree.
    """
    tonic = (detected_key or "C major").strip().split()[0] if detected_key else "C"
    if tonic in _SHARP_KEY_TONICS:
        spelling = _SHARP_SPELLINGS
    elif tonic in _FLAT_KEY_TONICS:
        spelling = _FLAT_SPELLINGS
    else:
        # C major / A minor and unrecognised keys -> default to flats so the
        # result matches transcribe_mono._midi_to_name (which uses flats for
        # Eb / Ab / Bb). Choosing sharps here would silently change spelling
        # for every C-major recording in the corpus.
        spelling = _FLAT_SPELLINGS
    pitch_class = int(midi) % 12
    octave = int(midi) // 12 - 1
    return f"{spelling[pitch_class]}{octave}"


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

    # =====================================================================
    # SCORE-SANITY DURATION GRID
    #
    # We deliberately cap the rest grid at 16th notes (0.25 quarter). The
    # previous implementation allowed 32nd and 64th rests (0.125 / 0.0625
    # quarter) which gave music21 the leeway to render gaps like 1.0625
    # quarter as "quarter rest + 64th rest". On user-uploaded violin
    # recordings this produced visually busy scores littered with tiny
    # rest symbols that aren't musically meaningful -- the original
    # performer's micro-timing variance below a 16th note isn't
    # information a violin student practicing from the score needs to
    # see, just noise.
    #
    # Notes themselves still allow 32nd / 16th durations (handled when
    # the note is converted to music21.note.Note), so genuinely fast
    # passages aren't restricted. Only the rest grid is coarsened.
    # =====================================================================
    standard_quarter_lengths = (4.0, 3.0, 2.0, 1.5, 1.0, 0.75, 0.5, 0.375, 0.25)
    MIN_REST_QUARTERS = 0.25   # rest >= 16th note or drop entirely
    MIN_GAP_TO_INSERT_REST = 0.25

    def split_into_standard(total_quarters: float) -> list[float]:
        result: list[float] = []
        remaining = total_quarters
        while remaining > MIN_REST_QUARTERS - 1e-6:
            for candidate in standard_quarter_lengths:
                if remaining + 1e-6 >= candidate:
                    result.append(candidate)
                    remaining -= candidate
                    break
            else:
                break
        return result

    # =====================================================================
    # RHYTHMIC-SLOT TILING (the "read like 简谱" fix)
    #
    # Basic Pitch reports each note's ACOUSTIC length -- how long the
    # string actually rang. That is shorter than the note's RHYTHMIC
    # VALUE (how many beats the note occupies) because a violinist
    # detaches notes: a quarter note rings ~0.8 beat then 0.2 beat of
    # bow-lift silence. The old code notated that 0.2 beat as a REST,
    # producing scores littered with tiny junk rests that don't exist
    # in the numbered notation.
    #
    # Fix: each note's displayed duration = distance to the NEXT note's
    # onset (snapped to standard note values). Every note tiles its own
    # rhythmic slot; small detache gaps vanish. A rest is inserted ONLY
    # when the gap to the next note is genuinely large (>= 2 beats) --
    # an actual musical pause, not articulation noise.
    # =====================================================================
    REST_GAP_THRESHOLD_QUARTERS = 2.0  # only gaps >= a half note become rests

    sorted_notes = sorted(track.notes, key=lambda item: (item["start_time"], item["midi_number"]))
    for note_index, raw in enumerate(sorted_notes):
        start_quarters = float(raw["start_time"]) / seconds_per_quarter
        acoustic_duration_quarters = float(
            raw.get("duration_quarters")
            or (raw.get("duration_seconds", 1.0) / seconds_per_quarter)
        )
        if acoustic_duration_quarters <= 0:
            continue

        # Distance to the next note's onset -- the rhythmic slot this note
        # should occupy.
        if note_index + 1 < len(sorted_notes):
            next_start_quarters = (
                float(sorted_notes[note_index + 1]["start_time"]) / seconds_per_quarter
            )
            slot_quarters = next_start_quarters - start_quarters
        else:
            # Last note: no successor. Use its own acoustic length.
            slot_quarters = acoustic_duration_quarters

        gap_after = slot_quarters - acoustic_duration_quarters
        if gap_after >= REST_GAP_THRESHOLD_QUARTERS:
            # Genuine musical pause: note keeps its acoustic length, the
            # gap becomes a rest (handled below after the note is emitted).
            duration_quarters = acoustic_duration_quarters
            rest_quarters = gap_after
        else:
            # Small detache gap: note fills the whole slot, no rest.
            duration_quarters = max(slot_quarters, acoustic_duration_quarters)
            rest_quarters = 0.0

        # Leading rest before the very first note, if it starts late.
        if start_quarters - cursor_quarters > REST_GAP_THRESHOLD_QUARTERS:
            for piece in split_into_standard(start_quarters - cursor_quarters):
                rest = note.Rest()
                rest.duration = duration.Duration(piece)
                part.append(rest)
            cursor_quarters = start_quarters

        # Canonical pitch derivation: re-spell from MIDI + detected_key
        # so the staff view uses the SAME accidental as the numbered
        # notation. Falls back to whatever the upstream pipeline wrote
        # in raw["pitch"] if MIDI isn't present (legacy data shape).
        midi_for_note = raw.get("midi_number")
        if isinstance(midi_for_note, (int, float)):
            canonical_pitch_str = _midi_to_canonical_pitch_string(
                int(midi_for_note), track.detected_key
            )
        else:
            canonical_pitch_str = raw.get("pitch", "C4")

        pieces = split_into_standard(duration_quarters) or [0.25]
        first_note = None
        last_note = None
        for piece in pieces:
            try:
                generated = note.Note(canonical_pitch_str)
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

        # Emit a rest ONLY for a genuine multi-beat musical pause.
        if rest_quarters >= REST_GAP_THRESHOLD_QUARTERS:
            for piece in split_into_standard(rest_quarters):
                rest = note.Rest()
                rest.duration = duration.Duration(piece)
                part.append(rest)
            cursor_quarters += rest_quarters

    try:
        part.makeMeasures(inPlace=True)
        # cautionaryAll=True: force EVERY note to carry an explicit <accidental>
        # tag in the MusicXML output (natural/sharp/flat as appropriate), even
        # when the accidental matches the key signature. This is a defensive
        # measure: OpenSheetMusicDisplay has historically had subtle bugs where
        # an implicit accidental from a key signature is interpreted
        # differently than an explicit one. Users reported "五线谱走调" --
        # different pitches displayed than the piano-roll / 简谱 -- which is
        # only possible if the renderer is applying the key-signature accidental
        # against the data's intent. By writing every accidental explicitly we
        # remove any room for the renderer to deviate from our MIDI numbers.
        # The trade-off is a visually busier staff (lots of naturals showing
        # explicitly) but the data is 100% unambiguous.
        part.makeAccidentals(inPlace=True, cautionaryAll=True)
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
    lily_path = output_dir / f"{prefix}.ly"
    abc_path = output_dir / f"{prefix}.abc"
    score.write("musicxml", fp=str(musicxml_path))
    score.write("midi", fp=str(midi_path))
    # LilyPond and ABC formats: best-effort, music21 supports both natively.
    # These are non-fatal extras for users who use those engravers.
    try:
        score.write("lily", fp=str(lily_path))
    except Exception:
        lily_path = None  # type: ignore[assignment]
    try:
        score.write("abc", fp=str(abc_path))
    except Exception:
        abc_path = None  # type: ignore[assignment]
    return {
        "musicxml": musicxml_path,
        "midi": midi_path,
        "lily": lily_path,
        "abc": abc_path,
    }
