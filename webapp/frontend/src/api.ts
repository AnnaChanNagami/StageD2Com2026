// ============================================================
// api.ts — Client API typé pour Scribe (Qwen3-ASR)
// Routes alignées sur webapp/transcriptions/urls.py
// ============================================================

export interface JobSummary {
  id: string;
  original_name: string;
  status: "queued" | "running" | "completed" | "failed";
  language_detected: string | null;
  duration_sec: number | null;
  elapsed_sec: number | null;
  total_words: number;
  total_chars: number;
  progress: number;
  created_at: string;
  completed_at: string | null;
  error: string | null;
  device: string | null;
  segment_count: number;
  generated_tokens: number | null;
}

export interface Stats {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_duration: number;
  total_words: number;
  total_chars: number;
}

export interface Segment {
  index: number;
  start: number;
  end: number;
  text: string;
}

export interface JobStatusResponse {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  stage?: string | null;
  error?: string | null;
  url?: string;
}

export interface CreateJobResponse {
  id?: string;
  job_id?: string;
  error?: string;
  status?: string;
  url?: string;
}

// --- helpers -------------------------------------------------

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
  return match ? decodeURIComponent(match[2]) : null;
}

async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const csrf = getCookie("csrftoken");
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> ?? {}),
  };
  if (csrf && init?.method && init.method !== "GET") headers["X-CSRFToken"] = csrf;
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// --- endpoints -----------------------------------------------

/** POST multipart vers /jobs/create/ (création de job + upload audio) */
export async function createJob(formData: FormData, createUrl = "/jobs/create/"): Promise<CreateJobResponse> {
  const csrf = getCookie("csrftoken");
  const headers: Record<string, string> = {};
  if (csrf) headers["X-CSRFToken"] = csrf;
  const res = await fetch(createUrl, { method: "POST", headers, body: formData });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Création ${res.status}: ${text}`);
  }
  return res.json() as Promise<CreateJobResponse>;
}

/** Statut d'un job via /api/status/<id>/ */
export async function getStatus(id: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/api/status/${id}/`);
}

/** Liste paginée via /api/jobs/ */
export async function fetchJobs(page = 1, perPage = 20): Promise<{ items: JobSummary[]; total: number }> {
  return apiFetch<{ items: JobSummary[]; total: number }>(
    `/api/jobs/?page=${page}&per_page=${perPage}`
  );
}

/** Stats dashboard via /api/stats/ */
export async function fetchStats(): Promise<Stats> {
  return apiFetch<Stats>("/api/stats/");
}

/** Suppression via POST /jobs/<id>/delete-api/ */
export async function deleteJob(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/jobs/${id}/delete-api/`, { method: "POST" });
}