"use client";

import { useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import type { EditableNote } from "@/lib/types";

export function PlaybackControls({ notes }: { notes: EditableNote[] }) {
  const [playing, setPlaying] = useState(false);
  const synthRef = useRef<{ dispose: () => void; releaseAll?: () => void } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function stop() {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (synthRef.current) {
      synthRef.current.releaseAll?.();
      synthRef.current.dispose();
      synthRef.current = null;
    }
    setPlaying(false);
  }

  async function play() {
    if (!notes.length) {
      return;
    }
    if (playing) {
      stop();
      return;
    }

    const Tone = await import("tone");
    await Tone.start();
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;
    const earliest = Math.min(...notes.map((note) => note.start_time));
    const now = Tone.now() + 0.08;

    for (const note of notes) {
      const start = Math.max(0, note.start_time - earliest);
      const duration = Math.max(0.08, note.duration_seconds);
      synth.triggerAttackRelease(note.pitch, duration, now + start);
    }

    const latestEnd = Math.max(...notes.map((note) => note.end_time - earliest));
    setPlaying(true);
    timerRef.current = setTimeout(stop, (latestEnd + 0.4) * 1000);
  }

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">Playback</p>
          <h2 className="text-2xl font-semibold text-ink">Generated melody</h2>
        </div>
        <button
          type="button"
          onClick={play}
          disabled={!notes.length}
          className="inline-flex min-h-11 items-center justify-center gap-2 bg-staff px-5 py-2 text-sm font-semibold text-white transition hover:bg-staff/90 disabled:cursor-not-allowed disabled:bg-ink/25"
        >
          {playing ? (
            <Pause className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Play className="h-4 w-4" aria-hidden="true" />
          )}
          {playing ? "Stop playback" : "Play melody"}
        </button>
      </div>
    </section>
  );
}
