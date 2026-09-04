"""
Worker de transcription Qwen3-ASR : boucle en continu et traite les jobs en attente.

Usage :
    python manage.py run_worker               # boucle continue
    python manage.py run_worker --once        # un seul job puis exit
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from transcriptions import qwen_service
from transcriptions.models import TranscriptionJob


class Command(BaseCommand):
    help = "Worker Qwen3-ASR : traite les transcriptions en attente."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Traite un seul job puis quitte.")
        parser.add_argument("--interval", type=int, default=3, help="Intervalle entre vérifications (secondes).")

    def handle(self, *args, **options):
        once = options["once"]
        interval = options["interval"]

        self.stdout.write(self.style.SUCCESS("✓ Worker Qwen3-ASR démarré"))
        if not qwen_service.backend_available():
            self.stderr.write(self.style.WARNING("⚠  Backend Qwen3 non disponible (torch manquant ?)."))
            self.stderr.write("   Le worker tournera mais les transcriptions échoueront.")

        while True:
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
