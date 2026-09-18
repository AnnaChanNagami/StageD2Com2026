// ============================================================
// upload.ts — Page upload : drag-drop, envoi, polling statut
// ============================================================
import { createJob, getStatus } from "./api.js";
function formatBytes(bytes) {
    return (bytes / (1024 * 1024)).toFixed(1) + " Mo";
}
export function initUpload() {
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("audioFile");
    const fileInfo = document.getElementById("fileInfo");
    const submitBtn = document.getElementById("submitBtn");
    const statusBox = document.getElementById("statusBox");
    const statusText = document.getElementById("statusText");
    const statusBar = document.getElementById("statusBar");
    const statusDetail = document.getElementById("statusDetail");
    const form = document.getElementById("uploadForm");
    if (!dropZone || !fileInput || !submitBtn || !fileInfo || !form)
        return;
    // Références non-null pour les closures
    const input = fileInput;
    const btn = submitBtn;
    const info = fileInfo;
    // Drag-drop
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer?.files?.[0]) {
            input.files = e.dataTransfer.files;
            onFile();
        }
    });
    input.addEventListener("change", onFile);
    function onFile() {
        const f = input.files?.[0];
        if (!f) {
            info.style.display = "none";
            btn.disabled = true;
            return;
        }
        const nameEl = document.getElementById("fileName");
        const sizeEl = document.getElementById("fileSize");
        if (nameEl)
            nameEl.textContent = f.name;
        if (sizeEl)
            sizeEl.textContent = formatBytes(f.size);
        info.style.display = "block";
        btn.disabled = false;
    }
    function resetBtn() {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-play-fill"></i> Lancer la transcription';
    }
    // Bouton clearFile
    const clearBtn = info.querySelector("button");
    clearBtn?.addEventListener("click", () => {
        input.value = "";
        info.style.display = "none";
        btn.disabled = true;
    });
    // Submit
    btn.addEventListener("click", async () => {
        const f = input.files?.[0];
        if (!f)
            return;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Envoi…';
        const fd = new FormData();
        fd.append("audio_file", f);
        const langSel = document.getElementById("languageSelect");
        const promptIn = document.getElementById("promptInput");
        const tsCheck = document.getElementById("timestamps");
        const maxTok = document.getElementById("maxTokens");
        fd.append("language", langSel?.value ?? "");
        fd.append("prompt", promptIn?.value ?? "");
        fd.append("timestamps", tsCheck?.checked ? "1" : "");
        fd.append("max_tokens", maxTok?.value ?? "512");
        try {
            const createUrl = form.dataset.apiCreate || "/jobs/create/";
            const data = await createJob(fd, createUrl);
            if (data.id) {
                pollJob(data.id);
            }
            else {
                alert(data.error ?? "Erreur");
                resetBtn();
            }
        }
        catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            alert("Erreur réseau: " + msg);
            resetBtn();
        }
    });
    function pollJob(id) {
        if (!statusBox || !statusText || !statusBar || !statusDetail)
            return;
        statusBox.style.display = "block";
        const interval = setInterval(async () => {
            try {
                const d = await getStatus(id);
                statusText.textContent =
                    d.status === "completed"
                        ? "✅ Terminé"
                        : d.status === "failed"
                            ? "❌ " + (d.error ?? "Erreur")
                            : "⏳ " + (d.stage ?? d.status);
                statusBar.style.width = d.progress + "%";
                statusDetail.textContent =
                    d.status === "completed" ? "Redirection…" : d.progress + "%";
                if (d.status === "completed" || d.status === "failed") {
                    clearInterval(interval);
                    window.location.href = d.url ?? "/jobs/" + id + "/";
                }
            }
            catch {
                // silencieux, on réessaie
            }
        }, 1500);
    }
}
