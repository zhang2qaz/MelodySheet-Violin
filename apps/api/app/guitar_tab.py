"""Convert a list of MIDI notes into 6-string guitar tablature positions.

Standard tuning (low → high): E2 A2 D3 G3 B3 E4
                              40 45 50 55 59 64

For each note we find all viable (string, fret) positions and pick the one
that minimizes:
   |this_fret - prev_fret|  +  0.2 * this_fret  +  string_jump_penalty

This produces playable, low-position tab for melodies in the violin/vocal
range. For pitches above the highest string + 24 frets (E6 = MIDI 88) we
emit `out_of_range = true`.
"""
from __future__ import annotations

from typing import Any


STANDARD_TUNING = (40, 45, 50, 55, 59, 64)  # E A D G B E (string 0 = lowest)
MAX_FRET = 24


def _candidates(midi: int) -> list[tuple[int, int]]:
    """Return [(string_index, fret), ...] options for the given pitch."""
    options: list[tuple[int, int]] = []
    for string_idx, open_pitch in enumerate(STANDARD_TUNING):
        fret = midi - open_pitch
        if 0 <= fret <= MAX_FRET:
            options.append((string_idx, fret))
    return options


def midi_to_tab(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each note with optimal (string, fret). Returns a NEW list
    of note dicts with `string` and `fret` keys added (or `out_of_range`).
    """
    result: list[dict[str, Any]] = []
    prev_string = 3   # G string is the center-of-gravity for melodies
    prev_fret = 0
    for note in notes:
        midi = int(note.get("midi_number", 0))
        opts = _candidates(midi)
        if not opts:
            result.append({**note, "out_of_range": True})
            continue
        # Cost function
        best = min(
            opts,
            key=lambda so: abs(so[1] - prev_fret) + 0.2 * so[1] + abs(so[0] - prev_string) * 0.5,
        )
        s_idx, fret = best
        result.append({**note, "string": s_idx, "fret": fret})
        prev_string = s_idx
        prev_fret = fret
    return result


def render_ascii_tab(annotated_notes: list[dict[str, Any]], *, width: int = 80) -> str:
    """Render a simple ASCII tab string (6 lines, last → first string from top).

    For browser display we prefer the JSON output, but ASCII is handy for
    `.txt` exports and quick eyeballing.
    """
    lines = ["e|", "B|", "G|", "D|", "A|", "E|"]
    if not annotated_notes:
        return "\n".join(line + "-" * width for line in lines)
    for note in annotated_notes:
        if note.get("out_of_range"):
            for i in range(6):
                lines[i] += "X"
            continue
        s = note.get("string")
        fret = note.get("fret")
        if s is None or fret is None:
            continue
        # Print the fret on the right string, dashes elsewhere
        fret_str = str(fret)
        cell_width = max(2, len(fret_str) + 1)
        for i in range(6):
            line_idx = 5 - i  # invert (string 0 → bottom line)
            if line_idx == s:
                lines[i] += fret_str + "-" * (cell_width - len(fret_str))
            else:
                lines[i] += "-" * cell_width
    return "\n".join(lines)
