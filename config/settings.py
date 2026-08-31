"""Configuration centrale de l'outil Speech-to-Text.

Toutes les constantes réglables sont ici, au même endroit, pour qu'il soit
facile de changer de touche, de langue, de moteur de transcription, etc.
sans toucher au reste du code.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------
# Racine du projet (le dossier qui contient ce fichier, remonté de 1 niveau).
BASE_DIR = Path(__file__).resolve().parent.parent

# Dossier où sont sauvegardées les transcriptions (fichiers .txt).
OUTPUT_DIR = BASE_DIR / "recordings"

# ---------------------------------------------------------------------------
# Racourci clavier (démarre / arrête l'enregistrement)
# ---------------------------------------------------------------------------
# Touche qui sert d'interrupteur. "appuyer = on", "rappuyer = off".
# Exemples : "F8", "scroll lock", "insert", "f12", "`", ...
TOGGLE_KEY = "F8"

# Si True, on sort du programme quand on appuie sur cette combinaison.
QUIT_SHORTCUT = "ctrl+alt+q"
QUIT_HOTKEY_ENABLED = True

# ---------------------------------------------------------------------------
# Reconnaissance vocale
# ---------------------------------------------------------------------------
# Moteur utilisé. Valeurs possibles :
#   - "google"  : API Google Web Speech (gratuit, en ligne, pas de clé).
#   - "vosk"    : hors-ligne, léger, bonne latence (nécessite `pip install vosk`).
#   - "whisper" : OpenAI Whisper (local ou API) - à brancher plus tard.
STT_ENGINE = "google"

# Langue parlée (code BCP-47).
LANG = "fr-FR"

# Durée max d'un "silence" (en secondes) avant de considérer qu'on
# peut envoyer ce qu'on a entendu. 0 = pas de coupure auto (on reste
# en écoute tant que l'interrupteur est actif).
PAUSE_THRESHOLD = 0.8

# Petite pause après détection d'un silence, pour éviter les doublons.
PHRASE_TIME_LIMIT = 5

# ---------------------------------------------------------------------------
# Micro / Audio
# ---------------------------------------------------------------------------
# Indice du périphérique d'entrée (None = micro par défaut du système).
# Pour lister les périphériques : lancer `python src/list_devices.py`.
INPUT_DEVICE_INDEX = None

# Taille des blocs audio envoyés au moteur (en secondes). Pour le moteur
# "google", une valeur de 1 seconde est un bon compromis latence/précision.
CHUNK_SECONDS = 1.0

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------
# Couleurs ANSI pour l'affichage console (True = couleur, sinon désactivé).
USE_COLORS = True

# Bip sonore au démarrage / à l'arrêt de l'enregistrement.
# True = on joue un petit bip avec le haut-parleur du PC.
BEEP_ON_TOGGLE = True
