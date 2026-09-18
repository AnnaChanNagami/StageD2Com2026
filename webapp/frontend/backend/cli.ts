// ============================================================
// cli.ts — Utilitaire backend TypeScript pour Scribe.
// Dialogue avec l'API Django (jobs, stats, statut, segments).
// Usage: npx tsx backend/cli.ts <commande> [options]
// ============================================================

const BASE_URL = process.env.SCRIBE_API_URL ?? "http://127.0.0.1:8002";

interface JobSummary {
  id: string;
  original_name: string;
  status: string;
  progress: number;
  total_words: number;
  total_chars: number;
  error: string | null;
  created_at: string | null;
  language_detected: string | null;
}

interface JobListResponse {
  count: number;
  total: number;
  results: JobSummary[];
}

interface Stats {
  total: number;
  completed: number;
  failed: number;
  running: number;
  total_audio_sec: number;
  total_process_sec: number;
  total_words: number;
  total_size_bytes: number;
}

interface Segment {
  start: number;
  end: number;
  text: string;
}

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    throw new Error(`API ${res.status} sur ${path} : ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

// --- Commandes -------------------------------------------------

async function cmdStats(): Promise<void> {
  const s = await request<Stats>("/api/stats/");
  console.log("=== Statistiques Scribe ===");
  console.log(`Jobs totaux       : ${s.total}`);
  console.log(`Terminés          : ${s.completed}`);
  console.log(`Échecs            : ${s.failed}`);
  console.log(`En cours / en attente : ${s.running}`);
  console.log(`Durée audio (s)   : ${s.total_audio_sec.toFixed(1)}`);
  console.log(`Temps d'analyse (s): ${s.total_process_sec.toFixed(1)}`);
  console.log(`Mots transcrits   : ${s.total_words}`);
  console.log(`Volume audio      : ${(s.total_size_bytes / 1024 / 1024).toFixed(1)} Mo`);
}

async function cmdJobs(limit = 10): Promise<void> {
  const data = await request<JobListResponse>(`/api/jobs/?limit=${limit}`);
  console.log(`=== ${data.results.length} derniers jobs (${data.total} au total) ===`);
  for (const j of data.results) {
    const lang = j.language_detected ?? "auto";
    console.log(
      `[${j.status.padEnd(9)}] ${j.id.slice(0, 8)}  ${j.original_name.padEnd(40)}  ` +
        `${j.total_words} mots  ${lang}`,
    );
  }
}

async function cmdStatus(id: string): Promise<void> {
  const j = await request<JobSummary>(`/api/status/${id}/`);
  console.log(`Job ${j.id}`);
  console.log(`  Fichier     : ${j.original_name}`);
  console.log(`  Statut      : ${j.status} (${j.progress}%)`);
  console.log(`  Mots        : ${j.total_words}`);
  console.log(`  Caractères  : ${j.total_chars}`);
  if (j.error) console.log(`  Erreur      : ${j.error}`);
}

async function cmdSegments(id: string): Promise<void> {
  const segs = await request<Segment[]>(`/api/segments/${id}/`);
  console.log(`=== ${segs.length} segments ===`);
  for (const s of segs) {
    console.log(`${Number(s.start).toFixed(2)}s → ${Number(s.end).toFixed(2)}s : ${s.text}`);
  }
}

// --- Dispatch ---------------------------------------------------

const [cmd, ...args] = process.argv.slice(2);

(async () => {
  try {
    switch (cmd) {
      case "stats":
        await cmdStats();
        break;
      case "jobs":
        await cmdJobs(args[0] ? Number(args[0]) : 10);
        break;
      case "status":
        if (!args[0]) throw new Error("Usage: cli.ts status <jobId>");
        await cmdStatus(args[0]);
        break;
      case "segments":
        if (!args[0]) throw new Error("Usage: cli.ts segments <jobId>");
        await cmdSegments(args[0]);
        break;
      default:
        console.log(
          "Usage: npx tsx backend/cli.ts <commande> [args]\n" +
            "  stats            — statistiques globales\n" +
            "  jobs [n]         — n derniers jobs (défaut 10)\n" +
            "  status <id>      — statut d'un job\n" +
            "  segments <id>    — segments d'un job",
        );
    }
  } catch (err) {
    console.error("Erreur:", err instanceof Error ? err.message : err);
    process.exit(1);
  }
})();