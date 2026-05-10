import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import type { JobResponse, JobStatus } from "@/lib/types";

const STEPS: JobStatus[] = ["uploaded", "converting", "transcribing", "postprocessing", "completed"];

const STATUS_MESSAGES: Record<JobStatus, string> = {
  uploaded: "Uploading audio...",
  converting: "Converting audio format...",
  transcribing: "Detecting melody...",
  postprocessing: "Building sheet music...",
  completed: "Preparing downloads...",
  failed: "Transcription failed. Try a shorter, clearer recording with less background accompaniment.",
};

export function ProcessingStatus({ job }: { job: JobResponse }) {
  const activeIndex = Math.max(0, STEPS.indexOf(job.status));
  const isFailed = job.status === "failed";

  return (
    <section className="border border-ink/10 bg-white/65 p-6 shadow-soft">
      <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">Processing job</p>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Building your melody sheet</h1>
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
              <span className={done ? "font-semibold text-ink" : "text-ink/55"}>{step}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
