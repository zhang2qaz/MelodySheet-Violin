# 架构说明

## 前端

前端位于 `apps/web`，使用 Next.js App Router、TypeScript、Tailwind CSS 和 React。

- `app/page.tsx`：中文上传首页。
- `app/jobs/[jobId]/page.tsx`：处理状态页和结果页。
- `components/`：上传、处理进度、五线谱渲染、简谱、播放、下载、摘要和音符编辑器。
- `lib/api.ts`：统一封装后端请求。
- `lib/music.ts`：浏览器端音高、MIDI 编号和半音移调工具。

前端会轮询 `GET /api/jobs/{job_id}`，只有后端真实完成并返回文件链接后才展示结果，不伪造成功状态或谱面。

## 后端

后端位于 `apps/api`，使用 FastAPI 和本地文件存储。

- `main.py`：HTTP API、上传校验、CORS、文件安全访问。
- `app/config.py`：环境变量配置。
- `app/job_store.py`：任务目录和 JSON 元数据读写。
- `app/music_processing.py`：编排管线总入口，负责按需路由到 v2（librosa）或兼容回退路径，并保留所有公共后处理工具函数。
- `app/audio_io.py`：使用 librosa 加载/重采样为 22.05 kHz 单声道，soundfile 写 WAV。
- `app/instrument_id.py`：自动识别录音中的乐器；优先 YAMNet（tensorflow-hub），缺失时回落到频谱/过零率/pYIN 连续性启发式。
- `app/separation.py`：调用 `demucs -n htdemucs_6s` 做 6 轨分离（vocals/drums/bass/guitar/piano/other），并按目标乐器选合适的 stem，必要时叠加多 stem。
- `app/transcribe_mono.py`：单音乐器专用转写。`librosa.pyin` 给出连续 f0 + 置信度，再用 `librosa.onset.onset_detect` 切分音符，按段内 voiced 帧的中位 f0 决定音高 — 这是相对 Basic Pitch 的关键质量提升。
- `app/transcribe_poly.py`：复音乐器走 Basic Pitch，但按目标乐器调过的 onset/frame 阈值和频率窗口；直接读 `note_events`，不再经过 MIDI 文件中转。
- `app/rhythm.py`：`librosa.beat` 估计 BPM 和拍点，把 onset/duration 量化到 16 分音符 + 三连音网格；同时给出 3/4 vs 4/4 的轻量推断。
- `app/score_builder.py`：构造 music21 多 Part Score，每个目标乐器独立 Part，绑定相应 Instrument/Clef/Key/Meter，并调用 `makeMeasures` + `makeAccidentals` 切小节加临时记号。
- `app/models.py`：请求/响应模型。

## 处理管线（v2 默认；缺依赖时自动回退到 v1）

1. 用户上传 `mp3`、`wav` 或 `m4a`，并选择目标乐器。
2. 后端校验格式、大小和空文件。
3. 原始文件保存到 `storage/uploads/{job_id}/original.{ext}`。
4. 任务元数据保存到 `storage/jobs/{job_id}.json`。
5. `ffmpeg` 转换为单声道 44.1 kHz WAV：`storage/converted/{job_id}/input.wav`。
6. `audio_io` 用 librosa 把整曲加载为 22.05 kHz 单声道数组。
7. `instrument_id` 自动识别乐器（YAMNet 可选，否则启发式），结果写入 `result.detected_instruments`。
8. 如果安装了 `demucs`，调用 htdemucs_6s 做 6 轨分离；按目标乐器挑选对应 stem（可能叠加多 stem）。否则使用整曲作为目标音频。
9. `rhythm` 估计速度 BPM、拍点序列和拍号。
10. **分两条转写路线**：
    - **单音乐器（小提琴/人声/长笛/二胡）**：`transcribe_mono` 用 `librosa.pyin` 跟踪 f0，配合 onset 检测切分音符，按段中位 f0 决定音高；merge 相邻同音段消除颤音抖动。
    - **复音乐器（钢琴/吉他）**：`transcribe_poly` 调用 Basic Pitch（已按乐器调阈值/频率窗），直接读 `note_events`。
11. `prepare_notes_for_target` 按目标乐器音域过滤；单音目标进一步压成单线旋律。
12. `quantize_notes_to_grid` 把 onset/duration 锁到拍点网格（默认 16 分；自动检测三连音段）。
13. 调号通过 music21 对量化后的音符序列做 Krumhansl-Schmuckler 分析。
14. `score_builder` 构造多 Part music21 Score：合谱 + 每个乐器一份单独的 MusicXML/MIDI。
15. 输出 `melody.mid`、`melody.musicxml`、`tracks/{instrument}.musicxml`、`tracks/{instrument}.mid`、`numbered.json`、`notes.json`。

> v1 回退路径：当本机没装 librosa 或 v2 路径抛异常时，使用原 ffmpeg 频段降噪 + Basic Pitch 通用模型路径，并在 `storage/outputs/{job_id}/` 下写 `v2_fallback.log` 或 `v2_error.log` 便于诊断。

任务状态：

- `uploaded`
- `converting`
- `preprocessing`
- `transcribing`
- `postprocessing`
- `completed`
- `failed`

## 存储结构

```text
storage/
  uploads/{job_id}/original.{ext}
  converted/{job_id}/input.wav
  converted/{job_id}/clean.wav                  # 仅 v1 回退路径生成
  converted/{job_id}/demucs_6s/                 # 仅 v2 + demucs 启用时生成
  converted/{job_id}/target_stem.wav            # 仅在需要叠加多 stem 时生成
  outputs/{job_id}/melody.mid                   # 合谱 MIDI（多 Part）
  outputs/{job_id}/melody.musicxml              # 合谱 MusicXML（多 Part）
  outputs/{job_id}/tracks/{instrument}.musicxml # 分乐器单独乐谱
  outputs/{job_id}/tracks/{instrument}.mid      # 分乐器单独 MIDI
  outputs/{job_id}/numbered.json
  outputs/{job_id}/notes.json
  outputs/{job_id}/v2_fallback.log              # 仅当 librosa 缺失触发回退
  outputs/{job_id}/v2_error.log                 # 仅当 v2 异常触发回退
  jobs/{job_id}.json
```

## 已知限制

- htdemucs_6s 把所有弓弦/管乐都归到 `other` stem。要把弦乐四重奏里的小提琴独立抽出来，需要专用模型（roadmap）。
- pYIN 是当前最优雅的免费单音追踪器，但对短促拨弦/复杂滑音仍可能 octave-error；CREPE（可选）在这些场景表现更好，需要 `pip install crepe`。
- 节拍量化默认 16 分 + 三连音；32 分以及复杂混拍尚未支持。
- 拍号识别只在 3/4 和 4/4 之间二选一；复杂拍子（5/8、7/8、变拍）暂走 4/4。
- MIDI 置信度来自模型输出或 pYIN voiced 概率，不等同于人耳判断。
- MusicXML 适合练习谱草稿；出版级排版建议导出后用 MuseScore 二次整理。
- 端到端依赖：必选 `ffmpeg`、`librosa`、`soundfile`、`basic-pitch`、`music21`；可选 `demucs`、`tensorflow-hub`、`crepe`。
