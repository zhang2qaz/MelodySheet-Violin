import { AlertTriangle, AudioLines, Gauge, KeyRound, Layers, ListMusic } from "lucide-react";
import type { EditableNote, JobResult } from "@/lib/types";
import { hasBelowViolinRange } from "@/lib/music";

const TARGET_INSTRUMENT_TEXT: Record<string, string> = {
  violin: "小提琴",
  vocal: "人声",
  flute: "长笛",
  piano: "钢琴",
  guitar: "吉他",
  erhu: "二胡",
  cello: "大提琴",
  bass: "贝斯",
  drums: "鼓",
  trumpet: "小号",
  saxophone: "萨克斯",
};

const TRANSCRIPTION_METHOD_LABEL: Record<string, string> = {
  "pyin-monophonic": "pYIN 单音音高跟踪 (librosa)",
  "basic-pitch-tuned": "Basic Pitch 复音转写（已调阈值）",
  "basic-pitch-legacy": "Basic Pitch 通用模型（兼容回退）",
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
        {result.transcription_method ? (
          <span className="mt-1 block">
            识别方式：{TRANSCRIPTION_METHOD_LABEL[result.transcription_method] || result.transcription_method}
          </span>
        ) : null}
        {result.estimated_meter ? (
          <span className="mt-1 block">估计拍号：{result.estimated_meter}</span>
        ) : null}
        {result.demucs_stems_used && result.demucs_stems_used.length > 0 ? (
          <span className="mt-1 block">已使用 Demucs 6 轨分离：{result.demucs_stems_used.join("、")}</span>
        ) : null}
        {result.filtered_note_count > 0 ? (
          <span className="mt-1 block">已过滤 {result.filtered_note_count} 个目标乐器音域外的音符。</span>
        ) : null}
      </div>

      {result.detected_instruments && result.detected_instruments.length > 0 ? (
        <div className="border border-ink/10 bg-white/55 p-4 md:col-span-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-staff">
            <AudioLines className="h-4 w-4" aria-hidden="true" />
            自动识别到的乐器
          </div>
          <ul className="mt-2 flex flex-wrap gap-2 text-sm text-ink/80">
            {result.detected_instruments.map((item) => (
              <li
                key={item.instrument}
                className="border border-ink/15 bg-white px-3 py-1"
                title={item.reason || undefined}
              >
                {TARGET_INSTRUMENT_TEXT[item.instrument] || item.instrument}
                <span className="ml-2 text-xs text-ink/55">{Math.round(item.confidence * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {result.per_track_outputs && Object.keys(result.per_track_outputs).length > 0 ? (
        <div className="border border-ink/10 bg-white/55 p-4 md:col-span-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-staff">
            <Layers className="h-4 w-4" aria-hidden="true" />
            分乐器单独导出
          </div>
          <ul className="mt-2 grid gap-2 text-sm text-ink/80 md:grid-cols-2">
            {Object.entries(result.per_track_outputs).map(([instrument, paths]) => (
              <li key={instrument} className="flex items-center justify-between border border-ink/10 px-3 py-2">
                <span>{TARGET_INSTRUMENT_TEXT[instrument] || instrument}</span>
                <span className="flex gap-3 text-xs">
                  {paths.musicxml ? (
                    <a className="text-staff underline" href={paths.musicxml}>
                      MusicXML
                    </a>
                  ) : null}
                  {paths.midi ? (
                    <a className="text-staff underline" href={paths.midi}>
                      MIDI
                    </a>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

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
