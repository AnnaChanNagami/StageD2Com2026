// ============================================================
// correction.ts — Page de correction : compteurs, copie, reset,
// Ctrl+Enter sauvegarde, scroll audio approx.
// ============================================================

export function initCorrection(): void {
  const textarea = document.getElementById("correctedText") as HTMLTextAreaElement | null;
  if (!textarea) return;
  const charCount = document.getElementById("charCount");
  const wordCount = document.getElementById("wordCount");
  if (!charCount || !wordCount) return;

  const ta = textarea;
  function updateCounts(): void {
    const text = ta.value;
    charCount!.textContent = String(text.length);
    wordCount!.textContent = String(text.trim() ? text.trim().split(/\s+/).length : 0);
  }
  textarea.addEventListener("input", updateCounts);
  updateCounts();

  // Copier la correction dans le presse-papiers
  const copyBtn = document.getElementById("copyBtn") as HTMLButtonElement | null;
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
          const btn = (event.target as HTMLElement).closest("button") as HTMLButtonElement | null;
          if (!btn) return;
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
  const resetBtn = document.getElementById("resetBtn") as HTMLButtonElement | null;
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      if (!confirm("Effacer la correction enregistrée ?")) return;
      textarea.value = "";
      updateCounts();
      textarea.focus();
    });
  }

  // Ctrl+Enter pour sauvegarder
  textarea.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      e.preventDefault();
      (document.getElementById("correctionForm") as HTMLFormElement | null)?.submit();
    }
  });

  // Sync player → scroll original (approximatif)
  const originalText = textarea.dataset.original ?? "";
  const audio = document.querySelector("audio");
  if (audio && originalText) {
    audio.addEventListener("timeupdate", () => {
      const pct = audio.currentTime / (audio.duration || 1);
      const el = document.getElementById("originalText");
      if (el) el.scrollTop = pct * (el.scrollHeight - el.clientHeight);
    });
  }
}