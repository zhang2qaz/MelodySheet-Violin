import { AlertTriangle, Gauge, KeyRound, ListMusic } from "lucide-react";
import type { EditableNote, JobResult } from "@/lib/types";
import { hasBelowViolinRange } from "@/lib/music";

const TARGET_INSTRUMENT_TEXT: Record<string, string> = {
  violin: "小提琴",
  vocal: "人声",
  flute: "长笛",
  piano: "钢琴",
  guitar: "吉他",
  erhu: "二胡",
};

export function SummaryPanel({
  result,
  notes,
}: {
  result: JobResult;
  notes: EditableNote[];
}) {
  const isViolinTarget = (result.target_instrument || "violin") === "violin";
  const localRangeWarning = isViolinTarget && hasBelowViolinRange(notes);
  const showRangeWarning = isViolinTarget && (result.violin_range_warning || localRangeWarning);

  return (
    <section className="grid gap-3 md:grid-cols-4">
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <ListMusic className="h-4 w-4" aria-hidden="true" />
          目标乐器
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">
          {TARGET_INSTRUMENT_TEXT[result.target_instrument || ""] || "小提琴"}
        </p>
      </div>
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <KeyRound className="h-4 w-4" aria-hidden="true" />
          识别调号
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{result.detected_key || "未知"}</p>
      </div>
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <Gauge className="h-4 w-4" aria-hidden="true" />
          估计速度
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{result.estimated_tempo || 90} BPM</p>
      </div>
      <div className="border border-ink/10 bg-white/55 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-staff">
          <ListMusic className="h-4 w-4" aria-hidden="true" />
          音符数量
        </div>
        <p className="mt-2 text-2xl font-semibold text-ink">{notes.length || result.note_count || 0}</p>
      </div>

      <div className="border border-reed/45 bg-reed/14 p-4 text-sm leading-6 text-ink/78 md:col-span-4">
        AI 转写可能不完美。请在导出前检查并修正音符。
        {result.preprocessing_summary ? (
          <span className="mt-1 block">{result.preprocessing_summary}</span>
        ) : null}
        {result.filtered_note_count > 0 ? (
          <span className="mt-1 block">已过滤 {result.filtered_note_count} 个目标乐器音域外的音符。</span>
        ) : null}
      </div>

      {showRangeWarning ? (
        <div className="flex items-start gap-2 border border-rosin/25 bg-rosin/10 p-4 text-sm leading-6 text-rosin md:col-span-4">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>
            {result.violin_range_message ||
              "检测到部分音符低于标准小提琴音域。你可能需要移调或手动修正。"}
          </span>
        </div>
      ) : null}
    </section>
  );
}
