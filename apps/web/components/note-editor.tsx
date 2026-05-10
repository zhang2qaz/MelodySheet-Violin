"use client";

import { ArrowDown, ArrowUp, RefreshCw, Trash2 } from "lucide-react";
import type { EditableNote } from "@/lib/types";
import {
  DURATION_LABELS,
  formatSeconds,
  pitchToMidi,
  transposeNotes,
  updateNoteDuration,
} from "@/lib/music";

type NoteEditorProps = {
  notes: EditableNote[];
  tempo: number;
  regenerating: boolean;
  onChange: (notes: EditableNote[]) => void;
  onRegenerate: () => void;
};

export function NoteEditor({
  notes,
  tempo,
  regenerating,
  onChange,
  onRegenerate,
}: NoteEditorProps) {
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
          <p className="text-sm font-semibold uppercase text-staff">Note correction</p>
          <h2 className="text-2xl font-semibold text-ink">Editable detected notes</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => onChange(transposeNotes(notes, -1))}
            className="inline-flex min-h-10 items-center gap-2 border border-ink/15 bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-staff hover:text-staff"
          >
            <ArrowDown className="h-4 w-4" aria-hidden="true" />
            Down semitone
          </button>
          <button
            type="button"
            onClick={() => onChange(transposeNotes(notes, 1))}
            className="inline-flex min-h-10 items-center gap-2 border border-ink/15 bg-white px-3 py-2 text-sm font-semibold text-ink transition hover:border-staff hover:text-staff"
          >
            <ArrowUp className="h-4 w-4" aria-hidden="true" />
            Up semitone
          </button>
          <button
            type="button"
            onClick={onRegenerate}
            disabled={regenerating || !notes.length}
            className="inline-flex min-h-10 items-center gap-2 bg-staff px-4 py-2 text-sm font-semibold text-white transition hover:bg-staff/90 disabled:cursor-not-allowed disabled:bg-ink/25"
          >
            <RefreshCw className={`h-4 w-4 ${regenerating ? "animate-spin" : ""}`} aria-hidden="true" />
            {regenerating ? "Regenerating..." : "Regenerate Sheet"}
          </button>
        </div>
      </div>

      <div className="overflow-x-auto border border-ink/10">
        <table className="min-w-[920px] w-full border-collapse text-left text-sm">
          <thead className="bg-ink/5 text-xs uppercase text-ink/60">
            <tr>
              <th className="px-3 py-3">Index</th>
              <th className="px-3 py-3">Start time</th>
              <th className="px-3 py-3">End time</th>
              <th className="px-3 py-3">Pitch</th>
              <th className="px-3 py-3">MIDI number</th>
              <th className="px-3 py-3">Duration</th>
              <th className="px-3 py-3">Confidence</th>
              <th className="px-3 py-3">Actions</th>
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
                        {label}
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
                    aria-label={`Delete note ${note.index}`}
                    title={`Delete note ${note.index}`}
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
