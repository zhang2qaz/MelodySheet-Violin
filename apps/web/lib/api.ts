import type {
  CreateJobResponse,
  JobResponse,
  NotesPayload,
  NumberedNotation,
  EditableNote,
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
        `Cannot reach the backend API at ${API_BASE_URL}. Make sure the backend is running and reload the page.`,
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
        : "Request failed. Please try again.";
    throw new Error(message);
  }
  return payload as T;
}

export async function createJob(file: File): Promise<CreateJobResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiFetch(`${API_BASE_URL}/api/jobs`, {
    method: "POST",
    body,
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

export async function regenerateJob(jobId: string, notes: EditableNote[]): Promise<JobResponse> {
  const response = await apiFetch(`${API_BASE_URL}/api/jobs/${jobId}/regenerate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ notes }),
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
