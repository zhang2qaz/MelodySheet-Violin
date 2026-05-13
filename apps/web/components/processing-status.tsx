import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import type { JobResponse, JobStatus } from "@/lib/types";

const STEPS: JobStatus[] = ["uploaded", "converting", "preprocessing", "transcribing", "postprocessing", "completed"];

const STATUS_MESSAGES: Record<JobStatus, string> = {
  uploaded: "正在上传音频...",
  converting: "正在转换音频格式...",
  preprocessing: "正在做基础降噪和目标乐器频段整理...",
  transcribing: "正在识别旋律...",
  postprocessing: "正在生成乐谱...",
  completed: "转写完成，下面是识别结果。",
  failed: "转写失败。请尝试更短、更清晰、背景伴奏更少的录音。",
};

const STATUS_HEADINGS: Record<JobStatus, string> = {
  uploaded: "正在生成你的旋律谱",
  converting: "正在生成你的旋律谱",
  preprocessing: "正在生成你的旋律谱",
  transcribing: "正在生成你的旋律谱",
  postprocessing: "正在生成你的旋律谱",
  completed: "你的旋律谱已经生成",
  failed: "旋律谱生成失败",
};

const STEP_LABELS: Record<JobStatus, string> = {
  uploaded: "已上传",
  converting: "格式转换",
  preprocessing: "降噪整理",
  transcribing: "旋律识别",
  postprocessing: "乐谱生成",
  completed: "已完成",
  failed: "失败",
};

export function ProcessingStatus({ job }: { job: JobResponse }) {
  const activeIndex = Math.max(0, STEPS.indexOf(job.status));
  const isFailed = job.status === "failed";

  return (
    <section className="border border-ink/10 bg-white/65 p-6 shadow-soft">
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">处理任务</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">{STATUS_HEADINGS[job.status]}</h1>
          <p className="mt-3 text-base text-ink/70">{job.error || STATUS_MESSAGES[job.status]}</p>
        </div>
        <div className="flex items-center gap-2 text-sm font-semibold text-ink/70">
          {isFailed ? (
            <AlertTriangle className="h-5 w-5 text-rosin" aria-hidden="true" />
          ) : job.status === "completed" ? (
            <CheckCircle2 className="h-5 w-5 text-staff" aria-hidden="true" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin text-staff" aria-hidden="true" />
          )}
          {job.progress}%
        </div>
      </div>

      <div className="mt-7 h-2 w-full overflow-hidden bg-ink/10">
        <div
          className={`h-full ${isFailed ? "bg-rosin" : "bg-staff"}`}
          style={{ width: `${Math.max(0, Math.min(job.progress, 100))}%` }}
        />
      </div>

      <div className="mt-6 grid gap-3 sm:grid-cols-5">
        {STEPS.map((step, index) => {
          const done = !isFailed && index <= activeIndex;
          return (
            <div key={step} className="flex items-center gap-2 text-sm">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  done ? "bg-staff" : isFailed && index === activeIndex ? "bg-rosin" : "bg-ink/18"
                }`}
              />
              <span className={done ? "font-semibold text-ink" : "text-ink/55"}>{STEP_LABELS[step]}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
