import type {
  CreateJobResponse,
  JobResponse,
  NotesPayload,
  NumberedNotation,
  EditableNote,
  TargetInstrument,
} from "@/lib/types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "http://localhost:8000";

export function apiUrl(path: string | null | undefined): string {
  if (!path) {
    return "";
  }
  if (path.startsWith("http://") || path.startsWith("https://")) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `无法连接后端 API（${API_BASE_URL}）。请确认后端服务正在运行，然后刷新页面。`,
      );
    }
    throw error;
  }
}

async function parseJsonOrThrow<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message =
      payload && typeof payload.detail === "string"
        ? payload.detail
        : "请求失败，请重试。";
    throw new Error(message);
  }
  return payload as T;
}

export async function createJob(
  file: File,
  targetInstrument: TargetInstrument = "violin",
): Promise<CreateJobResponse> {
  const body = new FormData();
  body.append("file", file);
  body.append("target_instrument", targetInstrument);
  const response = await apiFetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    body,
  });
  return parseJsonOrThrow<CreateJobResponse>(response);
}

export async function createJobFromUrl(
  url: string,
  targetInstrument: TargetInstrument = "violin",
): Promise<CreateJobResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/jobs/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, target_instrument: targetInstrument }),
  });
  return parseJsonOrThrow<CreateJobResponse>(response);
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}`, {
    cache: "no-store",
  });
  return parseJsonOrThrow<JobResponse>(response);
}

export async function fetchNotes(url: string): Promise<NotesPayload> {
  const response = await apiFetch(apiUrl(url), { cache: "no-store" });
  return parseJsonOrThrow<NotesPayload>(response);
}

export async function fetchNumberedNotation(url: string): Promise<NumberedNotation> {
  const response = await apiFetch(apiUrl(url), { cache: "no-store" });
  return parseJsonOrThrow<NumberedNotation>(response);
}

export async function regenerateJob(
  jobId: string,
  notes: EditableNote[],
  overrides?: { tempo_bpm?: number | null; detected_key?: string | null; meter?: string | null },
): Promise<JobResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}/regenerate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      notes,
      ...(overrides?.tempo_bpm != null ? { tempo_bpm: overrides.tempo_bpm } : {}),
      ...(overrides?.detected_key ? { detected_key: overrides.detected_key } : {}),
      ...(overrides?.meter ? { meter: overrides.meter } : {}),
    }),
  });
  const payload = await parseJsonOrThrow<{
    job_id: string;
    status: JobResponse["status"];
    result: JobResponse["result"];
  }>(response);
  return {
    job_id: payload.job_id,
    status: payload.status,
    progress: 100,
    error: null,
    result: payload.result,
  };
}
