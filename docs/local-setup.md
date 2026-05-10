# 本地启动

## 后端

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

主要 Python 依赖包括 FastAPI、python-multipart、Spotify Basic Pitch、music21、pytest 和 httpx。

Basic Pitch 自带模型文件，但仍需要本机有可加载模型的运行时。macOS 通常可以使用 CoreML；如果平台无法加载 CoreML，请安装 `basic-pitch[onnx]` 或 `basic-pitch[tf]`，必要时设置 `MELODYSHEET_BASIC_PITCH_MODEL_PATH`。

## ffmpeg

后端会通过子进程调用 `ffmpeg`，真实转写前必须先安装。

macOS：

```bash
brew install ffmpeg
```

Ubuntu/Debian：

```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

## 可选 Demucs

如果希望在人声/伴奏方向做粗分离，可以安装 Demucs 并启用环境变量：

```bash
pip install demucs
export MELODYSHEET_ENABLE_DEMUCS_SEPARATION=true
```

注意：这不是任意乐器的精确分轨，只是转写前的可选辅助预处理。

## 前端

```bash
cd apps/web
npm install
npm run dev
```

前端默认请求 `http://localhost:8000`。如需覆盖：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## 测试音频

生成一个短的合成 WAV：

```bash
python scripts/generate-test-audio.py storage/uploads/test-melody.wav
```

合成正弦波适合检查管线是否跑通，但不能替代真实用户录音测试。
