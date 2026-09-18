// ============================================================
// corrections.ts — Page liste des corrections : graphiques CER/WER
// Données via <script type="application/json" id="corrChartData">
// ============================================================
export function initCorrections() {
    const jsonEl = document.getElementById("corrChartData");
    if (!jsonEl?.textContent)
        return;
    const d = JSON.parse(jsonEl.textContent);
    if (d.labels.length > 0) {
        // Barres CER/WER
        new Chart(document.getElementById("error-chart"), {
            type: "bar",
            data: {
                labels: d.labels,
                datasets: [
                    { label: "CER (%)", data: d.cer, backgroundColor: "#f97316", borderRadius: 4 },
                    { label: "WER (%)", data: d.wer, backgroundColor: "#3b82f6", borderRadius: 4 },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { labels: { color: "#94a3b8", font: { size: 11 } } },
                    tooltip: { callbacks: { label: (ctx) => ctx.dataset.label + ": " + ctx.parsed.y + "%" } },
                },
                scales: {
                    x: { ticks: { color: "#64748b", font: { size: 10 }, maxRotation: 45 }, grid: { display: false } },
                    y: { ticks: { color: "#64748b", callback: (v) => v + "%" }, grid: { color: "rgba(148,163,184,0.1)" }, beginAtZero: true },
                },
            },
        });
        // Donut CER vs correct
        const avgCer = d.avgCer;
        new Chart(document.getElementById("errors-pie"), {
            type: "doughnut",
            data: {
                labels: ["Erreurs (CER)", "Correct"],
                datasets: [{ data: [avgCer, 100 - avgCer], backgroundColor: ["#f97316", "#10b981"], borderWidth: 0 }],
            },
            options: {
                responsive: true,
                cutout: "60%",
                plugins: { legend: { labels: { color: "#94a3b8", font: { size: 11 } } } },
            },
        });
    }
}
