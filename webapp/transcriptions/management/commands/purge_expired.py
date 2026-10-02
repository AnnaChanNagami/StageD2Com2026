"""
Commande de purge RGPD : supprime les transcriptions hors délai de conservation.

Usage :
    python manage.py purge_expired                 # purge réelle
    python manage.py purge_expired --dry-run       # aperçu, rien n'est supprimé
    python manage.py purge_expired --keep-rows     # ne supprime que les FICHIERS audio
    python manage.py purge_expired --orphans       # nettoie aussi les dossiers audio orphelins
    python manage.py purge_expired --status        # affiche l'état de la conservation
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from transcriptions import retention
from transcriptions.models import TranscriptionJob


class Command(BaseCommand):
    help = "Purge les transcriptions/audio dépassant la durée de conservation RGPD."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simule : affiche ce qui serait supprimé sans rien effacer.",
        )
        parser.add_argument(
            "--keep-rows",
            action="store_true",
            help="Ne supprime que les fichiers audio, conserve les lignes en base "
            "(texte + statistiques du dashboard).",
        )
        parser.add_argument(
            "--orphans",
            action="store_true",
            help="Supprime aussi les dossiers uploads/<uuid>/ sans job correspondant.",
        )
        parser.add_argument(
            "--status",
            action="store_true",
            help="Affiche la politique de conservation et le nombre de données à purger.",
        )

    def handle(self, *args, **options):
        months = retention.retention_months()
        days = retention.retention_days()
        cutoff = retention.retention_cutoff()

        self.stdout.write("")
        self.stdout.write("Politique de conservation RGPD")
        self.stdout.write(f"   Durée       : {months} mois ({days} jours)")
        self.stdout.write(f"   Date limite : {cutoff:%Y-%m-%d %H:%M} (purge au-delà)")
        self.stdout.write(f"   Auto-purge  : {'oui (worker)' if retention.is_enabled() else 'non (manuelle)'}")

        total = TranscriptionJob.objects.count()
        expired = TranscriptionJob.objects.filter(created_at__lt=cutoff).count()
        active = TranscriptionJob.objects.filter(
            created_at__lt=cutoff,
            status__in=[TranscriptionJob.Status.PENDING, TranscriptionJob.Status.RUNNING],
        ).count()
        self.stdout.write(
            f"   Données     : {total} transcription(s), {expired} hors délai "
            f"({active} en cours de traitement)"
        )

        if options["status"]:
            self.stdout.write("")
            return

        report = retention.purge_expired_jobs(
            dry_run=options["dry_run"],
            keep_rows=options["keep_rows"],
        )
        self.stdout.write("")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"   SIMULATION — {report.summary()}"))
        else:
            style = self.style.SUCCESS if report.ok else self.style.WARNING
            self.stdout.write(style(f"   ✓ {report.summary()}"))
            for err in report.errors:
                self.stdout.write(self.style.ERROR(f"   ✗ {err}"))

        if options["orphans"]:
            orphans = retention.purge_orphan_files(dry_run=options["dry_run"])
            verb = "trouvés" if options["dry_run"] else "supprimés"
            self.stdout.write(self.style.SUCCESS(f"   ✓ {orphans} dossier(s) audio orphelin(s) {verb}"))

        self.stdout.write("")