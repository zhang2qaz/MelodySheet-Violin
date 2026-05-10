import type { NumberedNotation, NumberedNote } from "@/lib/types";

const DURATION_BEATS: Record<string, number> = {
  whole: 4,
  half: 2,
  quarter: 1,
  eighth: 0.5,
  sixteenth: 0.25,
};

function formatDegree(note: NumberedNote): string {
  const octaveMarks = note.octave > 0 ? "'".repeat(note.octave) : note.octave < 0 ? ",".repeat(Math.abs(note.octave)) : "";
  return `${note.scale_degree}${octaveMarks}`;
}

function splitBars(notes: NumberedNote[]): NumberedNote[][] {
  const bars: NumberedNote[][] = [];
  let current: NumberedNote[] = [];
  let beats = 0;

  for (const note of notes) {
    current.push(note);
    beats += DURATION_BEATS[note.duration] || 1;
    if (beats >= 4) {
      bars.push(current);
      current = [];
      beats = 0;
    }
  }

  if (current.length) {
    bars.push(current);
  }
  return bars;
}

export function NumberedNotationView({ notation }: { notation: NumberedNotation | null }) {
  if (!notation) {
    return null;
  }

  const bars = splitBars(notation.notes);

  return (
    <section className="border border-ink/10 bg-white/65 p-5 shadow-soft">
      <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-sm font-semibold uppercase text-staff">简谱</p>
          <h2 className="text-2xl font-semibold text-ink">简化练习谱</h2>
        </div>
        <div className="text-sm text-ink/65">
          调号 {notation.key} · 拍号 {notation.meter} · 速度 {notation.tempo} BPM
        </div>
      </div>

      <div className="flex flex-wrap gap-y-3 text-lg leading-9 text-ink">
        {bars.map((bar, index) => (
          <div key={`${index}-${bar[0]?.index}`} className="flex items-center">
            <span className="mx-2 text-ink/35">|</span>
            <span className="flex flex-wrap gap-x-3">
              {bar.map((note) => (
                <span key={note.index} title={`${note.pitch_name} ${note.duration}`}>
                  {formatDegree(note)}
                </span>
              ))}
            </span>
          </div>
        ))}
        <span className="mx-2 text-ink/35">|</span>
      </div>
    </section>
  );
}
