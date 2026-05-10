"use client";

import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, FileAudio, Music2, ShieldCheck, UploadCloud } from "lucide-react";
import { createJob } from "@/lib/api";
import type { TargetInstrument } from "@/lib/types";

const ACCEPTED_EXTENSIONS = ["mp3", "wav", "m4a"];
const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || 50);
const TARGET_INSTRUMENT_OPTIONS: Array<{ value: TargetInstrument; label: string; hint: string }> = [
  { value: "violin", label: "小提琴", hint: "默认：适合独奏小提琴、童声旋律、单线旋律练习" },
  { value: "vocal", label: "人声", hint: "适合哼唱、演唱或主唱旋律" },
  { value: "flute", label: "长笛", hint: "适合明亮高音区旋律" },
  { value: "piano", label: "钢琴", hint: "宽音域，适合键盘主旋律" },
  { value: "guitar", label: "吉他", hint: "适合吉他旋律或独奏片段" },
  { value: "erhu", label: "二胡", hint: "适合二胡旋律或接近音区的独奏" },
];

function extensionFor(file: File): string {
  return file.name.split(".").pop()?.toLowerCase() || "";
}

export function UploadPanel() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [targetInstrument, setTargetInstrument] = useState<TargetInstrument>("violin");

  function validateFile(nextFile: File | null) {
    setError(null);
    if (!nextFile) {
      setFile(null);
      return;
    }

    const extension = extensionFor(nextFile);
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setFile(null);
      setError("请选择 mp3、wav 或 m4a 音频文件。");
      return;
    }

    if (nextFile.size === 0) {
      setFile(null);
      setError("所选文件为空。");
      return;
    }

    if (nextFile.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFile(null);
      setError(`所选文件超过 ${MAX_UPLOAD_MB} MB。`);
      return;
    }

    setFile(nextFile);
  }

  function handleInput(event: ChangeEvent<HTMLInputElement>) {
    validateFile(event.target.files?.[0] || null);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    validateFile(event.dataTransfer.files?.[0] || null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setError("请先选择音频文件，再开始转写。");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await createJob(file, targetInstrument);
      router.push(`/jobs/${created.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败，请重试。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="grid flex-1 gap-8 py-10 lg:grid-cols-[minmax(0,1fr)_360px]">
      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          className={`flex min-h-[300px] flex-col items-center justify-center border-2 border-dashed px-6 py-10 text-center transition ${
            dragging
              ? "border-staff bg-staff/8"
              : "border-ink/20 bg-white/55 hover:border-staff/70 hover:bg-white/75"
          }`}
        >
          <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-staff/12 text-staff">
            <UploadCloud className="h-7 w-7" aria-hidden="true" />
          </div>
          <h2 className="text-2xl font-semibold text-ink">上传并生成乐谱</h2>
          <p className="mt-3 max-w-xl text-base leading-7 text-ink/70">
            请上传你有权使用的音频文件。小提琴旋律谱会尝试提取主旋律，并生成一份可读的小提琴练习谱。
          </p>

          <input
            ref={inputRef}
            type="file"
            accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/x-wav,audio/mp4"
            className="hidden"
            onChange={handleInput}
          />

          <label className="mt-6 flex w-full max-w-md flex-col gap-2 text-left text-sm text-ink/75">
            <span className="font-semibold text-ink">目标乐器</span>
            <select
              value={targetInstrument}
              onChange={(event) => setTargetInstrument(event.target.value as TargetInstrument)}
              className="h-11 border border-ink/15 bg-white px-3 text-ink outline-none transition focus:border-staff"
            >
              {TARGET_INSTRUMENT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="text-xs leading-5 text-ink/60">
              {TARGET_INSTRUMENT_OPTIONS.find((option) => option.value === targetInstrument)?.hint}
            </span>
          </label>

          <div className="mt-7 flex flex-col items-center gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex min-h-11 items-center gap-2 border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink shadow-soft transition hover:border-staff hover:text-staff"
            >
              <FileAudio className="h-4 w-4" aria-hidden="true" />
              选择音频文件
            </button>
            <button
              type="submit"
              disabled={submitting || !file}
              className="inline-flex min-h-11 items-center gap-2 bg-staff px-5 py-2 text-sm font-semibold text-white transition hover:bg-staff/90 disabled:cursor-not-allowed disabled:bg-ink/25"
            >
              <Music2 className="h-4 w-4" aria-hidden="true" />
              {submitting ? "正在上传音频..." : "上传并转写"}
            </button>
          </div>

          {file ? (
            <p className="mt-5 text-sm text-ink/75">
              已选择：<span className="font-semibold text-ink">{file.name}</span>
            </p>
          ) : null}

          {error ? (
            <div className="mt-5 flex max-w-xl items-start gap-2 border border-rosin/25 bg-rosin/10 px-4 py-3 text-left text-sm text-rosin">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          ) : null}
        </div>

        <div className="grid gap-3 text-sm text-ink/68 sm:grid-cols-3">
          <div className="border border-ink/10 bg-white/45 p-4">
            <p className="font-semibold text-ink">支持格式</p>
            <p className="mt-1">mp3, wav, m4a</p>
          </div>
          <div className="border border-ink/10 bg-white/45 p-4">
            <p className="font-semibold text-ink">最大文件大小</p>
            <p className="mt-1">{MAX_UPLOAD_MB} MB</p>
          </div>
          <div className="border border-ink/10 bg-white/45 p-4">
            <p className="font-semibold text-ink">建议时长</p>
            <p className="mt-1">MVP 测试建议使用 60 秒以内的短片段。</p>
          </div>
        </div>
      </form>

      <aside className="flex flex-col gap-5">
        <div className="border border-ink/10 bg-white/55 p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-staff">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            版权与限制
          </div>
          <p className="text-sm leading-6 text-ink/70">
            小提琴旋律谱只处理用户上传的音频，不连接流媒体平台，不绕过 DRM，也不授予转写受保护音乐的权限。生成前会按目标乐器做基础降噪和音域过滤。
          </p>
        </div>

        <div className="border border-ink/10 bg-white/55 p-5">
          <p className="text-sm font-semibold text-ink">适合上传的音频</p>
          <ul className="mt-3 space-y-2 text-sm text-ink/70">
            <li>清晰的小提琴旋律</li>
            <li>清晰的人声旋律</li>
            <li>单一乐器旋律</li>
            <li>哼唱或演唱录音</li>
            <li>主旋律明显的短音频片段</li>
          </ul>
        </div>

        <div className="border border-reed/45 bg-reed/14 p-5 text-sm leading-6 text-ink/75">
          AI 转写可能出错。导出前，你可以手动修正生成的音符。
        </div>
      </aside>
    </section>
  );
}
