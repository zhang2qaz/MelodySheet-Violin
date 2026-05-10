"use client";

import { ChangeEvent, DragEvent, FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, FileAudio, Music2, ShieldCheck, UploadCloud } from "lucide-react";
import { createJob } from "@/lib/api";

const ACCEPTED_EXTENSIONS = ["mp3", "wav", "m4a"];
const MAX_UPLOAD_MB = Number(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB || 50);

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

  function validateFile(nextFile: File | null) {
    setError(null);
    if (!nextFile) {
      setFile(null);
      return;
    }

    const extension = extensionFor(nextFile);
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setFile(null);
      setError("Please choose an mp3, wav, or m4a audio file.");
      return;
    }

    if (nextFile.size === 0) {
      setFile(null);
      setError("The selected file is empty.");
      return;
    }

    if (nextFile.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFile(null);
      setError(`The selected file is larger than ${MAX_UPLOAD_MB} MB.`);
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
      setError("Choose an audio file before starting transcription.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await createJob(file);
      router.push(`/jobs/${created.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
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
          <h2 className="text-2xl font-semibold text-ink">Upload and Transcribe</h2>
          <p className="mt-3 max-w-xl text-base leading-7 text-ink/70">
            Upload an audio file you have the right to use. MelodySheet Violin will try to extract the main melody and generate a readable violin practice sheet.
          </p>

          <input
            ref={inputRef}
            type="file"
            accept=".mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/x-wav,audio/mp4"
            className="hidden"
            onChange={handleInput}
          />

          <div className="mt-7 flex flex-col items-center gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="inline-flex min-h-11 items-center gap-2 border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink shadow-soft transition hover:border-staff hover:text-staff"
            >
              <FileAudio className="h-4 w-4" aria-hidden="true" />
              Choose audio file
            </button>
            <button
              type="submit"
              disabled={submitting || !file}
              className="inline-flex min-h-11 items-center gap-2 bg-staff px-5 py-2 text-sm font-semibold text-white transition hover:bg-staff/90 disabled:cursor-not-allowed disabled:bg-ink/25"
            >
              <Music2 className="h-4 w-4" aria-hidden="true" />
              {submitting ? "Uploading audio..." : "Upload and Transcribe"}
            </button>
          </div>

          {file ? (
            <p className="mt-5 text-sm text-ink/75">
              Selected: <span className="font-semibold text-ink">{file.name}</span>
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
            <p className="font-semibold text-ink">Accepted formats</p>
            <p className="mt-1">mp3, wav, m4a</p>
          </div>
          <div className="border border-ink/10 bg-white/45 p-4">
            <p className="font-semibold text-ink">Max file size</p>
            <p className="mt-1">{MAX_UPLOAD_MB} MB</p>
          </div>
          <div className="border border-ink/10 bg-white/45 p-4">
            <p className="font-semibold text-ink">Recommended length</p>
            <p className="mt-1">For MVP testing, use short clips under 60 seconds.</p>
          </div>
        </div>
      </form>

      <aside className="flex flex-col gap-5">
        <div className="border border-ink/10 bg-white/55 p-5">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-staff">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            Rights and limits
          </div>
          <p className="text-sm leading-6 text-ink/70">
            MelodySheet Violin processes user-uploaded audio only. It does not connect to streaming platforms, bypass DRM, or grant permission to transcribe protected music.
          </p>
        </div>

        <div className="border border-ink/10 bg-white/55 p-5">
          <p className="text-sm font-semibold text-ink">Best input examples</p>
          <ul className="mt-3 space-y-2 text-sm text-ink/70">
            <li>Clear violin melody</li>
            <li>Clear vocal melody</li>
            <li>Single instrument melody</li>
            <li>Humming or singing recording</li>
            <li>Short song clip with obvious lead melody</li>
          </ul>
        </div>

        <div className="border border-reed/45 bg-reed/14 p-5 text-sm leading-6 text-ink/75">
          AI transcription may make mistakes. The generated notes are editable before export.
        </div>
      </aside>
    </section>
  );
}
