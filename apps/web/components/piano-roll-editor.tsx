"use client";

import { useMemo, useRef, useState } from "react";
import { Mouse } from "lucide-react";
import type { EditableNote } from "@/lib/types";
import { midiToPitch } from "@/lib/music";

/**
 * Lightweight SVG-based piano-roll editor.
 *
 * Each note is drawn as a horizontal rectangle on a (pitch × time) grid.
 * You can:
 *   - Click + drag a note vertically to change its pitch (snaps to semitones)
 *   - Click + drag a note's right edge to extend its duration
 *   - Click + drag a note horizontally to shift its start time
 *   - Shift+click a note to delete it
 *
 * The audio is rebuilt by the parent via the regenerate flow.
 */

const MIDI_RANGE = { min: 36, max: 96 }; // C2 to C7 — covers all violin/vocal/piano comfortably
const ROW_HEIGHT = 12; // px per semitone
const PX_PER_SECOND = 80;

type DragMode = "move" | "resize" | "pitch";

export function PianoRollEditor({
  notes,
  tempo,
  onChange,
}: {
  notes: EditableNote[];
  tempo: number;
  onChange: (notes: EditableNote[]) => void;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [dragState, setDragState] = useState<{
    noteIndex: number;
    mode: DragMode;
    startX: number;
    startY: number;
    origStart: number;
    origDuration: number;
    origMidi: number;
  } | null>(null);

  const totalDuration = useMemo(
    () => Math.max(8, ...notes.map((n) => n.end_time)),
    [notes],
  );
  const width = totalDuration * PX_PER_SECOND;
  const semitones = MIDI_RANGE.max - MIDI_RANGE.min + 1;
  const height = semitones * ROW_HEIGHT;

  function midiToY(midi: number): number {
    return (MIDI_RANGE.max - midi) * ROW_HEIGHT;
  }
  function yToMidi(y: number): number {
    return Math.round(MIDI_RANGE.max - y / ROW_HEIGHT);
  }

  function handlePointerDown(
    event: React.PointerEvent<SVGRectElement>,
    note: EditableNote,
    mode: DragMode,
  ) {
    event.preventDefault();
    event.stopPropagation();
    if (event.shiftKey) {
      // Shift-click deletes
      onChange(
        notes.filter((n) => n.index !== note.index).map((n, i) => ({ ...n, index: i + 1 })),
      );
      return;
    }
    setDragState({
      noteIndex: note.index,
      mode,
      startX: event.clientX,
      startY: event.clientY,
      origStart: note.start_time,
      origDuration: note.duration_seconds,
      origMidi: note.midi_number,
    });
  }

  function handlePointerMove(event: React.PointerEvent<SVGElement>) {
    if (!dragState) return;
    const dx = event.clientX - dragState.startX;
    const dy = event.clientY - dragState.startY;
    const dtSeconds = dx / PX_PER_SECOND;
    const dMidi = -Math.round(dy / ROW_HEIGHT);

    onChange(
      notes.map((n) => {
        if (n.index !== dragState.noteIndex) return n;
        if (dragState.mode === "move") {
          const newStart = Math.max(0, dragState.origStart + dtSeconds);
          return {
            ...n,
            midi_number: Math.max(MIDI_RANGE.min, Math.min(MIDI_RANGE.max, dragState.origMidi + dMidi)),
            pitch: midiToPitch(
              Math.max(MIDI_RANGE.min, Math.min(MIDI_RANGE.max, dragState.origMidi + dMidi)),
            ),
            start_time: Number(newStart.toFixed(4)),
            end_time: Number((newStart + dragState.origDuration).toFixed(4)),
          };
        }
        if (dragState.mode === "resize") {
          const seconds_per_quarter = 60 / Math.max(tempo, 1);
          const newDur = Math.max(seconds_per_quarter * 0.0625, dragState.origDuration + dtSeconds);
          return {
            ...n,
            duration_seconds: Number(newDur.toFixed(4)),
            end_time: Number((n.start_time + newDur).toFixed(4)),
          };
        }
        return n;
      }),
    );
  }

  function handlePointerUp() {
    setDragState(null);
  }

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase text-staff">
        <Mouse className="h-4 w-4" aria-hidden="true" />
        Piano-roll 音符编辑器（拖拽即改）
      </div>
      <p className="mb-3 text-sm leading-6 text-ink/65">
        点击音符中部拖拽改音高/时刻；点右边缘拖拽改长度；按住 Shift 点击删除。改完点上面"重新生成乐谱"
        让 AI 把 PDF / MusicXML / MIDI 全部刷新。
      </p>
      <div ref={containerRef} className="overflow-auto bg-white" style={{ maxHeight: 400 }}>
        <svg
          width={width}
          height={height}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          onPointerLeave={handlePointerUp}
          style={{ touchAction: "none" }}
        >
          {/* Horizontal pitch-row striping — black keys darker */}
          {Array.from({ length: semitones }).map((_, i) => {
            const midi = MIDI_RANGE.max - i;
            const isBlackKey = [1, 3, 6, 8, 10].includes(midi % 12);
            return (
              <rect
                key={i}
                x={0}
                y={i * ROW_HEIGHT}
                width={width}
                height={ROW_HEIGHT}
                fill={isBlackKey ? "rgba(0,0,0,0.04)" : "transparent"}
              />
            );
          })}
          {/* Beat grid lines */}
          {Array.from({ length: Math.ceil(totalDuration) + 1 }).map((_, sec) => (
            <line
              key={sec}
              x1={sec * PX_PER_SECOND}
              y1={0}
              x2={sec * PX_PER_SECOND}
              y2={height}
              stroke="rgba(0,0,0,0.08)"
              strokeWidth={1}
            />
          ))}
          {/* Notes */}
          {notes.map((note) => {
            const x = note.start_time * PX_PER_SECOND;
            const w = Math.max(4, note.duration_seconds * PX_PER_SECOND);
            const y = midiToY(note.midi_number);
            return (
              <g key={note.index}>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={ROW_HEIGHT - 1}
                  fill="rgba(140,50,60,0.85)"
                  stroke="rgba(140,50,60,1)"
                  strokeWidth={1}
                  rx={2}
                  style={{ cursor: "grab" }}
                  onPointerDown={(e) => handlePointerDown(e, note, "move")}
                />
                <rect
                  x={x + w - 4}
                  y={y}
                  width={4}
                  height={ROW_HEIGHT - 1}
                  fill="rgba(255,255,255,0.4)"
                  style={{ cursor: "ew-resize" }}
                  onPointerDown={(e) => handlePointerDown(e, note, "resize")}
                />
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
