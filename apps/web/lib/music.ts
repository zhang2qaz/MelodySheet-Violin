import type { EditableNote } from "@/lib/types";

const PITCH_CLASS_TO_SEMITONE: Record<string, number> = {
  C: 0,
  "C#": 1,
  Db: 1,
  D: 2,
  "D#": 3,
  Eb: 3,
  E: 4,
  F: 5,
  "F#": 6,
  Gb: 6,
  G: 7,
  "G#": 8,
  Ab: 8,
  A: 9,
  "A#": 10,
  Bb: 10,
  B: 11,
};

const SEMITONE_TO_PITCH = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export const DURATION_LABELS: EditableNote["duration_label"][] = [
  "whole",
  "half",
  "quarter",
  "eighth",
  "sixteenth",
];

export const DURATION_TO_BEATS: Record<EditableNote["duration_label"], number> = {
  whole: 4,
  half: 2,
  quarter: 1,
  eighth: 0.5,
  sixteenth: 0.25,
};

export function pitchToMidi(pitch: string): number | null {
  const match = pitch.trim().match(/^([A-Ga-g])([#b]?)(-?\d)$/);
  if (!match) {
    return null;
  }
  const [, letter, accidental, octaveText] = match;
  const pitchClass = `${letter.toUpperCase()}${accidental}`;
  const semitone = PITCH_CLASS_TO_SEMITONE[pitchClass];
  if (semitone === undefined) {
    return null;
  }
  const octave = Number(octaveText);
  return (octave + 1) * 12 + semitone;
}

export function midiToPitch(midiNumber: number): string {
  const clamped = Math.max(0, Math.min(127, Math.round(midiNumber)));
  const octave = Math.floor(clamped / 12) - 1;
  const pitchClass = SEMITONE_TO_PITCH[clamped % 12];
  return `${pitchClass}${octave}`;
}

export function durationSeconds(label: EditableNote["duration_label"], tempo: number): number {
  return (DURATION_TO_BEATS[label] * 60) / Math.max(tempo, 1);
}

export function updateNoteDuration(
  note: EditableNote,
  label: EditableNote["duration_label"],
  tempo: number,
): EditableNote {
  const seconds = durationSeconds(label, tempo);
  return {
    ...note,
    duration_label: label,
    duration_seconds: Number(seconds.toFixed(4)),
    end_time: Number((note.start_time + seconds).toFixed(4)),
  };
}

export function transposeNotes(notes: EditableNote[], semitones: number): EditableNote[] {
  return notes.map((note) => {
    const nextMidi = Math.max(0, Math.min(127, note.midi_number + semitones));
    return {
      ...note,
      midi_number: nextMidi,
      pitch: midiToPitch(nextMidi),
    };
  });
}

export function hasBelowViolinRange(notes: EditableNote[]): boolean {
  return notes.some((note) => note.midi_number < 55);
}

export function formatSeconds(value: number): string {
  return value.toFixed(2);
}
