// ============================================================
// main.ts — Point d'entrée : wiring global (utilisé par base.html)
// ============================================================
import { initJobDetail } from "./jobDetail.js";
import { initUpload } from "./upload.js";
import { initDashboard } from "./dashboard.js";
import { initCorrections } from "./corrections.js";
import { initCorrection } from "./correction.js";
import { initVoiceCommands } from "./voiceCommands.js"; // nouveau module vocal
function domReady(cb) {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", cb);
    }
    else {
        cb();
    }
}
domReady(() => {
    initJobDetail();
    initUpload();
    initDashboard();
    initCorrections();
    initCorrection();
    initVoiceCommands(); // initialisation des commandes vocales
});
