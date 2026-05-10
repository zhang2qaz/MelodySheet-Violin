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
- `app/music_processing.py`：ffmpeg 转换、基础降噪、可选 Demucs 分离、Basic Pitch 转写、music21 后处理、简谱生成和重新生成。
- `app/models.py`：请求/响应模型。

## 处理管线

1. 用户上传 `mp3`、`wav` 或 `m4a`，并选择目标乐器。
2. 后端校验格式、大小和空文件。
3. 原始文件保存到 `storage/uploads/{job_id}/original.{ext}`。
4. 任务元数据保存到 `storage/jobs/{job_id}.json`。
5. `ffmpeg` 转换为单声道 WAV：`storage/converted/{job_id}/input.wav`。
6. 进入 `preprocessing`：按目标乐器做高通/低通、频谱降噪、动态归一化，输出 `clean.wav`。
7. 如果启用 `MELODYSHEET_ENABLE_DEMUCS_SEPARATION=true` 且本机安装 `demucs`，会先尝试人声/伴奏二分离。
8. Basic Pitch 对清理后的音频生成 `melody.mid`。
9. music21 解析 MIDI，估计速度和调号。
10. 后端按目标乐器音域过滤明显不合适的音符，并从同时发声的音符中优先保留一条主旋律线。
11. 输出 `melody.mid`、`melody.musicxml`、`numbered.json`、`notes.json`。

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
  converted/{job_id}/clean.wav
  outputs/{job_id}/melody.mid
  outputs/{job_id}/melody.musicxml
  outputs/{job_id}/numbered.json
  outputs/{job_id}/notes.json
  jobs/{job_id}.json
```

## 已知限制

- Basic Pitch 对清晰主旋律最有效，复杂伴奏仍可能产生错误音符。
- 当前“音色分轨”是基础预处理和可选人声/伴奏分离，不是完整多乐器分离。
- MIDI 置信度来自可用的 MIDI velocity，不能等同于真实模型概率。
- 调号分析和简谱映射是确定性的近似结果。
- MusicXML 适合练习谱草稿，不是出版级排版。
- 端到端处理依赖本机 `ffmpeg`、Basic Pitch、`music21`，可选依赖 Demucs。
