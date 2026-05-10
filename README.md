# 小提琴旋律谱

小提琴旋律谱是一款面向音乐学习的 MVP Web 应用：用户上传自己有权使用的音频文件，系统会尝试提取主旋律，生成 MIDI、MusicXML、简谱 JSON 和可编辑音符 JSON，并在浏览器中展示五线谱、简谱、播放和基础修正工具。

这个版本的重点不是华丽界面，而是真实可运行的“音频到练习谱”处理管线。

## MVP 范围

已经支持：

- 上传 `mp3`、`wav`、`m4a`。
- 选择目标乐器：小提琴、人声、长笛、钢琴、吉他、二胡。
- 使用 `ffmpeg` 转换为单声道 WAV。
- 在转写前按目标乐器做基础频段降噪、动态归一化和音域过滤。
- 可选启用 Demucs 做人声/伴奏二分离。
- 使用 Spotify Basic Pitch 生成 MIDI。
- 使用 `music21` 解析 MIDI、估计调号/速度、导出 MusicXML。
- 生成简化简谱 JSON 和可编辑音符 JSON。
- 浏览器内渲染 MusicXML，显示简谱，播放生成旋律。
- 编辑音高、时值，删除音符，半音升降，并重新生成谱子。
- 小提琴目标下检测到 G3 以下音符时给出音域警告。

暂不支持：

- 不接入 QQ 音乐、Spotify、Apple Music、网易云音乐或任何外部音乐平台。
- 不绕过 DRM，不处理加密或受保护的流媒体音频。
- 不承诺用户拥有转写商业歌曲的法律权限。
- 不保证复杂伴奏、多乐器混音、强混响录音能准确扒谱。
- 不做小提琴指法、弓法、把位、PDF 导出和高级排版。
- 不假装已经完成专业级多乐器音色分轨；当前是目标乐器频段/音域清理、主旋律筛选，以及可选的人声/伴奏分离。

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

可选启用 Demucs 人声/伴奏二分离：

```bash
pip install demucs
export MELODYSHEET_ENABLE_DEMUCS_SEPARATION=true
```

说明：当前 Demucs 只作为可选预处理，用于人声/伴奏方向的粗分离；它不是任意乐器的精确音色分轨。

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
  尽量上传 60 秒以内、主旋律清楚、伴奏少、混响少的录音。这个版本已加入基础降噪、目标乐器音域过滤和单线主旋律筛选，但复杂混音仍然需要更强的分离模型和人工修正。
