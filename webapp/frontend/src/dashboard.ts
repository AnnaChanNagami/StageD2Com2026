// ============================================================
// dashboard.ts — Page dashboard : graphiques Chart.js
// Données injectées via <script type="application/json" id="dashboardData">
// ============================================================

declare const Chart: any;

interface DashboardData {
  series: { label: string; count: number; audio_min: number }[];
  languages: { lang: string; count: number }[];
  jobs: { name: string; audio_sec: number; process_sec: number; words: number; chars: number }[];
  corrections: { name: string; error_pct: number; orig_chars: number; corr_chars: number }[];
  errorCategories: { category: string; count: number }[];
  errorDays: { label: string; categories?: Record<string, number> }[];
  errorDetails: { name: string; category: string; created_at: string; error_msg: string }[];
}

const AXIS_DARK = "rgba(15,23,42,0.6)";
const GRID_DARK = "rgba(15,23,42,0.08)";
const LEGEND_DARK = "rgba(15,23,42,0.8)";
const ERROR_COLORS = ["#ff6b6b", "#ff922b", "#ffd43b", "#51cf66", "#22b8cf", "#845ef7", "#f06595", "#20c997", "#e94560", "#66d9e8"];

function baseScaleOptions(): Record<string, unknown> {
  return {
    x: { ticks: { color: AXIS_DARK }, grid: { color: GRID_DARK } },
    y: { ticks: { color: AXIS_DARK }, grid: { color: GRID_DARK } },
  };
}

function legendOptions(position = "top"): Record<string, unknown> {
  return { legend: { position, labels: { color: LEGEND_DARK } } };
}

function canvasOr(parentId: string): HTMLElement | null {
  const el = document.getElementById(parentId);
  return el?.parentElement ?? null;
}

function emptyState(parentId: string, icon: string, message: string): void {
  const parent = canvasOr(parentId);
  if (parent) {
    parent.innerHTML = `<div class="text-center text-muted py-5"><i class="bi ${icon}" style="font-size:2rem;"></i><br><br>${message}</div>`;
  }
}

export function initDashboard(): void {
  const jsonEl = document.getElementById("dashboardData") as HTMLScriptElement | null;
  if (!jsonEl?.textContent) return;
  const d: DashboardData = JSON.parse(jsonEl.textContent);
  if (!d) return;

  // Activité 7 jours (barres groupées)
  const activity = document.getElementById("activityChart") as HTMLCanvasElement | null;
  if (activity) {
    new Chart(activity, {
      type: "bar",
      data: {
        labels: d.series.map((s) => s.label),
        datasets: [
          { label: "Transcriptions", data: d.series.map((s) => s.count), backgroundColor: "rgba(233, 69, 96, 0.7)", borderRadius: 4 },
          { label: "Min audio", data: d.series.map((s) => s.audio_min), backgroundColor: "rgba(13, 202, 240, 0.5)", borderRadius: 4 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, scales: baseScaleOptions(), plugins: legendOptions() },
    });
  }

  // Langues (donut)
  const lang = document.getElementById("langChart") as HTMLCanvasElement | null;
  if (lang) {
    new Chart(lang, {
      type: "doughnut",
      data: {
        labels: d.languages.map((l) => l.lang),
        datasets: [{ data: d.languages.map((l) => l.count), backgroundColor: ["#e94560", "#22b8cf", "#51cf66", "#ffd43b", "#845ef7", "#ff922b", "#20c997", "#f06595"] }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom", labels: { color: LEGEND_DARK, padding: 12 } } } },
    });
  }

  // Temps analyse vs durée audio (barres horizontales)
  const timeCompare = document.getElementById("timeCompareChart") as HTMLCanvasElement | null;
  if (timeCompare) {
    new Chart(timeCompare, {
      type: "bar",
      data: {
        labels: d.jobs.map((j) => j.name),
        datasets: [
          { label: "Durée audio (s)", data: d.jobs.map((j) => j.audio_sec), backgroundColor: "rgba(13, 202, 240, 0.7)", borderRadius: 4 },
          { label: "Temps d'analyse (s)", data: d.jobs.map((j) => j.process_sec), backgroundColor: "rgba(255, 146, 43, 0.7)", borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        scales: { x: { ticks: { color: AXIS_DARK }, grid: { color: GRID_DARK } }, y: { ticks: { color: AXIS_DARK, font: { size: 10 } }, grid: { color: GRID_DARK } } },
        plugins: legendOptions(),
      },
    });
  }

  // Mots & caractères par job (barres horizontales)
  const wordsChars = document.getElementById("wordsCharsChart") as HTMLCanvasElement | null;
  if (wordsChars) {
    new Chart(wordsChars, {
      type: "bar",
      data: {
        labels: d.jobs.map((j) => j.name),
        datasets: [
          { label: "Mots", data: d.jobs.map((j) => j.words), backgroundColor: "rgba(132, 94, 247, 0.7)", borderRadius: 4 },
          { label: "Caractères", data: d.jobs.map((j) => j.chars), backgroundColor: "rgba(240, 101, 149, 0.5)", borderRadius: 4 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: "y",
        scales: { x: { ticks: { color: AXIS_DARK }, grid: { color: GRID_DARK } }, y: { ticks: { color: AXIS_DARK, font: { size: 10 } }, grid: { color: GRID_DARK } } },
        plugins: legendOptions(),
      },
    });
  }

  // Taux d'erreur par correction
  const corrChart = document.getElementById("correctionChart") as HTMLCanvasElement | null;
  if (corrChart) {
    if (d.corrections.length > 0) {
      new Chart(corrChart, {
        type: "bar",
        data: {
          labels: d.corrections.map((c) => c.name),
          datasets: [{
            label: "Taux d'erreur (%)",
            data: d.corrections.map((c) => c.error_pct),
            backgroundColor: d.corrections.map((c) => (c.error_pct < 5 ? "rgba(81, 207, 102, 0.7)" : c.error_pct < 15 ? "rgba(255, 212, 59, 0.7)" : "rgba(255, 107, 107, 0.7)")),
            borderRadius: 4,
          }],
        },
        options: { responsive: true, maintainAspectRatio: false, scales: baseScaleOptions(), plugins: legendOptions() },
      });
    } else {
      emptyState("correctionChart", "bi-pencil-square", "Aucune correction pour le moment");
    }
  }

  // Original vs corrigé (barres groupées)
  const corrCompare = document.getElementById("corrCompareChart") as HTMLCanvasElement | null;
  if (corrCompare) {
    if (d.corrections.length > 0) {
      new Chart(corrCompare, {
        type: "bar",
        data: {
          labels: d.corrections.map((c) => c.name),
          datasets: [
            { label: "Original (car.)", data: d.corrections.map((c) => c.orig_chars), backgroundColor: "rgba(255, 107, 107, 0.6)", borderRadius: 4 },
            { label: "Corrigé (car.)", data: d.corrections.map((c) => c.corr_chars), backgroundColor: "rgba(81, 207, 102, 0.6)", borderRadius: 4 },
          ],
        },
        options: { responsive: true, maintainAspectRatio: false, scales: baseScaleOptions(), plugins: legendOptions() },
      });
    } else {
      emptyState("corrCompareChart", "bi-arrow-left-right", "Aucune correction pour le moment");
    }
  }

  // Répartition erreurs par type (donut)
  const errorType = document.getElementById("errorTypeChart") as HTMLCanvasElement | null;
  if (errorType) {
    if (d.errorCategories.length > 0) {
      new Chart(errorType, {
        type: "doughnut",
        data: {
          labels: d.errorCategories.map((c) => c.category),
          datasets: [{ data: d.errorCategories.map((c) => c.count), backgroundColor: ERROR_COLORS.slice(0, d.errorCategories.length) }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: "bottom", labels: { color: LEGEND_DARK, padding: 10, font: { size: 11 } } } },
          cutout: "55%",
        },
      });
    } else {
      emptyState("errorTypeChart", "bi-check-circle", "Aucune erreur — tout fonctionne !");
    }
  }

  // Tendance erreurs 7 jours (barres empilées par catégorie)
  const errorTrend = document.getElementById("errorTrendChart") as HTMLCanvasElement | null;
  if (errorTrend) {
    if (d.errorDays.length > 0) {
      const allCats = new Set<string>();
      d.errorDays.forEach((day) => Object.keys(day.categories || {}).forEach((c) => allCats.add(c)));
      const catList = Array.from(allCats);
      const datasets = catList.map((cat, i) => ({
        label: cat,
        data: d.errorDays.map((day) => day.categories?.[cat] || 0),
        backgroundColor: ERROR_COLORS[i % ERROR_COLORS.length],
        borderRadius: 3,
      }));
      new Chart(errorTrend, {
        type: "bar",
        data: { labels: d.errorDays.map((day) => day.label), datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { stacked: true, ticks: { color: AXIS_DARK }, grid: { color: GRID_DARK } },
            y: { stacked: true, ticks: { color: AXIS_DARK, stepSize: 1 }, grid: { color: GRID_DARK } },
          },
          plugins: { legend: { labels: { color: LEGEND_DARK, font: { size: 10 } } } },
        },
      });
    } else {
      emptyState("errorTrendChart", "bi-graph-up", "Aucune erreur cette semaine");
    }
  }

  // Tableau détaillé des erreurs
  if (d.errorDetails.length > 0) {
    const tbody = document.getElementById("errorTableBody");
    if (!tbody) return;
    d.errorDetails.forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML =
        `<td style="max-width:200px;" title="${e.name}">${e.name}</td>` +
        `<td><span class="badge" style="background: rgba(255,107,107,0.2); color: #dc2626;">${e.category}</span></td>` +
        `<td class="duration">${e.created_at}</td>` +
        `<td style="max-width:400px; font-size:0.82rem; color: var(--text-secondary);" title="${e.error_msg}">${e.error_msg}</td>`;
      tbody.appendChild(tr);
    });
  }
}