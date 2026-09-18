// ============================================================
// api.ts — Client API typé pour Scribe (Qwen3-ASR)
// Routes alignées sur webapp/transcriptions/urls.py
// ============================================================
// --- helpers -------------------------------------------------
function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
    return match ? decodeURIComponent(match[2]) : null;
}
async function apiFetch(url, init) {
    const csrf = getCookie("csrftoken");
    const headers = {
        ...(init?.headers ?? {}),
    };
    if (csrf && init?.method && init.method !== "GET")
        headers["X-CSRFToken"] = csrf;
    const res = await fetch(url, { ...init, headers });
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`API ${res.status}: ${text}`);
    }
    return res.json();
}
// --- endpoints -----------------------------------------------
/** POST multipart vers /jobs/create/ (création de job + upload audio) */
export async function createJob(formData, createUrl = "/jobs/create/") {
    const csrf = getCookie("csrftoken");
    const headers = {};
    if (csrf)
        headers["X-CSRFToken"] = csrf;
    const res = await fetch(createUrl, { method: "POST", headers, body: formData });
    if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`Création ${res.status}: ${text}`);
    }
    return res.json();
}
/** Statut d'un job via /api/status/<id>/ */
export async function getStatus(id) {
    return apiFetch(`/api/status/${id}/`);
}
/** Liste paginée via /api/jobs/ */
export async function fetchJobs(page = 1, perPage = 20) {
    return apiFetch(`/api/jobs/?page=${page}&per_page=${perPage}`);
}
/** Stats dashboard via /api/stats/ */
export async function fetchStats() {
    return apiFetch("/api/stats/");
}
/** Suppression via POST /jobs/<id>/delete-api/ */
export async function deleteJob(id) {
    return apiFetch(`/jobs/${id}/delete-api/`, { method: "POST" });
}
