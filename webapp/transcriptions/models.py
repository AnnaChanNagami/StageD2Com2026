from __future__ import annotations

import json
import uuid
from pathlib import Path

from django.db import models
from django.utils import timezone


class TranscriptionJob(models.Model):
    """Un travail de transcription : un fichier audio + son résultat Qwen3-ASR."""

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        RUNNING = "running", "En cours"
        COMPLETED = "completed", "Terminé"
        FAILED = "failed", "Échec"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Fichier d'entrée conservé sous MEDIA_ROOT/uploads/<uuid>/<nom>
    audio_file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    original_name = models.CharField(max_length=512, blank=True, default="")
    duration_sec = models.FloatField(null=True, blank=True)

    # Options d'inférence Qwen3-ASR
    prompt = models.TextField(blank=True, default="")       # contexte / hotwords
    language = models.CharField(max_length=32, blank=True, default="")  # langue forcée ("" = auto)
    max_new_tokens = models.IntegerField(default=512)
    want_timestamps = models.BooleanField(default=False)    # forced aligner activé ?

    # Cycle de vie
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    progress = models.FloatField(default=0.0)               # 0..1
    stage = models.CharField(max_length=64, blank=True, default="")
    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Résultat
    transcript_text = models.TextField(blank=True, default="")      # texte transcrit
    language_detected = models.CharField(max_length=64, blank=True, default="")
    segments_json = models.TextField(blank=True, default="")        # liste de segments horodatés
    segment_count = models.IntegerField(default=0)
    generated_tokens = models.IntegerField(null=True, blank=True)
    device = models.CharField(max_length=32, blank=True, default="")

    # Correction
    corrected_text = models.TextField(blank=True, default="")      # texte corrigé par l'utilisateur
    corrected_at = models.DateTimeField(null=True, blank=True)     # date de la dernière correction

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Transcription"
        verbose_name_plural = "Transcriptions"

    def __str__(self):
        return f"{self.original_name or self.id} ({self.status})"

    # --- Helpers ---------------------------------------------------------

    @property
    def elapsed_sec(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def media_name(self) -> str:
        """Nom du fichier audio stocké (pour les téléchargements)."""
        return Path(self.audio_file.name).name

    def set_status(self, status: str, *, save: bool = True) -> None:
        self.status = status
        if status == self.Status.RUNNING and not self.started_at:
            self.started_at = timezone.now()
        if status in (self.Status.COMPLETED, self.Status.FAILED):
            self.completed_at = timezone.now()
        if save:
            self.save(update_fields=["status", "started_at", "completed_at"])

    def parse_segments(self) -> list[dict]:
        """Segments issus de segments_json, triés par temps de début."""
        if not self.segments_json:
            return []
        try:
            segs = json.loads(self.segments_json)
        except (json.JSONDecodeError, TypeError):
            return []
        return sorted(segs, key=lambda s: s.get("start", 0.0))

    def total_words(self) -> int:
        return len(self.transcript_text.split()) if self.transcript_text.strip() else 0

    def total_chars(self) -> int:
        return len(self.transcript_text) if self.transcript_text else 0

    @property
    def ratio_audio(self) -> float:
        """Ratio temps d'analyse / durée audio (combien de fois l'analyse est plus longue que l'audio)."""
        if self.duration_sec and self.duration_sec > 0 and self.elapsed_sec:
            return round(self.elapsed_sec / self.duration_sec, 1)
        return 0.0
