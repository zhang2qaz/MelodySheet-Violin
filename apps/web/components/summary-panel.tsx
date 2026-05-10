import { AlertTriangle, Gauge, KeyRound, ListMusic } from "lucide-react";
import type { EditableNote, JobResult } from "@/lib/types";
import { hasBelowViolinRange } from "@/lib/music";

export function SummaryPanel({
  result,
  notes,
}: {
  result: JobResult;
  notes: EditableNote[];
}) {
  const localRangeWarning = hasBelowViolinRange(notes);
  const showRangeWarning = result.violin_range_warning || localRangeWarning;

  return (
    <section className="grid gap-3 md:grid-cols-3">
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <KeyRound className="h-4 w-4" aria-hidden="true" />
          Detected key
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{result.detected_key || "Unknown"}</p>
      </div>
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <Gauge className="h-4 w-4" aria-hidden="true" />
          Estimated tempo
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{result.estimated_tempo || 90} BPM</p>
      </div>
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <ListMusic className="h-4 w-4" aria-hidden="true" />
          Note count
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{notes.length || result.note_count || 0}</p>
      </div>

      <div className="border border-reed/45 bg-reed/14 p-4 text-sm leading-6 text-ink/78 md:col-span-3">
        AI transcription may not be perfect. Please review and correct notes before exporting.
      </div>

      {showRangeWarning ? (
        <div className="flex items-start gap-2 border border-rosin/25 bg-rosin/10 p-4 text-sm leading-6 text-rosin md:col-span-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            {result.violin_range_message ||
              "Some detected notes are below standard violin range. You may need to transpose or correct them."}
          </span>
        </div>
      ) : null}
    </section>
  );
}
