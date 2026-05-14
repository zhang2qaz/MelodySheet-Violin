import type {
  CreateJobResponse,
  JobResponse,
  NotesPayload,
  NumberedNotation,
  EditableNote,
  TargetInstrument,
} from "@/lib/types";

/**
 * Resolve the API base URL.
 *
 * We have two deployment modes and one dev mode:
 *
 *   1. Dev split: `npm run dev` (port 3000) + `uvicorn main:app` (port 8000).
 *      Different origins, so the web app needs an explicit cross-origin URL
 *      to reach the API. Resolved to "http://localhost:8000".
 *
 *   2. Installer (Windows .exe / macOS .app): the PyInstaller-frozen FastAPI
 *      serves BOTH the static Next.js export AND the JSON API from the same
 *      port (127.0.0.1:8765 typically). Same-origin, so we use
 *      `window.location.origin` for everything.
 *
 *   3. Reverse-proxy / hosted: explicit URL injected via env var.
 *
 * Decision flow:
 *   - env explicitly set to non-empty string  → use it (mode 3)
 *   - env explicitly set to ""                → same-origin (mode 2, the
 *                                               bash-friendly way to opt in)
 *   - env undefined AND production build      → same-origin (mode 2, because
 *                                               PowerShell `$env:VAR = ""`
 *                                               silently deletes the var on
 *                                               Windows — we cannot rely on
 *                                               "" surviving the build step)
 *   - env undefined AND development           → localhost:8000 (mode 1)
 *
 * The original `||` logic was broken because empty-string was falsy AND
 * because Windows PowerShell wouldn't reliably set it to "" anyway.
 */
const ENV_BASE: string | undefined = process.env.NEXT_PUBLIC_API_BASE_URL;
const TRIMMED_ENV: string | undefined =
  typeof ENV_BASE === "string" ? ENV_BASE.replace(/\/$/, "") : undefined;
const IS_PROD: boolean = process.env.NODE_ENV === "production";

export function apiBaseUrl(): string {
  // Mode 3: explicit cross-origin URL (e.g. behind a reverse proxy)
  if (typeof TRIMMED_ENV === "string" && TRIMMED_ENV !== "") {
    return TRIMMED_ENV;
  }
  // Modes 1+2: no explicit URL.
  // In a browser, same-origin works for the installer AND is harmless for
  // hosted deploys (where the JS would be served from the same domain anyway).
  // In dev (NODE_ENV=development), fall through to localhost:8000 because the
  // dev server runs on a different port than uvicorn.
  if (typeof window !== "undefined" && window.location) {
    if (IS_PROD || TRIMMED_ENV === "") {
      return window.location.origin;
    }
    return "http://localhost:8000";
  }
  // SSR/build-time: no window. Production exports relative URLs (handled by
  // caller adding "/api/..." to ""), dev falls back to localhost.
  if (IS_PROD || TRIMMED_ENV === "") return "";
  return "http://localhost:8000";
}

// Compatibility re-export: prefer apiBaseUrl() in new code. This is a
// build-time constant so it cannot do the window.location dance — call sites
// that need installer support must use apiBaseUrl().
export const API_BASE_URL =
  typeof TRIMMED_ENV === "string" && TRIMMED_ENV !== ""
    ? TRIMMED_ENV
    : IS_PROD
      ? ""
      : "http://localhost:8000";

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
