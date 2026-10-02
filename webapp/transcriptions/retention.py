"""
Politique de conservation des données (RGPD) — Qwen3-ASR Web.

Principe : une transcription peut contenir des données à caractère personnel
(voix, nom de fichier, contenu du texte transcrit). Conformément au principe de
limitation de la conservation (art. 5.1.e RGPD), ces données sont conservées
une durée limitée puis supprimées automatiquement.

Point important : la durée court à compter du DÉPÔT du fichier (`created_at`),
pas de la fin du traitement.

Ce module ne dépend que de Django (pas de torch) : il peut être importé par la
commande `purge_expired`, par le worker, ou par les tests.

Usage :
    from transcriptions import retention
    report = retention.purge_expired_jobs()          # purge réelle
    report = retention.purge_expired_jobs(dry_run=True)  # aperçu
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import TranscriptionJob

# Nombre moyen de jours par mois calendaire (28 à 31 selon le mois).
_DAYS_PER_MONTH = 30.44


# ---------------------------------------------------------------------------
# Configuration (surchargeable via settings)
# ---------------------------------------------------------------------------


def retention_months() -> int:
    """Durée de conservation en mois (6 par défaut)."""
    return max(1, int(getattr(settings, "RGPD_RETENTION_MONTHS", 6)))


def retention_days() -> int:
    """Durée de conservation en jours, dérivée de la durée en mois.

    On utilise une moyenne de 30,44 jours/mois : les mois calendaires n'ont pas
    tous la même longueur, et `timedelta(days=n)` ne gère pas les mois.
    """
    return int(round(retention_months() * _DAYS_PER_MONTH))


def is_enabled() -> bool:
    """La purge automatique est-elle active ? (désactivable sans toucher au code)"""
    return bool(getattr(settings, "RGPD_AUTO_PURGE", True))


def retention_cutoff(reference: datetime | None = None) -> datetime:
    """Date limite : tout job créé AVANT cette date est purgé."""
    now = reference or timezone.now()
    return now - timedelta(days=retention_days())


def _audio_path(job: TranscriptionJob) -> str | None:
    """Chemin du fichier audio d'un job, ou None si absent/illisible.

    À résoudre AVANT `job.delete()` : après suppression de la ligne, Django ne
    peut plus fournir l'accès au stockage.
    """
    if not job.audio_file:
        return None
    try:
        return job.audio_file.path
    except (ValueError, NotImplementedError, OSError):
        return None


def _purge_media_dir(path: str | None) -> bool:
    """Supprime `uploads/<uuid>/` s'il est vide. Retourne True si supprimé."""
    if not path:
        return False
    parent = Path(path).parent
    try:
        # On ne retire que le dossier du job, et seulement s'il est vide :
        # `uploads/` lui-même est partagé par tous les jobs.
        if parent.is_dir() and parent != Path(settings.MEDIA_ROOT) / "uploads":
            parent.rmdir()
            return True
    except OSError:
        pass
    return False


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------


@dataclass
class PurgeReport:
    """Compte rendu d'une exécution de purge."""

    rows_deleted: int = 0
    files_deleted: int = 0
    dirs_removed: int = 0
    skipped_active: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        prefix = "[SIMULATION] " if self.dry_run else ""
        parts = [
            f"{self.rows_deleted} transcription(s)",
            f"{self.files_deleted} fichier(s) audio",
        ]
        if self.dirs_removed:
            parts.append(f"{self.dirs_removed} dossier(s) vide(s)")
        if self.skipped_active:
            parts.append(f"{self.skipped_active} ignoré(s) en cours de traitement")
        if self.errors:
            parts.append(f"{len(self.errors)} erreur(s)")
        return prefix + " : " + ", ".join(parts)


# ---------------------------------------------------------------------------
# Purge
# ---------------------------------------------------------------------------


def purge_expired_jobs(
    *,
    reference: datetime | None = None,
    dry_run: bool = False,
    keep_rows: bool = False,
) -> PurgeReport:
    """Supprime les transcriptions plus anciennes que la durée de conservation.

    Args:
        reference: date de référence du calcul (défaut : maintenant).
        dry_run: True = ne supprime rien, compte seulement (pour prévisualiser).
        keep_rows: True = ne supprime que les FICHIERS audio et conserve les
            lignes en base (texte + statistiques). Par défaut False = purge
            complète : fichier audio + ligne.

    Returns:
        Un `PurgeReport` détaillant l'opération.
    """
    report = PurgeReport(dry_run=dry_run)
    cutoff = retention_cutoff(reference)

    expired = TranscriptionJob.objects.filter(created_at__lt=cutoff)

    # Un job en attente ou en cours est peut-être dans la file du worker :
    # ne jamais l'effacer (le worker lirait un objet disparu, ou le fichier
    # disparaîtrait sous ses pieds).
    active_statuses = [TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING]
    jobs = list(expired.exclude(status__in=active_statuses).order_by("created_at"))
    report.skipped_active = expired.filter(status__in=active_statuses).count()

    for job in jobs:
        path = _audio_path(job)

        if dry_run:
            report.rows_deleted += 1
            if path and os.path.isfile(path):
                report.files_deleted += 1
            continue

        # 1. Fichier audio
        if path:
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    report.files_deleted += 1
            except OSError as exc:
                report.errors.append(f"{job.id} — fichier audio : {exc}")

        # 2. Dossier uploads/<uuid>/ s'il est vide
        try:
            if _purge_media_dir(path):
                report.dirs_removed += 1
        except OSError as exc:
            report.errors.append(f"{job.id} — dossier : {exc}")

        # 3. Ligne en base (sauf si l'appelant veut garder l'historique)
        if keep_rows:
            continue
        try:
            job.delete()
            report.rows_deleted += 1
        except Exception as exc:  # noqa: BLE001 - on ne veut pas stopper la purge
            report.errors.append(f"{job.id} — ligne en base : {exc}")

    return report


def purge_orphan_files(*, dry_run: bool = False, force: bool = False) -> int:
    """Supprime les dossiers `uploads/<uuid>/` sans job correspondant en base.

    Filet de sécurité : si un job a été supprimé en base sans que son fichier
    parte (crash, restauration partielle), l'audio traînerait sur le disque
    indéfiniment — ce que le RGPD n'admet pas.

    Garde-fou : par défaut on ne touche QUE les dossiers dont la dernière
    modification est plus ancienne que la durée de conservation. Un dossier
    récent peut être un upload en cours (le dossier est créé avant que la ligne
    en base soit enregistrée) ; le supprimer bricks l'upload. `force=True`
    désactive ce délai — à réserver à une vérification manuelle.

    Returns:
        Le nombre de dossiers supprimés (ou qui l'auraient été en `dry_run`).
    """
    uploads_root = Path(settings.MEDIA_ROOT) / "uploads"
    if not uploads_root.is_dir():
        return 0

    # `values_list(..., flat=True)` sur une clé primaire `id` renvoie la VALEUR
    # (un UUID ici), pas un objet : pas de `.id` à appeler dessus.
    known_ids = {str(pk) for pk in TranscriptionJob.objects.values_list("id", flat=True)}
    min_age_seconds = 0 if force else retention_days() * 86400
    now = timezone.now().timestamp()
    removed = 0

    for child in uploads_root.iterdir():
        if not child.is_dir() or child.name in known_ids:
            continue
        if not force:
            try:
                age = now - child.stat().st_mtime
            except OSError:
                continue
            if age < min_age_seconds:
                # Trop récent : upload en cours, ou job créé il y a peu.
                # Le fichier sera purgé normalement à son échéance.
                continue
        try:
            if dry_run:
                removed += 1
                continue
            shutil.rmtree(child)   # dossier orphelin : tout son contenu est obsolète
            removed += 1
        except OSError:
            # Dossier encore utilisé (upload en cours) : on le laisse.
            continue
    return removed