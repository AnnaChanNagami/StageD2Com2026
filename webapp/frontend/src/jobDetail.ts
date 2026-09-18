// ============================================================
// jobDetail.ts — Page détail d'un job : polling, graphiques,
// diff, sync player ↔ segments
// ============================================================

import { getStatus, type JobStatusResponse } from "./api.js";
import { computeStats, diffWords, diffChars, diffLines, escapeHtml, filterParts, type DiffMode, type DiffFilter } from "./diff.js";

declare const Chart: any;

type PageData = JobStatusResponse & {
  originalFull?: string;
  correctedFull?: string;
};

export function initJobDetail(): void {
  const jsonEl = document.getElementById("scribeJobData") as HTMLScriptElement | null;
  if (!jsonEl || !jsonEl.textContent) return;
  const pageData: PageData = JSON.parse(jsonEl.textContent);

  const jobId = pageData.id;

  // --- Polling si job en cours ---
  if (pageData.status === "running") {
    const bar = document.getElementById("progressBar") as HTMLElement | null;
    const poll = async (): Promise<void> => {
      try {
        const d = await getStatus(jobId);
        if (bar) bar.style.width = `${d.progress}%`;
        if (d.status === "completed" || d.status === "failed") {
          window.location.reload();
        } else {
          setTimeout(poll, 2000);
        }
      } catch {
        setTimeout(poll, 4000);
      }
    };
    void poll();
  }

  // --- Graphiques Chart.js (données injectées via data attributes) ---
  const ratioCanvas = document.getElementById("ratioChart") as HTMLCanvasElement | null;
  const ratioData = ratioCanvas?.dataset;
  if (ratioCanvas && ratioData && typeof Chart !== "undefined") {
    new Chart(ratioCanvas, {
      type: "doughnut",
      data: {
        labels: ["Durée audio", "Temps analyse"],
        datasets: [{
          data: [Number(ratioData.durationSec ?? 0), Number(ratioData.elapsedSec ?? 0)],
          backgroundColor: ["rgba(13, 202, 240, 0.7)", "rgba(255, 146, 43, 0.7)"],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "65%",
        plugins: {
          legend: { position: "bottom", labels: { color: "rgba(15,23,42,0.8)", padding: 10 } },
        },
      },
    });
  }

  const wcCanvas = document.getElementById("wcChart") as HTMLCanvasElement | null;
  const wcData = wcCanvas?.dataset;
  if (wcCanvas && wcData && typeof Chart !== "undefined") {
    new Chart(wcCanvas, {
      type: "bar",
      data: {
        labels: ["Mots", "Caractères"],
        datasets: [{
          data: [Number(wcData.totalWords ?? 0), Number(wcData.totalChars ?? 0)],
          backgroundColor: ["rgba(132, 94, 247, 0.7)", "rgba(240, 101, 149, 0.7)"],
          borderRadius: 6,
          barThickness: 50,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: "rgba(15,23,42,0.6)" }, grid: { display: false } },
          y: { ticks: { color: "rgba(15,23,42,0.6)" }, grid: { color: "rgba(15,23,42,0.08)" } },
        },
      },
    });
  }

  // --- Comparatif Scribe vs Correction ---
  // Les textes original/corrigé sont injectés dans le JSON pageData via job_json
  if (pageData.originalFull !== undefined && pageData.correctedFull !== undefined) {
    initDiff(pageData.originalFull, pageData.correctedFull);
  }

  // --- Sync player → segments ---
  const audio = document.querySelector("audio");
  const segs = document.querySelectorAll<HTMLElement>(".segment-item");
  if (audio && segs.length) {
    audio.addEventListener("timeupdate", () => {
      const t = audio.currentTime;
      segs.forEach((s) => {
        const start = parseFloat(s.dataset.start ?? "0");
        const end = parseFloat(s.dataset.end ?? "0");
        s.style.background = t >= start && t <= end ? "rgba(233, 69, 96, 0.12)" : "";
      });
    });
  }
}

// --- Diff UI ---

function initDiff(originalFull: string, correctedFull: string): void {
  let diffMode: DiffMode = "word";
  let diffFilter: DiffFilter = "all";

  const computeDiff = (): ReturnType<typeof diffWords> => {
    if (diffMode === "word") return diffWords(originalFull, correctedFull);
    if (diffMode === "char") return diffChars(originalFull, correctedFull);
    return diffLines(originalFull, correctedFull);
  };

  const renderParts = (parts: ReturnType<typeof diffWords>, mode: DiffMode): string => {
    let html = "";
    for (const p of parts) {
      if (mode === "line") {
        const lines = p.value.split("\n");
        lines.forEach((l, i) => {
          if (l !== "" || i > 0) {
            const cls = p.added ? "diff-line diff-add" : p.removed ? "diff-line diff-del" : "diff-line";
            html += `<div class="${cls}">${p.added ? "+" : p.removed ? "-" : ""}${escapeHtml(l || " ")}</div>`;
          }
        });
      } else {
        const cls = p.added ? "diff-add" : p.removed ? "diff-del" : "";
        html += `<span class="${cls}" title="${p.added ? "Ajouté" : p.removed ? "Supprimé" : ""}">${escapeHtml(p.value)}</span>`;
      }
    }
    return html;
  };

  const applyDiff = (): void => {
    const parts = computeDiff();
    const stats = computeStats(parts);
    const display = filterParts(parts, diffFilter);

    const out = document.getElementById("diffOutput");
    if (out) out.innerHTML = renderParts(display, diffMode);

    const statsEl = document.getElementById("diffStats");
    if (statsEl) {
      statsEl.innerHTML =
        `<i class="bi bi-arrow-up-right" style="color: #15803d;"></i> +${stats.charsAdded} car. &nbsp;` +
        `<i class="bi bi-arrow-down-left" style="color: #dc2626;"></i> −${stats.charsRemoved} car. &nbsp;` +
        `<i class="bi bi-columns-gap"></i> ${stats.charsAdded + stats.charsRemoved} car. modifiés`;
    }
  };

  const setDiffMode = (mode: DiffMode): void => {
    diffMode = mode;
    document.querySelectorAll("#btnDiffWord, #btnDiffChar, #btnDiffLine").forEach((b) => b.classList.remove("active"));
    const btn = document.getElementById("btnDiff" + mode.charAt(0).toUpperCase() + mode.slice(1));
    btn?.classList.add("active");
    applyDiff();
  };

  const setDiffFilter = (filter: DiffFilter): void => {
    diffFilter = filter;
    document.getElementById("btnShowAll")?.classList.toggle("active", filter === "all");
    document.getElementById("btnShowChanges")?.classList.toggle("active", filter === "changes");
    applyDiff();
  };

  (window as unknown as Record<string, unknown>).setDiffMode = setDiffMode;
  (window as unknown as Record<string, unknown>).setDiffFilter = setDiffFilter;

  applyDiff();
}