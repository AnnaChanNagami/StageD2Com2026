"""Tâches Celery pour la transcription.

Remplace `manage.py run_worker` : chaque job devient une tâche asynchrone
consommée par un worker Celery (Redis comme broker/result backend).
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from transcriptions.models import TranscriptionJob
from transcriptions import qwen_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_job(self, job_id: str) -> dict:
    """
    Tâche Celery : exécute la transcription pour un TranscriptionJob.

    - Accepte l'ID du job (UUID string)
    - Met à jour job.stage / job.progress en temps réel via qwen_service.run_transcription
    - Retourne un dict de résultat (loggé par Celery, disponible dans result backend)
    """
    try:
        with transaction.atomic():
            job = TranscriptionJob.objects.select_for_update().get(id=job_id)
            if job.status != TranscriptionJob.Status.PENDING:
                logger.warning("Job %s n'est plus PENDING (%s), annulation", job_id, job.status)
                return {"status": "skipped", "reason": f"status={job.status}"}

            job.status = TranscriptionJob.Status.RUNNING
            job.stage = "queued"
            job.progress = 0.0
            job.save(update_fields=["status", "stage", "progress"])

        def on_status(stage: str, progress: float):
            """Callback appelé par qwen_service pendant l'inférence."""
            TranscriptionJob.objects.filter(id=job_id).update(
                stage=stage, progress=max(0.0, min(1.0, progress))
            )

        # Lancement de l'inférence (bloquant dans la tâche Celery)
        qwen_service.run_transcription(job, on_status=on_status)

        # Succès : recharger pour avoir les champs mis à jour par qwen_service
        job.refresh_from_db()
        logger.info("Job %s terminé — %d segments", job_id, job.segment_count)
        return {"status": "completed", "job_id": job_id, "segments": job.segment_count}

    except TranscriptionJob.DoesNotExist:
        logger.error("Job %s introuvable", job_id)
        return {"status": "error", "reason": "job not found"}

    except Exception as exc:
        logger.exception("Job %s échoué", job_id)
        # Marquer le job en erreur dans la base
        TranscriptionJob.objects.filter(id=job_id).update(
            status=TranscriptionJob.Status.FAILED,
            error=str(exc),
        )
        # Retry automatique (jusqu'à 3 fois avec délai exponentiel)
        raise self.retry(exc=exc)


# Tâche de purge RGPD — lancée périodiquement par Celery Beat
@shared_task
def purge_expired_jobs() -> dict:
    """
    Tâche périodique de purge RGPD. Remplace l'appel dans run_worker.py.
    """
    from transcriptions import retention

    if not retention.is_enabled():
        return {"status": "skipped", "reason": "RGPD non activé"}

    report = retention.purge_expired_jobs()
    return {
        "status": "completed",
        "rows_deleted": report.rows_deleted,
        "files_deleted": report.files_deleted,
        "errors": report.errors,
    }