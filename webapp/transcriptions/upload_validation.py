"""
Validation des fichiers audio téléversés : extension, type MIME, taille.

Règles :
  - extension dans ALLOWED_EXT
  - type MIME dans ALLOWED_MIME (avec tolérance : mimetypes peut renvoyer
    application/octet-stream pour certains formats valides)
  - taille <= MAX_UPLOAD_SIZE_MB (configurable via settings)

Chaque erreur de validation lève ValidationError avec un message en français
destiné à l'API JSON (et aux messages de l'interface).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

# Extensions acceptées (extensions de conteneurs audio/vidéo courantes).
ALLOWED_EXT = {
    ".wav", ".mp3", ".mp4", ".flac", ".m4a", ".ogg", ".opus",
    ".aac", ".wma", ".mov", ".mkv", ".webm", ".amr",
}

# Types MIME acceptés. "application/octet-stream" reste toléré : certains
# navigateurs / conteneurs (ogg, opus, mkv...) ne sont pas finement annoncés.
ALLOWED_MIME = {
    "audio/",
    "video/",
    "application/ogg",
    "application/octet-stream",
}

# Tailles maximales (octets). Lecture depuis settings, avec défauts sûrs.
MAX_UPLOAD_SIZE_MB = getattr(settings, "MAX_UPLOAD_SIZE_MB", 2000)
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024


def validate_file_size(file_obj) -> None:
    """Lève ValidationError si le fichier dépasse la taille maximale."""
    max_bytes = MAX_UPLOAD_SIZE
    if file_obj.size > max_bytes:
        size_mb = file_obj.size / (1024 * 1024)
        raise ValidationError(
            f"Fichier trop volumineux : {size_mb:.1f} Mo, "
            f"maximum autorisé {MAX_UPLOAD_SIZE_MB} Mo."
        )


def validate_extension(filename: str) -> None:
    """Lève ValidationError si l'extension du nom de fichier n'est pas autorisée."""
    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValidationError(
            f"Extension '{ext or '(aucune)'}' non prise en charge. "
            f"Autorisé : {', '.join(sorted(ALLOWED_EXT))}"
        )


def validate_mime_type(filename: str, content_type: str | None) -> None:
    """
    Lève ValidationError si le type MIME (annoncé par le client ou deviné
    depuis l'extension) n'est pas une famille autorisée (audio/*, video/*).
    """
    ct = (content_type or "").strip().lower().split(";")[0]
    # Déduction depuis l'extension quand le client n'annonce rien d'utile.
    if not ct or ct in ("application/octet-stream", "binary/octet-stream"):
        guessed, _ = mimetypes.guess_type(filename or "")
        ct = (guessed or "application/octet-stream").lower()

    if not ct:
        ct = "application/octet-stream"

    if ct in ALLOWED_MIME:
        return
    if any(ct.startswith(prefix) for prefix in ALLOWED_MIME if prefix.endswith("/")):
        return
    raise ValidationError(f"Type de fichier non autorisé : '{ct}'.")


def validate_audio_file(filename: str, content_type: str | None, size: int) -> None:
    """Valide un fichier uploadé (extension + MIME + taille). Lève ValidationError."""
    validate_extension(filename)
    validate_mime_type(filename, content_type)
    if size > MAX_UPLOAD_SIZE:
        size_mb = size / (1024 * 1024)
        raise ValidationError(
            f"Fichier trop volumineux : {size_mb:.1f} Mo, "
            f"maximum autorisé {MAX_UPLOAD_SIZE_MB} Mo."
        )