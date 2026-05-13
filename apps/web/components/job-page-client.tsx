"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, AlertCircle } from "lucide-react";
import { apiUrl, fetchNotes, fetchNumberedNotation, getJob, regenerateJob } from "@/lib/api";
import type { EditableNote, JobResponse, NumberedNotation } from "@/lib/types";
import { DownloadButtons } from "@/components/download-buttons";
import { MusicXmlViewer } from "@/components/musicxml-viewer";
import { SpectrogramView } from "@/components/spectrogram-view";
import { NoteEditor } from "@/components/note-editor";
import { NumberedNotationView } from "@/components/numbered-notation-view";
import { PlaybackControls } from "@/components/playback-controls";
import { ProcessingStatus } from "@/components/processing-status";
import { SummaryPanel } from "@/components/summary-panel";

export function JobPageClient({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobResponse | null>(null);
  const [notes, setNotes] = useState<EditableNote[]>([]);
  const [numberedNotation, setNumberedNotation] = useState<NumberedNotation | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);

  const loadResultFiles = useCallback(async (nextJob: JobResponse) => {
    if (nextJob.status !== "completed" || !nextJob.result) {
      return;
    }

    const [notesPayload, numberedPayload] = await Promise.all([
      nextJob.result.notes_url ? fetchNotes(nextJob.result.notes_url) : Promise.resolve({ notes: [] }),
      nextJob.result.numbered_json_url
        ? fetchNumberedNotation(nextJob.result.numbered_json_url)
        : Promise.resolve(null),
    ]);
    setNotes(notesPayload.notes);
    setNumberedNotation(numberedPayload);
  }, []);

  const loadJob = useCallback(async () => {
    const nextJob = await getJob(jobId);
    setJob(nextJob);
    if (nextJob.status === "completed") {
      await loadResultFiles(nextJob);
    }
    return nextJob;
  }, [jobId, loadResultFiles]);

  useEffect(() => {
    let cancelled = false;
    let interval: ReturnType<typeof setInterval> | null = null;

    async function tick() {
      try {
        const nextJob = await getJob(jobId);
        if (cancelled) {
          return;
        }
        setJob(nextJob);
        if (nextJob.status === "completed") {
          await loadResultFiles(nextJob);
        }
        if (nextJob.status === "completed" || nextJob.status === "failed") {
          if (interval) {
            clearInterval(interval);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setLoadingError(err instanceof Error ? err.message : "无法加载这个任务。");
        }
      }
    }

    tick();
    interval = setInterval(tick, 2000);

    return () => {
      cancelled = true;
      if (interval) {
        clearInterval(interval);
      }
    };
  }, [jobId, loadResultFiles]);

  async function handleRegenerate(overrides?: {
    tempo_bpm?: number | null;
    detected_key?: string | null;
    meter?: string | null;
  }) {
    setRegenerating(true);
    setLoadingError(null);
    try {
      const updated = await regenerateJob(jobId, notes, overrides);
      setJob(updated);
      await loadResultFiles(updated);
    } catch (err) {
      setLoadingError(err instanceof Error ? err.message : "重新生成失败。");
      await loadJob().catch(() => undefined);
    } finally {
      setRegenerating(false);
    }
  }

  const result = job?.result || null;
  const tempo = result?.estimated_tempo || numberedNotation?.tempo || 90;

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-5 py-8 sm:px-8 lg:px-10">
      <header className="flex flex-col gap-4 border-b border-ink/10 pb-6 md:flex-row md:items-center md:justify-between">
        <div>
          <Link href="/" className="mb-3 inline-flex items-center gap-2 text-sm font-semibold text-staff">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            重新上传
          </Link>
          <h1 className="text-3xl font-semibold text-ink">小提琴旋律谱</h1>
          <p className="mt-2 text-sm text-ink/65">任务 {jobId}</p>
        </div>
      </header>

      {loadingError ? (
        <div className="flex items-start gap-2 border border-rosin/25 bg-rosin/10 p-4 text-sm text-rosin">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{loadingError}</span>
        </div>
      ) : null}

      {!job ? (
        <section className="border border-ink/10 bg-white/65 p-6 shadow-soft">
          <p className="text-ink/70">正在加载任务状态...</p>
        </section>
      ) : (
        <ProcessingStatus job={job} />
      )}

      {job?.status === "failed" ? (
        <section className="border border-rosin/25 bg-rosin/10 p-5 text-sm leading-6 text-rosin">
          转写失败。请尝试更短、更清晰、背景伴奏更少的录音。
        </section>
      ) : null}

      {job?.status === "completed" && result ? (
        <div className="flex flex-col gap-6">
          <SummaryPanel result={result} notes={notes} />

          <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
            <div className="mb-4">
              <p className="text-sm font-semibold uppercase text-staff">原始音频</p>
              <h2 className="text-2xl font-semibold text-ink">已上传的录音</h2>
            </div>
            {result.original_audio_url ? (
              <audio className="w-full" controls src={apiUrl(result.original_audio_url)} />
            ) : (
              <p className="text-sm text-ink/65">原始音频暂不可用。</p>
            )}
          </section>

          <MusicXmlViewer musicXmlUrl={result.musicxml_url} />
          <SpectrogramView spectrogramUrl={result.spectrogram_url} />
          <NumberedNotationView notation={numberedNotation} />
          <PlaybackControls notes={notes} />
          <DownloadButtons result={result} />
          <NoteEditor
            notes={notes}
            tempo={tempo}
            detectedKey={result?.detected_key ?? null}
            meter={result?.estimated_meter ?? null}
            regenerating={regenerating}
            onChange={setNotes}
            onRegenerate={handleRegenerate}
          />
        </div>
      ) : null}
    </main>
  );
}
