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
/** POST multipart vers /jobs/create/ (création de job + upload audio) */
export declare function createJob(formData: FormData, createUrl?: string): Promise<CreateJobResponse>;
/** Statut d'un job via /api/status/<id>/ */
export declare function getStatus(id: string): Promise<JobStatusResponse>;
/** Liste paginée via /api/jobs/ */
export declare function fetchJobs(page?: number, perPage?: number): Promise<{
    items: JobSummary[];
    total: number;
}>;
/** Stats dashboard via /api/stats/ */
export declare function fetchStats(): Promise<Stats>;
/** Suppression via POST /jobs/<id>/delete-api/ */
export declare function deleteJob(id: string): Promise<{
    ok: boolean;
}>;
