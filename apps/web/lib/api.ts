import type {
  CreateJobResponse,
  JobResponse,
  NotesPayload,
  NumberedNotation,
  EditableNote,
  TargetInstrument,
} from "@/lib/types";

/**
 * Resolve the API base URL with three modes:
 *
 *   undefined env var → "http://localhost:8000" (dev default, when the web
 *                       app is running separately from the api)
 *   empty string ""   → use current page origin (the installer bundle
 *                       serves frontend + api from the same FastAPI port,
 *                       so we want same-origin relative URLs)
 *   any other value   → use that explicit URL (e.g. behind a reverse proxy)
 *
 * The old logic used `||` which treated "" as falsy and clobbered the
 * "same-origin" intent of the installer build, causing the installed exe
 * to point at http://localhost:8000 (where nothing was listening).
 */
const ENV_BASE: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL;
const TRIMMED_ENV: string | undefined =
  typeof ENV_BASE === "string" ? ENV_BASE.replace(/\/$/, "") : undefined;

export function apiBaseUrl(): string {
  if (TRIMMED_ENV === undefined) return "http://localhost:8000";
  if (TRIMMED_ENV === "") {
    if (typeof window !== "undefined" && window.location) {
      return window.location.origin;
    }
    return "";
  }
  return TRIMMED_ENV;
}

// Compatibility re-export: prefer apiBaseUrl() in new code.
export const API_BASE_URL = TRIMMED_ENV ?? "http://localhost:8000";

export function apiUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = apiBaseUrl();
  const tail = path.startsWith("/") ? path : `/${path}`;
  return `${base}${tail}`;
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof TypeError) {
      const base = apiBaseUrl() || "(同源)";
      throw new Error(
        `无法连接后端 API（${base}）。请确认后端服务正在运行，然后刷新页面。`,
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
  const response = await apiFetch(`${apiBaseUrl()}/api/jobs`, {
    method: "POST",
    body,
  });
  return parseJsonOrThrow<CreateJobResponse>(response);
}

export async function createJobFromUrl(
  url: string,
  targetInstrument: TargetInstrument = "violin",
): Promise<CreateJobResponse> {
  const response = await apiFetch(`${apiBaseUrl()}/api/jobs/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, target_instrument: targetInstrument }),
  });
  return parseJsonOrThrow<CreateJobResponse>(response);
}

export async function getJob(jobId: string): Promise<JobResponse> {
  const response = await apiFetch(`${apiBaseUrl()}/api/jobs/${jobId}`, {
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
  const response = await apiFetch(`${apiBaseUrl()}/api/jobs/${jobId}/regenerate`, {
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
