from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# Map our internal target instrument to the htdemucs_6s stem we should prefer.
# htdemucs_6s outputs: vocals.wav, drums.wav, bass.wav, guitar.wav, piano.wav, other.wav.
# Bowed strings, flutes and erhu all fall under "other" — that's the best Demucs can do
# without a dedicated string-extraction model. We additionally allow combining stems
# when a target is genuinely ambiguous (e.g. violin solo with piano accompaniment).
TARGET_TO_STEMS_6S: dict[str, list[str]] = {
    "vocal": ["vocals"],
    "piano": ["piano"],
    "guitar": ["guitar"],
    "violin": ["other"],
    "flute": ["other"],
    "erhu": ["other"],
    "drums": ["drums"],
    "bass": ["bass"],
}


def demucs_available() -> bool:
    return shutil.which("demucs") is not None


def _sum_wavs(stem_paths: list[Path], output_path: Path) -> Path:
    import numpy as np
    import soundfile as sf

    mix = None
    sr = None
    for path in stem_paths:
        data, current_sr = sf.read(str(path), always_2d=True)
        if sr is None:
            sr = current_sr
            mix = np.zeros_like(data)
        if data.shape != mix.shape:
            length = min(mix.shape[0], data.shape[0])
            mix = mix[:length] + data[:length]
        else:
            mix = mix + data
    if mix is None or sr is None:
        raise RuntimeError("没有可合并的 stem")
    peak = float(max(abs(mix).max(), 1e-9))
    if peak > 1.0:
        mix = mix / peak
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), mix, sr, subtype="PCM_16")
    return output_path


def run_demucs_six_stems(input_wav: Path, work_dir: Path) -> dict[str, Path] | None:
    if not demucs_available():
        return None

    demucs_dir = work_dir / "demucs_6s"
    log_path = work_dir / "demucs_6s.log"
    if demucs_dir.exists():
        shutil.rmtree(demucs_dir)
    demucs_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "demucs",
        "-n",
        "htdemucs_6s",
        "-o",
        str(demucs_dir),
        str(input_wav),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    log_path.write_text(f"{result.stdout}\n{result.stderr}", encoding="utf-8")
    if result.returncode != 0:
        return None

    stems: dict[str, Path] = {}
    for stem_name in ("vocals", "drums", "bass", "guitar", "piano", "other"):
        matches = sorted(demucs_dir.glob(f"**/{stem_name}.wav"))
        if matches:
            stems[stem_name] = matches[0]
    return stems or None


def pick_stem_for_target(stems: dict[str, Path], target_instrument: str, fallback: Path, work_dir: Path) -> tuple[Path, list[str]]:
    """Return (stem_path, stem_names_used). Falls back to `fallback` when target is unknown."""
    wanted = TARGET_TO_STEMS_6S.get(target_instrument)
    if not wanted:
        return fallback, []
    available = [name for name in wanted if name in stems]
    if not available:
        return fallback, []
    if len(available) == 1:
        return stems[available[0]], available
    summed = _sum_wavs([stems[name] for name in available], work_dir / "target_stem.wav")
    return summed, available
