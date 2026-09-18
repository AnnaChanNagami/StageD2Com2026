// ============================================================
// correction.ts — Page de correction : compteurs, copie, reset,
// Ctrl+Enter sauvegarde, scroll audio approx.
// ============================================================
export function initCorrection() {
    const textarea = document.getElementById("correctedText");
    if (!textarea)
        return;
    const charCount = document.getElementById("charCount");
    const wordCount = document.getElementById("wordCount");
    if (!charCount || !wordCount)
        return;
    const ta = textarea;
    function updateCounts() {
        const text = ta.value;
        charCount.textContent = String(text.length);
        wordCount.textContent = String(text.trim() ? text.trim().split(/\s+/).length : 0);
    }
    textarea.addEventListener("input", updateCounts);
    updateCounts();
    // Copier la correction dans le presse-papiers
    const copyBtn = document.getElementById("copyBtn");
    if (copyBtn) {
        copyBtn.addEventListener("click", (event) => {
            const text = textarea.value;
            if (!text.trim()) {
                alert("La zone de correction est vide.");
                return;
            }
            navigator.clipboard
                .writeText(text)
                .then(() => {
                const btn = event.target.closest("button");
                if (!btn)
                    return;
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="bi bi-check-lg"></i> Copié !';
                btn.classList.remove("btn-outline-info");
                btn.classList.add("btn-outline-success");
                setTimeout(() => {
                    btn.innerHTML = originalHTML;
                    btn.classList.remove("btn-outline-success");
                    btn.classList.add("btn-outline-info");
                }, 2000);
            })
                .catch((err) => {
                console.error("Erreur copie :", err);
                alert("Impossible de copier. Essayez Ctrl+C.");
            });
        });
    }
    // Réinitialiser
    const resetBtn = document.getElementById("resetBtn");
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            if (!confirm("Effacer la correction enregistrée ?"))
                return;
            textarea.value = "";
            updateCounts();
            textarea.focus();
        });
    }
    // Ctrl+Enter pour sauvegarder
    textarea.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
            e.preventDefault();
            document.getElementById("correctionForm")?.submit();
        }
    });
    // Sync player → scroll original (approximatif)
    const originalText = textarea.dataset.original ?? "";
    const audio = document.querySelector("audio");
    if (audio && originalText) {
        audio.addEventListener("timeupdate", () => {
            const pct = audio.currentTime / (audio.duration || 1);
            const el = document.getElementById("originalText");
            if (el)
                el.scrollTop = pct * (el.scrollHeight - el.clientHeight);
        });
    }
}
