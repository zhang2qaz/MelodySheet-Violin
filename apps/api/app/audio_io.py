from __future__ import annotations

from pathlib import Path
from typing import Any


DEFAULT_SAMPLE_RATE = 22050


class AudioBackendMissing(RuntimeError):
    pass


def load_audio_mono(path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> tuple[Any, int]:
    try:
        import librosa
    except Exception as exc:
        raise AudioBackendMissing(
            "未安装 librosa，无法做高精度音频特征分析。请在后端虚拟环境中执行 pip install librosa。"
        ) from exc

    audio, sr = librosa.load(str(path), sr=sample_rate, mono=True)
    return audio, int(sr)


def write_wav(audio: Any, path: Path, sample_rate: int = DEFAULT_SAMPLE_RATE) -> Path:
    try:
        import soundfile as sf
    except Exception as exc:
        raise AudioBackendMissing(
            "未安装 soundfile，无法导出 WAV。请在后端虚拟环境中执行 pip install soundfile。"
        ) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), audio, sample_rate, subtype="PCM_16")
    return path


def audio_duration_seconds(audio: Any, sample_rate: int) -> float:
    if audio is None:
        return 0.0
    return float(len(audio)) / float(max(sample_rate, 1))
