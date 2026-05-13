"""User profile system — biases pipeline parameters from past edits.

A real ML fine-tune would require thousands of (audio, score) pairs per user.
Instead we collect lightweight signals from what the user *manually corrected*
after each job, and use them to bias subsequent runs:

  - Most common detected_key  → boost prior probability of that key
  - Most common meter         → seed the meter estimator
  - Min/max midi from manually-kept notes → tighter fmin/fmax for pYIN
  - Median tempo of saved jobs → tempo prior

Persistence:
    ~/.config/melodysheet/profile.json    (Linux/macOS)
    %APPDATA%\MelodySheet\profile.json    (Windows)

API:
    record_correction(target_instrument, notes, detected_key, meter, tempo)
        — called after the user clicks "重新生成乐谱" with edits
    apply_profile(target_instrument, default_params) -> dict
        — called by the pipeline to merge user prefs into defaults
    reset_profile(target_instrument=None)
        — clear all or a single instrument's profile
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from pathlib import Path
from typing import Any


def _profile_path() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "MelodySheet"
    elif os.name == "nt":
        base = Path(os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")) / "MelodySheet"
    else:
        base = Path(os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")) / "MelodySheet"
    base.mkdir(parents=True, exist_ok=True)
    return base / "profile.json"


def _load() -> dict[str, Any]:
    path = _profile_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    try:
        _profile_path().write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
    except Exception:
        pass


def record_correction(
    target_instrument: str,
    notes: list[dict[str, Any]],
    *,
    detected_key: str | None = None,
    meter: str | None = None,
    tempo_bpm: int | None = None,
) -> None:
    """Append signals from this job's final (post-edit) state."""
    if not target_instrument or not notes:
        return
    data = _load()
    bucket = data.setdefault(target_instrument, {})
    if detected_key:
        keys = bucket.setdefault("keys", {})
        keys[detected_key] = keys.get(detected_key, 0) + 1
    if meter:
        meters = bucket.setdefault("meters", {})
        meters[meter] = meters.get(meter, 0) + 1
    if tempo_bpm:
        tempos = bucket.setdefault("tempos", [])
        tempos.append(int(tempo_bpm))
        bucket["tempos"] = tempos[-20:]  # keep last 20

    midi_numbers = [int(n["midi_number"]) for n in notes if "midi_number" in n]
    if midi_numbers:
        bucket["midi_min_observed"] = min(bucket.get("midi_min_observed", 200), min(midi_numbers))
        bucket["midi_max_observed"] = max(bucket.get("midi_max_observed", 0), max(midi_numbers))

    bucket["last_updated_utc"] = _now_iso()
    bucket["correction_count"] = bucket.get("correction_count", 0) + 1
    _save(data)


def apply_profile(target_instrument: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `defaults` with the user's learned preferences merged in."""
    data = _load()
    bucket = data.get(target_instrument, {})
    if not bucket or bucket.get("correction_count", 0) < 3:
        return defaults  # not enough signal yet — don't bias

    merged = dict(defaults)
    keys = bucket.get("keys", {})
    if keys:
        merged["preferred_key"] = max(keys, key=keys.get)
    meters = bucket.get("meters", {})
    if meters:
        merged["preferred_meter"] = max(meters, key=meters.get)
    tempos = bucket.get("tempos", [])
    if tempos:
        merged["preferred_tempo_median"] = int(statistics.median(tempos))
    if "midi_min_observed" in bucket:
        # Use observed range with 2 semitones of margin
        merged["preferred_min_midi"] = max(0, bucket["midi_min_observed"] - 2)
    if "midi_max_observed" in bucket:
        merged["preferred_max_midi"] = min(127, bucket["midi_max_observed"] + 2)
    return merged


def reset_profile(target_instrument: str | None = None) -> None:
    if target_instrument is None:
        _save({})
        return
    data = _load()
    data.pop(target_instrument, None)
    _save(data)


def read_profile() -> dict[str, Any]:
    return _load()


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
