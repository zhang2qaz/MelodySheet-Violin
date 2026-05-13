export type JobStatus =
  | "uploaded"
  | "converting"
  | "preprocessing"
  | "transcribing"
  | "postprocessing"
  | "completed"
  | "failed";

export type TargetInstrument = "violin" | "vocal" | "flute" | "piano" | "guitar" | "erhu";

export type DetectedInstrument = {
  instrument: string;
  confidence: number;
  source?: string | null;
  reason?: string | null;
};

export type TrackOutput = {
  musicxml: string | null;
  midi: string | null;
};

export type JobResult = {
  original_audio_url: string | null;
  midi_url: string | null;
  musicxml_url: string | null;
  numbered_json_url: string | null;
  notes_url: string | null;
  spectrogram_url: string | null;
  lily_url: string | null;
  abc_url: string | null;
  chords_url: string | null;
  chord_count?: number;
  tab_url: string | null;
  tab_txt_url: string | null;
  drums_url: string | null;
  drum_hit_count?: number;
  sections_url: string | null;
  section_count?: number;
  detected_key: string | null;
  estimated_tempo: number | null;
  estimated_meter: string | null;
  note_count: number | null;
  target_instrument: TargetInstrument | null;
  filtered_note_count: number;
  preprocessing_summary: string | null;
  transcription_method: string | null;
  detected_instruments: DetectedInstrument[];
  demucs_stems_used: string[];
  per_track_outputs: Record<string, TrackOutput>;
  violin_range_warning: boolean;
  violin_range_message: string | null;
};

export type JobResponse = {
  job_id: string;
  status: JobStatus;
  progress: number;
  error: string | null;
  result: JobResult | null;
};

export type CreateJobResponse = {
  job_id: string;
  status: JobStatus;
};

export type EditableNote = {
  index: number;
  start_time: number;
  end_time: number;
  pitch: string;
  midi_number: number;
  duration_seconds: number;
  duration_label: "whole" | "half" | "quarter" | "eighth" | "sixteenth";
  confidence: number;
};

export type NotesPayload = {
  notes: EditableNote[];
};

export type ChordEvent = {
  start_time: number;
  end_time: number;
  chord: string;
  root: string;
  quality: string;
  confidence: number;
};

export type ChordsPayload = {
  chords: ChordEvent[];
};

export type NumberedNote = {
  index: number;
  pitch_name: string;
  scale_degree: string;
  octave: number;
  duration: string;
  start_time: number;
  end_time: number;
  confidence: number;
};

export type NumberedNotation = {
  key: string;
  meter: string;
  tempo: number;
  notes: NumberedNote[];
};
