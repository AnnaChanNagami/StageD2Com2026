"""
Worker de transcription Qwen3-ASR : boucle en continu et traite les jobs en attente.

Usage :
    python manage.py run_worker               # boucle continue
    python manage.py run_worker --once        # un seul job puis exit
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand
from django.conf import settings

from transcriptions import qwen_service, retention
from transcriptions.models import TranscriptionJob
# Différents import pour le worker de transcription
# Création d'une classe Command qui hérite de BaseCommand pour définir le worker de transcription
class Command(BaseCommand):
    help = "Worker Qwen3-ASR : traite les transcriptions en attente."

#-------------Ajout d'arguments pour le worker de transcription--------------------------------------------------------------
    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Traite un seul job puis quitte.")
        parser.add_argument("--interval", type=int, default=3, help="Intervalle entre vérifications (secondes).")
        parser.add_argument(
            "--no-purge",
            action="store_true",
            help="Désactive la purge RGPD automatique dans ce worker.",
        )

    # ---------Purge RGPD : suppression automatique des données hors délai de conservation-------------------------------
    def _maybe_purge(self):
        """Lance la purge RGPD si elle est due. Ne lève jamais d'exception."""
        if not retention.is_enabled():
            return
        interval = int(getattr(settings, "RGPD_PURGE_INTERVAL_SEC", 6 * 3600))
        now = time.monotonic()
        if now - self._last_purge < interval:
            return
        self._last_purge = now
        try:
            report = retention.purge_expired_jobs()
            if report.rows_deleted or report.files_deleted:
                self.stdout.write(self.style.SUCCESS(f"🧹 Purge RGPD : {report.summary()}"))
                for err in report.errors:
                    self.stderr.write(self.style.WARNING(f"   ⚠  {err}"))
        except Exception as exc:  # noqa: BLE001 - la purge ne doit pas tuer le worker
            self.stderr.write(self.style.WARNING(f"⚠  Purge RGPD impossible : {exc}"))

#-------------Boucle principale du worker de transcription qui récupère les jobs en attente et les traite--------------------------------
    def handle(self, *args, **options):
        once = options["once"]
        interval = options["interval"]

        self._last_purge = 0.0
        if options["no_purge"]:
            self.stdout.write(self.style.WARNING("⏸  Purge RGPD automatique désactivée pour cette session."))

        self.stdout.write(self.style.SUCCESS("✓ Worker Qwen3-ASR démarré"))
        if not qwen_service.backend_available():
            self.stderr.write(self.style.WARNING("⚠  Backend Qwen3 non disponible (torch manquant ?)."))
            self.stderr.write("   Le worker tournera mais les transcriptions échoueront.")

        if retention.is_enabled() and not options["no_purge"]:
            self.stdout.write(
                f"   Conservation RGPD : {retention.retention_months()} mois "
                f"(purge automatique toutes les ~"
                f"{int(getattr(settings, 'RGPD_PURGE_INTERVAL_SEC', 21600) // 3600)} h)"
            )

        while True:
            self._maybe_purge()

            job = (
                TranscriptionJob.objects
                .filter(status=TranscriptionJob.Status.PENDING)
                .order_by("created_at")
                .first()
            )
            if job:
                self.stdout.write(f"\n⏳ Job : {job.original_name} ({job.id})")
                self.stdout.write(f"   Langue : {job.language or 'auto'} | Tokens : {job.max_new_tokens} | Timestamps : {job.want_timestamps}")

                def _status(stage, progress):
                    self.stdout.write(f"   → {stage} ({progress:.0%})" if progress else f"   → {stage}")

                try:
                    qwen_service.run_transcription(job, on_status=_status)
                    self.stdout.write(self.style.SUCCESS(f"   ✓ Terminé — {job.segment_count} segments"))
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"   ✗ Erreur : {exc}"))

                if once:
                    break
            else:
                time.sleep(interval)
