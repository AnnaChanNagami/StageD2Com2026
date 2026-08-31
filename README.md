# 🎤 Outil Speech-to-Text "mains libres"

Transcrivez votre voix en texte **sans toucher au clavier** : vous êtes en
train de travailler (les mains prises), vous appuyez sur une **même touche**
pour démarrer l'enregistrement, votre voix est retranscrite **en direct** à
l'écran, et vous **rappuyez sur la même touche** pour arrêter et sauvegarder
automatiquement la transcription dans un fichier texte.

---

## ✨ Fonctionnalités

- **Interrupteur sur une seule touche** (par défaut `F8`) : appuyer = on, rappuyer = off.
- Raccourci **global** : il fonctionne même si une autre fenêtre a le focus.
- Transcription **en temps réel** affichée au fur et à mesure dans le terminal.
- **Sauvegarde automatique** d'un fichier `.txt` horodaté dans `/recordings/` à l'arrêt.
- **Bip sonore** au démarrage / arrêt (pratique quand on ne peut pas regarder l'écran).
- Langue configurable (français par défaut).

---

## 🛠️ Installation

> ⚠️ **Python 3.11 recommandé** : `pyaudio` ne fournit pas de binaire (wheel)
> pour les versions récentes (3.12, 3.13, 3.14) sous Windows, ce qui bloque
> son installation. Utilisez Python 3.11 (ex. `py -V:Astral/CPython3.11.15`
> pour lancer la commande avec cette version). Un environnement virtuel est
> **déjà préparé** dans `.venv` avec tout installé.

### 1. Créer un environnement virtuel (recommandé)

Depuis le dossier du projet :

```bash
python -m venv .venv
```

Sur Windows, activer l'environnement :

```bash
.venv\Scripts\activate
```

### 2. Installer les dépendances

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ **`pyaudio` sous Windows** : l'installation classique échoue parfois.
> Dans ce cas, utilisez `pipwin` :
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

> ℹ️ Le module `keyboard` peut nécessiter des **droits administrateur**
> (Windows) pour capter les raccourcis globaux. Relancez le terminal en
> administrateur si besoin.

---

## 🚀 Utilisation

```bash
.venv\Scripts\activate        # activer l'environnement (Windows)
python src\main.py            # lancer l'outil
```

Puis :

1. **Appuyez sur `F8`** → un bip retentit, l'enregistrement démarre
   (`>>> ENREGISTREMENT EN COURS`).
2. **Parlez** : chaque phrase reconnue s'affiche en direct.
3. **Rappuyez sur `F8`** → un bip retentit, l'enregistrement s'arrête et le
   fichier est sauvegardé dans `/recordings/`.
4. Pour **quitter** : `Ctrl + Alt + Q`.

---

## ⚙️ Configuration

Tout se règle dans [`config/settings.py`](config/settings.py) :

| Réglage               | Défaut  | Description                                       |
|-----------------------|---------|---------------------------------------------------|
| `TOGGLE_KEY`          | `F8`    | La touche on/off                                  |
| `QUIT_SHORTCUT`       | `Ctrl+Alt+Q` | Combinaison pour quitter                |
| `STT_ENGINE`          | `google`| `google`, `vosk` (hors-ligne) ou `whisper`        |
| `LANG`                | `fr-FR` | Langue parlée                                     |
| `INPUT_DEVICE_INDEX`  | `None`  | Index du micro (voir `list_devices.py`)           |

---

## 📁 Structure du projet

```
Outil Speech to text/
├── config/
│   └── settings.py            # Toute la configuration
├── src/
│   ├── main.py                # Point d'entrée + raccourcis clavier
│   ├── list_devices.py        # Affiche les micros disponibles
│   └── transcripteur/
│       ├── engine.py          # Capturer le micro + transcrire
│       └── saver.py           # Sauvegarde des .txt
├── recordings/                # Transcriptions sauvegardées (créé à l'usage)
├── requirements.txt
└── README.md
```

---

## 🔌 Brancher un autre moteur (Whisper, Vosk…)

Le code est découpé pour être facilement extensible :
- `AudioCapture` gère le micro (pyaudio).
- `Transcriber.transcribe_audio()` transforme un morceau audio en texte.
- Pour ajouter `vosk` ou `whisper`, il suffit d'étendre
  `Transcriber.transcribe_audio()` et de régler `STT_ENGINE` en conséquence.

Bon enregistrement ! 🎙️
