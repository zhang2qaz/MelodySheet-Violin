"use client";

import { useState } from "react";
import { ArrowDown, ArrowUp, RefreshCw, Trash2 } from "lucide-react";
import type { EditableNote } from "@/lib/types";
import {
  DURATION_LABELS,
  formatSeconds,
  pitchToMidi,
  transposeNotes,
  updateNoteDuration,
} from "@/lib/music";

const DURATION_LABEL_TEXT: Record<EditableNote["duration_label"], string> = {
  whole: "全音符",
  half: "二分音符",
  quarter: "四分音符",
  eighth: "八分音符",
  sixteenth: "十六分音符",
};

const KEY_OPTIONS = [
  "C major", "G major", "D major", "A major", "E major", "B major",
  "F# major", "F major", "Bb major", "Eb major", "Ab major", "Db major", "Gb major",
  "A minor", "E minor", "B minor", "F# minor", "C# minor", "G# minor", "D# minor",
  "D minor", "G minor", "C minor", "F minor", "Bb minor", "Eb minor",
];

const METER_OPTIONS = ["4/4", "3/4", "2/4", "6/8", "12/8", "5/4", "7/8"];

export type RegenerateOverrides = {
  tempo_bpm?: number | null;
  detected_key?: string | null;
  meter?: string | null;
};

type NoteEditorProps = {
  notes: EditableNote[];
  tempo: number;
  detectedKey?: string | null;
  meter?: string | null;
  regenerating: boolean;
  onChange: (notes: EditableNote[]) => void;
  onRegenerate: (overrides?: RegenerateOverrides) => void;
};

export function NoteEditor({
  notes,
  tempo,
  detectedKey,
  meter,
  regenerating,
  onChange,
  onRegenerate,
}: NoteEditorProps) {
  const [tempoOverride, setTempoOverride] = useState<string>("");
  const [keyOverride, setKeyOverride] = useState<string>("");
  const [meterOverride, setMeterOverride] = useState<string>("");

  function handleRegenerate() {
    const parsedTempo = tempoOverride.trim() ? parseInt(tempoOverride, 10) : null;
    onRegenerate({
      tempo_bpm: parsedTempo && parsedTempo >= 30 && parsedTempo <= 300 ? parsedTempo : null,
      detected_key: keyOverride.trim() || null,
      meter: meterOverride.trim() || null,
    });
  }
  function updatePitch(index: number, pitch: string) {
    const midi = pitchToMidi(pitch);
    onChange(
      notes.map((note) =>
        note.index === index
          ? {
              ...note,
              pitch,
              midi_number: midi ?? note.midi_number,
            }
          : note,
      ),
    );
  }

  function updateDuration(index: number, label: EditableNote["duration_label"]) {
    onChange(notes.map((note) => (note.index === index ? updateNoteDuration(note, label, tempo) : note)));
  }

  function deleteNote(index: number) {
    onChange(
      notes
        .filter((note) => note.index !== index)
        .map((note, position) => ({
          ...note,
          index: position + 1,
        })),
    );
  }

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-5 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">音符修正</p>
          <h2 className="text-2xl font-semibold text-ink">可编辑的识别音符</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onChange(transposeNotes(notes, -1))}
            className="inline-flex min-h-10 items-center gap-2 border border-ink/15 bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-staff hover:text-staff"
          >
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
            降低半音
          </button>
          <button
            type="button"
            onClick={() => onChange(transposeNotes(notes, 1))}
            className="inline-flex min-h-10 items-center gap-2 border border-ink/15 bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-staff hover:text-staff"
          >
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
            升高半音
          </button>
          <button
            type="button"
            onClick={handleRegenerate}
            disabled={regenerating || !notes.length}
            className="inline-flex min-h-10 items-center gap-2 bg-staff px-4 py-2 text-sm font-semibold text-white transition hover:bg-staff/90 disabled:cursor-not-allowed disabled:bg-ink/25"
          >
            <RefreshCw className={`h-4 w-4 ${regenerating ? "animate-spin" : ""}`} aria-hidden="true" />
            {regenerating ? "正在重新生成..." : "重新生成乐谱"}
          </button>
        </div>
      </div>

      {/* Manual override controls — tempo / key / meter. Empty means keep current. */}
      <div className="mb-5 grid grid-cols-1 gap-3 border border-ink/10 bg-white/55 p-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink/80">速度 (BPM)</span>
          <input
            type="number"
            min={30}
            max={300}
            value={tempoOverride}
            onChange={(event) => setTempoOverride(event.target.value)}
            placeholder={`当前 ${tempo}`}
            className="h-10 border border-ink/15 bg-white px-3 outline-none transition focus:border-staff"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink/80">调号</span>
          <select
            value={keyOverride}
            onChange={(event) => setKeyOverride(event.target.value)}
            className="h-10 border border-ink/15 bg-white px-3 outline-none transition focus:border-staff"
          >
            <option value="">保持当前 ({detectedKey || "C"})</option>
            {KEY_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-semibold text-ink/80">拍号</span>
          <select
            value={meterOverride}
            onChange={(event) => setMeterOverride(event.target.value)}
            className="h-10 border border-ink/15 bg-white px-3 outline-none transition focus:border-staff"
          >
            <option value="">保持当前 ({meter || "4/4"})</option>
            {METER_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-x-auto border border-ink/10">
        <table className="min-w-[920px] w-full border-collapse text-left text-sm">
          <thead className="bg-ink/5 text-xs uppercase text-ink/60">
            <tr>
              <th className="px-3 py-3">序号</th>
              <th className="px-3 py-3">开始时间</th>
              <th className="px-3 py-3">结束时间</th>
              <th className="px-3 py-3">音高</th>
              <th className="px-3 py-3">MIDI 编号</th>
              <th className="px-3 py-3">时值</th>
              <th className="px-3 py-3">置信度</th>
              <th className="px-3 py-3">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink/8 bg-white">
            {notes.map((note) => (
              <tr key={note.index}>
                <td className="px-3 py-2 font-medium text-ink">{note.index}</td>
                <td className="px-3 py-2 text-ink/70">{formatSeconds(note.start_time)}</td>
                <td className="px-3 py-2 text-ink/70">{formatSeconds(note.end_time)}</td>
                <td className="px-3 py-2">
                  <input
                    value={note.pitch}
                    onChange={(event) => updatePitch(note.index, event.target.value)}
                    className="h-9 w-24 border border-ink/15 px-2 text-ink outline-none transition focus:border-staff"
                  />
                </td>
                <td className="px-3 py-2 text-ink/70">{note.midi_number}</td>
                <td className="px-3 py-2">
                  <select
                    value={note.duration_label}
                    onChange={(event) =>
                      updateDuration(note.index, event.target.value as EditableNote["duration_label"])
                    }
                    className="h-9 border border-ink/15 bg-white px-2 text-ink outline-none transition focus:border-staff"
                  >
                    {DURATION_LABELS.map((label) => (
                      <option key={label} value={label}>
                        {DURATION_LABEL_TEXT[label]}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-3 py-2 text-ink/70">{Math.round(note.confidence * 100)}%</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    onClick={() => deleteNote(note.index)}
                    className="inline-flex h-9 w-9 items-center justify-center border border-ink/15 text-rosin transition hover:border-rosin"
                    aria-label={`删除第 ${note.index} 个音符`}
                    title={`删除第 ${note.index} 个音符`}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
