"""Moteur de reconnaissance vocale.

Ce module encapsule la capture micro + la transcription, en deux classes
distinctes pour rester simple à remplacer :

  - AudioCapture   : capture le micro en flux continu (pyaudio).
  - Transcriber    : convertit un morceau audio en texte (SpeechRecognition).

Le moteur réel (google / vosk / whisper) est choisi dans config/settings.py.
La couche "traitement en temps réel" est volontairement découplée du micro
pour pouvoir la brancher sur un vrai flux continu plus tard (ex: Whisper
streaming) sans tout réécrire.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parent.parent.parent / "config"))
import settings  # noqa: E402


@dataclass
class TranscriptSession:
    """Représente une session d'enregistrement en cours.

    Accumule toutes les phrases transcrites jusqu'à l'arrêt.
    Le timestamp permet d'obtenir un nom de fichier stable à la sauvegarde.
    """

    started_at: float = field(default_factory=time.time)
    phrases: list[str] = field(default_factory=list)

    def add(self, phrase: str) -> None:
        """Ajoute une phrase (texte déjà nettoyé)."""
        if phrase:
            self.phrases.append(phrase)

    @property
    def text(self) -> str:
        """Le texte complet, phrases séparées par des retours à la ligne."""
        return "\n".join(self.phrases)

    @property
    def duration(self) -> float:
        return time.time() - self.started_at


class Transcriber:
    """Interface unique vers le moteur de reconnaissance.

    Le paramètre `engine` est chargé paresseusement (lazy) : on n'importe
    le module tiers que lorsqu'on en a vraiment besoin, ce qui évite de
    bloquer le lancement si une dépendance manque.
    """

    def __init__(self, engine: str | None = None):
        self.engine = engine or settings.STT_ENGINE
        self._recognizer = None
        self._api = None

    def _ensure_loaded(self):
        """Charge le recognizer SpeechRecognition au premier usage."""
        if self._recognizer is None:
            try:
                import speech_recognition as sr
            except ImportError:
                raise RuntimeError(
                    "Le module 'speech_recognition' est requis. "
                    "Installe-le avec : pip install SpeechRecognition"
                )
            self._recognizer = sr
            self._api = sr.Recognizer()
            self._api.pause_threshold = settings.PAUSE_THRESHOLD
            self._api.phrase_time_limit = settings.PHRASE_TIME_LIMIT
        return self._api

    def transcribe_audio(self, audio) -> str:
        """Analyse un morceau audio déjà capturé et renvoie le texte.

        Retourne une chaîne vide si rien d'intelligible n'a été compris,
        plutôt que de lever une erreur — la boucle d'enregistrement s'en
        sert pour ignorer le silence.
        """
        api = self._ensure_loaded()
        try:
            if self.engine == "google":
                text = api.recognize_google(audio, language=settings.LANG)
            else:
                raise NotImplementedError(
                    f"Moteur '{self.engine}' pas encore implémenté dans ce squelette."
                )
            return text
        except self._recognizer.UnknownValueError:
            # Rien d'intelligible (silence, bruit) -> on ignore.
            return ""
        except self._recognizer.RequestError as exc:
            # Problème réseau / API.
            print(f"[erreur API] {exc}")
            return ""


class AudioCapture:
    """Capture micro en flux (pyaudio).

    On lit des blocs de CHUNK_SECONDS secondes ; chaque bloc est rendu
    "audible" par SpeechRecognition via `recognizer.record(source)`.
    """

    def __init__(self, transcriber: Transcriber, session: TranscriptSession):
        self.transcriber = transcriber
        self.session = session
        self._source = None
        self._aud = None

    def _ensure_loaded(self):
        if self._aud is None:
            try:
                import pyaudio
            except ImportError:
                raise RuntimeError(
                    "Le module 'pyaudio' est requis. "
                    "Installe-le avec : pip install pipwin && pipwin install pyaudio"
                )
            self._aud = pyaudio
        return self._aud

    def run(self, on_text=None, stop_check=None) -> str:
        """Écoute et transcrit en continu jusqu'à l'arrêt.

        Arguments
        ---------
        on_text    : callback appelé à chaque phrase transcrites (texte).
        stop_check : fonction() -> bool ; si elle renvoie True, on s'arrête
                     (vérifiée entre chaque bloc).

        Retour
        ------
        Le texte complet de la session (en plus de celui dans session.text).
        """
        api = self.transcriber._ensure_loaded()
        aud = self._ensure_loaded()

        stream = aud.open(
            format=aud.paInt16,
            channels=1,
            rate=16000,
            input=True,
            input_device_index=settings.INPUT_DEVICE_INDEX,
            frames_per_buffer=int(16000 * settings.CHUNK_SECONDS),
        )

        try:
            while True:
                if stop_check is not None and stop_check():
                    break

                # Capture une seconde d'audio et tente la transcription.
                data = stream.read(int(16000 * settings.CHUNK_SECONDS),
                                   exception_on_overflow=False)
                # SpeechRecognition veut un objet AudioData : on construit
                # une source in-memory en réutilisant l'API.
                audio = api.AudioData(data, 16000, 2)
                text = self.transcriber.transcribe_audio(audio)

                if text:
                    self.session.add(text)
                    if on_text:
                        on_text(text)
        finally:
            stream.stop_stream()
            stream.close()
            # N'ouvre pas aud.terminate ici : le contexte peut vouloir
            # redémarrer une capture.
        return self.session.text
