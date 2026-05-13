# 小提琴旋律谱

小提琴旋律谱是一款面向音乐学习的 MVP Web 应用：用户上传自己有权使用的音频文件，系统会尝试提取主旋律，生成 MIDI、MusicXML、简谱 JSON 和可编辑音符 JSON，并在浏览器中展示五线谱、简谱、播放和基础修正工具。

这个版本的重点不是华丽界面，而是真实可运行的“音频到练习谱”处理管线。

## MVP 范围

已经支持：

- 上传 `mp3`、`wav`、`m4a`。
- 选择目标乐器：小提琴、人声、长笛、钢琴、吉他、二胡。
- 使用 `ffmpeg` 转换为单声道 WAV，再用 `librosa` 加载为分析友好的 22.05 kHz 单声道。
- 自动识别乐器（YAMNet 可选；缺失时回落到频谱/过零率/pYIN 启发式）。
- 可选启用 Demucs htdemucs_6s 做 6 轨分离（vocals/drums/bass/guitar/piano/other）并按目标乐器选 stem。
- **单音乐器（小提琴/人声/长笛/二胡）走 pYIN 单音音高跟踪 + onset 检测**，绕开 Basic Pitch 通用多音模型在单音乐器上的过度切片与 octave error。
- **复音乐器（钢琴/吉他）走 Basic Pitch，但用按乐器调过的 onset/frame 阈值与频率窗**。
- `librosa.beat` 估计 BPM 和拍点，onset/duration 量化到 16 分音符 + 三连音网格；自动 3/4 vs 4/4 判别。
- 调号通过 music21 对量化后的音符做 Krumhansl-Schmuckler 分析。
- 多 Part music21 Score：合谱 MusicXML/MIDI + `tracks/{乐器}.musicxml`、`tracks/{乐器}.mid` 单独导出。
- 生成简化简谱 JSON 和可编辑音符 JSON。
- 浏览器内渲染 MusicXML，显示简谱，播放生成旋律。
- 编辑音高、时值，删除音符，半音升降，并重新生成谱子。
- 小提琴目标下检测到 G3 以下音符时给出音域警告。
- 当本机没有 librosa 或 v2 路径抛异常时，自动回退到原 ffmpeg + Basic Pitch 通用模型路径，并写诊断日志。

暂不支持：

- 不接入 QQ 音乐、Spotify、Apple Music、网易云音乐或任何外部音乐平台。
- 不绕过 DRM，不处理加密或受保护的流媒体音频。
- 不承诺用户拥有转写商业歌曲的法律权限。
- htdemucs_6s 把所有弓弦/管乐归到 `other` stem——把弦乐四重奏里的小提琴单独抽出来需要专用模型（roadmap）。
- 不做小提琴指法、弓法、把位、PDF 导出和高级排版。
- 复杂混拍、32 分音符、装饰音目前仍需人工修正。

请上传你有权使用的音频。AI 转写可能出错，导出前请检查并修正音符。

## 目录结构

```text
apps/
  api/   FastAPI 后端和音频处理管线
  web/   Next.js 前端
docs/    产品、架构、API、设置和测试文档
scripts/ 开发辅助脚本
storage/ 本地上传、转换文件、输出文件和任务元数据
```

## 环境要求

- Python 3.9 或更高版本
- Node.js 20 或更高版本
- `ffmpeg` 已安装并在 `PATH` 中可用
- Spotify Basic Pitch Python 包
- `music21` Python 包

macOS 安装 ffmpeg：

```bash
brew install ffmpeg
```

## 后端启动

一键安装：

```bash
./scripts/setup.sh
```

手动启动：

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

默认本地存储目录是仓库根目录下的 `storage/`。可以覆盖：

```bash
export MELODYSHEET_STORAGE_PATH=/absolute/path/to/storage
```

Basic Pitch 在 macOS 上通常可以使用自带 CoreML 模型。Linux 或其他环境如果模型运行时报错，可以安装 `basic-pitch[onnx]` 或 `basic-pitch[tf]`，并按需设置：

```bash
export MELODYSHEET_BASIC_PITCH_MODEL_PATH=/absolute/path/to/model
```

可选启用 Demucs htdemucs_6s 六轨分离：

```bash
pip install demucs
```

只要 `demucs` 命令在 PATH 中，v2 管线会自动调用 htdemucs_6s（vocals/drums/bass/guitar/piano/other），并按目标乐器挑选 stem。**无需**再设环境变量。

旧的 `MELODYSHEET_ENABLE_DEMUCS_SEPARATION=true` 仅在 v2 不可用回退到 v1 时控制是否做人声/伴奏二分离。

可选乐器识别（YAMNet）：

```bash
pip install tensorflow tensorflow-hub
```

可选 CREPE 单音深度音高跟踪器（在 pYIN 已经不够准的录音上有进一步提升）：

```bash
pip install crepe
```

## 前端启动

```bash
cd apps/web
npm install
npm run dev
```

打开 [http://localhost:3000](http://localhost:3000)。

如果后端地址不是默认值：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

## 测试

后端测试：

```bash
cd apps/api
pytest
```

前端类型检查：

```bash
npm --prefix apps/web run typecheck
```

针对运行中的后端做端到端 API 烟测：

```bash
python3 scripts/e2e-api-smoke.py http://127.0.0.1:8000
```

更多手动检查见 [docs/testing.md](docs/testing.md)。

## 常见问题

- `未找到 ffmpeg。请先安装 ffmpeg，并确认它在 PATH 中。`
  安装 ffmpeg 后重新启动后端。

- `未安装 Spotify Basic Pitch，或无法导入该依赖。`
  激活后端虚拟环境，运行 `pip install -r requirements.txt`。

- `Basic Pitch 转写失败。`
  查看 `storage/outputs/{job_id}/basic_pitch.log`，确认 Basic Pitch 模型运行时可用，并尝试更短、更清晰的录音。

- 五线谱渲染失败，但 MusicXML 可以下载。
  可以下载 MusicXML 后用 MuseScore 等软件检查；浏览器渲染器可能不支持某些生成内容。

- 扒谱准确性差。
  尽量上传 60 秒以内、主旋律清楚、伴奏少、混响少的录音。如果是多乐器混音，请 `pip install demucs` 让管线自动跑 htdemucs_6s 六轨分离；想识别音频里有什么乐器，请 `pip install tensorflow-hub`。这些都是可选依赖，没装也能跑，只是会回退到精度更低的路径。

- v2 路径偶尔报错怎么办？
  打开 `storage/outputs/{job_id}/v2_error.log` 看完整 traceback；管线会自动回退到 v1 兼容路径，所以你仍然能拿到谱子，只是精度会下降。常见原因：录音过短（pYIN 需要至少几秒连续音频）、采样率异常、librosa/soundfile 版本与 macOS 上的 Accelerate 冲突。
