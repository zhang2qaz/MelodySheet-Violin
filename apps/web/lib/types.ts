export type JobStatus =
  | "uploaded"
  | "converting"
  | "preprocessing"
  | "transcribing"
  | "postprocessing"
  | "completed"
  | "failed";

export type TargetInstrument = "violin" | "vocal" | "flute" | "piano" | "guitar" | "erhu";

export type JobResult = {
  original_audio_url: string | null;
  midi_url: string | null;
  musicxml_url: string | null;
  numbered_json_url: string | null;
  notes_url: string | null;
  detected_key: string | null;
  estimated_tempo: number | null;
  note_count: number | null;
  target_instrument: TargetInstrument | null;
  filtered_note_count: number;
  preprocessing_summary: string | null;
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
