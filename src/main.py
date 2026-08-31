"""Point d'entrée de l'outil Speech-to-Text "mains libres".

Usage :
    python src/main.py

Comportement
------------
- Une touche (configurée dans config/settings.py, par défaut F8) sert
  d'interrupteur : appuyer -> DÉMARRE l'enregistrement ; rappuyer ->
  ARRÊTE et sauvegarde la transcription.
- Le raccourci est GLOBAL : il fonctionne même si une autre fenêtre
  a le focus (idéal quand on a les mains prises).
- Pendant l'enregistrement, chaque phrase reconnue s'affiche en direct.
- À l'arrêt, le texte complet est écrit dans /recordings/.
- Un petit bip sonore confirme le démarrage / l'arrêt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path as _P

# Rend `config` importable (chemin relatif au dossier projet).
PROJECT_ROOT = _P(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "config"))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import settings  # noqa: E402
from transcripteur.engine import AudioCapture, Transcriber, TranscriptSession  # noqa: E402
from transcripteur.saver import save_transcript  # noqa: E402

# ---------------------------------------------------------------------------
# Couleurs console (ANSI) — optionnelles.
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"


def _c(color_code: str, text: str) -> str:
    if settings.USE_COLORS:
        return f"{color_code}{text}{RESET}"
    return text


def _beep() -> None:
    """Joue un petit bip via le haut-parleur du PC (Windows inclus)."""
    if settings.BEEP_ON_TOGGLE:
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# État global partagé entre la boucle clavier (thread) et la boucle micro.
# ---------------------------------------------------------------------------
class RecorderState:
    def __init__(self):
        self.recording = False
        self.quit = False


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------
def run() -> None:
    transcriber = Transcriber(settings.STT_ENGINE)
    state = RecorderState()
    session: TranscriptSession | None = None

    # --- Raccourcis clavier globaux -------------------------------------
    try:
        import keyboard
    except ImportError:
        print(_c(RED, "[ERREUR] Le module 'keyboard' est requis."))
        print("Installe-le avec : pip install keyboard  (admin requis)")
        sys.exit(1)

    def toggle():
        if state.recording:
            stop_recording(session)
        else:
            start_recording()

    def start_recording():
        nonlocal session
        if state.recording:
            return
        session = TranscriptSession()
        state.recording = True
        _beep()
        print(_c(GREEN, "\n>>> ENREGISTREMENT EN COURS (rappuie sur "
                        f"{settings.TOGGLE_KEY} pour arrêter)"))
        print(_c(CYAN, "    Écoute... (transcription en direct)\n"))

    def stop_recording(sess):
        state.recording = False
        _beep()
        if sess is None:
            return
        path = save_transcript(sess.text)
        dur = sess.duration
        print(_c(RED, f"\n<<< ENREGISTREMENT ARRÊTÉ ({dur:.1f} s)"))
        print(_c(YELLOW, f"    Sauvegardé dans : {path}"))
        print(_c(CYAN, "    Appuie de nouveau pour enregistrer, "
                       f"ou {settings.QUIT_SHORTCUT} pour quitter."))

    # Enregistrement des raccourcis (hooks globaux).
    keyboard.add_hotkey(settings.TOGGLE_KEY, toggle)
    if settings.QUIT_HOTKEY_ENABLED:
        try:
            keyboard.add_hotkey(settings.QUIT_SHORTCUT, lambda: setattr(state, "quit", True))
        except Exception as exc:
            print(_c(YELLOW, f"[avertissement] quitter via clavier indisponible : {exc}"))

    # Affichage d'accueil.
    print(_c(BOLD, "=== Outil Speech-to-Text 'mains libres' ==="))
    print(f"  Touche pour démarrer/arrêter : {settings.TOGGLE_KEY}")
    print(f"  Touche pour quitter           : {settings.QUIT_SHORTCUT}")
    print(f"  Moteur de transcription      : {settings.STT_ENGINE}")
    print(f"  Langue                       : {settings.LANG}")
    print(_c(GREEN, "\n  Appuie sur la touche pour démarrer. Bon enregistrement !"))
    print("-" * 50)

    # Boucle d'écoute : vérifie la touche et fait tourner la capture.
    # On ne garde PAS la boucle `keyboard.wait()` seule : on intercale des
    # vérifications pour gérer l'arrêt y compris pendant une capture.
    while not state.quit:
        if state.recording and session is not None:
            # Fait tourner la capture en blocs ; on sort à chaque fin de bloc
            # pour laisser la boucle re-vérifier l'état (arrêt/quit).
            def on_text(t):
                print(_c(CYAN, f"  → {t.strip()}"))

            capture = AudioCapture(transcriber, session)
            capture.run(on_text=on_text, stop_check=lambda: (not state.recording) or state.quit)
        else:
            # En attente du déclencheur.
            time.sleep(0.05)

    print(_c(BOLD, "\nAu revoir !"))

    # Nettoyage des hooks clavier (nécessaire sinon 'keyboard' garde l'app).
    keyboard.unhook_all()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nInterruption. Au revoir !")
