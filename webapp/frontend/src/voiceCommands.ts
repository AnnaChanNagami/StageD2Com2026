// ============================================================
// voiceCommands.ts — Module de commandes vocales (speech-to-text + actions)
// ============================================================

let recognition: any = null;
let isListening = false;
let commandsEnabled = false;

function toggleMicIcon(listening: boolean): void {
  const iconEl = document.getElementById('mic-icon') as HTMLElement;
  if (!iconEl) return;
  const icon = iconEl.querySelector('i');
  if (listening) {
    iconEl.classList.replace('text-muted', 'text-success');
    icon?.classList.replace('bi-mic', 'bi-mic-fill');
  } else {
    iconEl.classList.replace('text-success', 'text-muted');
    icon?.classList.replace('bi-mic-fill', 'bi-mic');
  }
}

function updateStatus(text: string, statusClass: string): void {
  const statusEl = document.getElementById('voice-status') as HTMLElement;
  if (!statusEl) return;
  statusEl.innerHTML = `<span class="badge ${statusClass}">${text}</span>`;
}

function executeCommand(cmd: string): void {
  console.log('Commande vocale:', cmd);
  updateStatus('Commande reconnue : ' + cmd, 'bg-primary text-white');
  // Actions UI simples basées sur les commandes
  switch (cmd) {
    case 'lancer la transcription':
      // Cliquer sur le bouton d'upload principal si disponible
      const uploadBtn = document.querySelector('.drop-zone') as HTMLElement;
      if (uploadBtn) uploadBtn.click();
      break;
    case 'arrêter':
      // Simuler un arrêt de la transcription (si en cours)
      alert('Transcription arrêtée');
      break;
    case 'télécharger le txt':
      // Rechercher un bouton de téléchargement
      const dlBtn = document.querySelector('.btn-primary') as HTMLElement;
      if (dlBtn) dlBtn.click();
      break;
    case 'montrer la liste des jobs':
      // Aller à la page d'historique (liste des jobs)
      window.location.href = '/jobs/';
      break;
    case 'montrer le dashboard':
      // Aller à la page de statistiques (dashboard)
      window.location.href = '/';
      break;
    default:
      console.warn('Commande inconnue :', cmd);
  }
}

function startVoiceRecognition(): void {
  if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
    updateStatus('API de reconnaissance vocale non supportée', 'bg-danger text-white');
    alert('Votre navigateur ne supporte pas la reconnaissance vocale.');
    return;
  }

  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = 'fr-FR';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isListening = true;
    updateStatus('Écoute...', 'bg-info text-white');
    toggleMicIcon(true);
  };

  recognition.onresult = (event: any) => {
    const transcript = event.results[0][0].transcript.trim().toLowerCase();
    const confidence = event.results[0][0].confidence;
    updateStatus(`Reconnu (${confidence.toFixed(2)}): ${transcript}`, 'bg-success text-white');
    // Exécuter la commande après un court délai pour l'expérience utilisateur
    setTimeout(() => {
      executeCommand(transcript);
    }, 500);
  };

  recognition.onerror = (event: any) => {
    console.error('Erreur de reconnaissance vocale:', event.error);
    updateStatus('Erreur : ' + event.error, 'bg-danger text-white');
    stopVoiceRecognition();
  };

  recognition.onend = () => {
    isListening = false;
    toggleMicIcon(false);
    updateStatus('Arrêtée', 'bg-secondary');
  };

  recognition.start();
  commandsEnabled = true;
}

function stopVoiceRecognition(): void {
  if (recognition) {
    recognition.stop();
    recognition = null;
  }
  isListening = false;
  commandsEnabled = false;
  toggleMicIcon(false);
}

export function initVoiceCommands(): void {
  // Bouton du menu principal (navbar)
  const voiceBtn = document.getElementById('voice-command-btn');
  if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
      const modal = new (window as any).bootstrap.Modal(document.getElementById('voiceCommandModal'));
      modal.show();
    });
  }

  // Bouton de dictée (navbar)
  const dictBtn = document.getElementById('dictation-btn');
  if (dictBtn) {
    dictBtn.addEventListener('click', () => {
      // Pour l'instant, redirige vers l'upload, 
      // ou pourrait démarrer une dictée en direct vers un job
      window.location.href = '/upload/';
    });
  }

  // Bouton "Démarrer l'écoute" dans le modal
  const startBtn = document.getElementById('start-voice-command');
  if (startBtn) {
    startBtn.addEventListener('click', () => {
      startVoiceRecognition();
      // Désactiver le bouton après démarrage
      (startBtn as HTMLButtonElement).disabled = true;
    });
  }

  // Fermer la modal -> arrêter l'écoute
  const modalEl = document.getElementById('voiceCommandModal');
  if (modalEl) {
    modalEl.addEventListener('hidden.bs.modal', () => {
      stopVoiceRecognition();
      const startBtn = document.getElementById('start-voice-command') as HTMLButtonElement;
      if (startBtn) startBtn.disabled = false;
      updateStatus('En attente...', 'bg-secondary');
    });
  }

  // Support des commandes hot-key "activation" (simulation) - optionnel
  document.addEventListener('keydown', (e) => {
    if (e.key.toLowerCase() === 'a' && e.ctrlKey) {
      e.preventDefault();
      if (!commandsEnabled) {
        startVoiceRecognition();
      }
    }
  });
}

// Expose pour debugging (optionnel)
(window as any).voiceCommands = { startVoiceRecognition, stopVoiceRecognition };