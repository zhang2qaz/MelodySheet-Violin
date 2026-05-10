# API 契约

本地开发默认地址：`http://localhost:8000`。

## POST `/api/jobs`

上传音频并创建处理任务。

请求类型：`multipart/form-data`

字段：

- `file`：音频文件，支持 `mp3`、`wav`、`m4a`。
- `target_instrument`：可选，默认 `violin`。支持 `violin`、`vocal`、`flute`、`piano`、`guitar`、`erhu`。

成功响应：

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "uploaded"
}
```

常见错误：

- 不支持的文件类型。
- 上传文件为空。
- 文件超过配置大小。
- 不支持的目标乐器。

## GET `/api/jobs/{job_id}`

查询任务状态和结果链接。

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "completed",
  "progress": 100,
  "error": null,
  "result": {
    "original_audio_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/original.wav",
    "midi_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.mid",
    "musicxml_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.musicxml",
    "numbered_json_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/numbered.json",
    "notes_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/notes.json",
    "detected_key": "C",
    "estimated_tempo": 90,
    "note_count": 24,
    "target_instrument": "violin",
    "filtered_note_count": 3,
    "preprocessing_summary": "已按小提琴频段做基础降噪，过滤标准小提琴音域外音符，并从同时发声中优先保留主旋律线。",
    "violin_range_warning": true,
    "violin_range_message": "检测到部分音符低于标准小提琴音域，已在生成谱子前过滤。你也可以尝试升调或选择其他目标乐器。"
  }
}
```

状态值：

- `uploaded`
- `converting`
- `preprocessing`
- `transcribing`
- `postprocessing`
- `completed`
- `failed`

## GET `/api/files/{job_id}/{filename}`

安全下载任务文件。允许文件：

- `original.{ext}`
- `melody.mid`
- `melody.musicxml`
- `numbered.json`
- `notes.json`

接口会拒绝任意路径、隐藏文件和未知文件名。

## POST `/api/jobs/{job_id}/regenerate`

提交用户编辑后的音符，并重新生成 MIDI、MusicXML、简谱 JSON 和 notes JSON。

请求：

```json
{
  "notes": [
    {
      "index": 1,
      "start_time": 0.0,
      "end_time": 0.5,
      "pitch": "C4",
      "midi_number": 60,
      "duration_seconds": 0.5,
      "duration_label": "quarter",
      "confidence": 0.87
    }
  ]
}
```

成功响应：

```json
{
  "job_id": "9f6e1d9a6c0f4c0fb9dbe2a16c23f51a",
  "status": "completed",
  "result": {
    "original_audio_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/original.wav",
    "midi_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.mid",
    "musicxml_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/melody.musicxml",
    "numbered_json_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/numbered.json",
    "notes_url": "/api/files/9f6e1d9a6c0f4c0fb9dbe2a16c23f51a/notes.json",
    "detected_key": "C",
    "estimated_tempo": 90,
    "note_count": 1,
    "target_instrument": "violin",
    "filtered_note_count": 0,
    "preprocessing_summary": "已按小提琴频段做基础降噪，过滤标准小提琴音域外音符，并从同时发声中优先保留主旋律线。",
    "violin_range_warning": false,
    "violin_range_message": null
  }
}
```
