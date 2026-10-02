"""Vues du widget embarquable.

Les endpoints API du widget réutilisent le modèle TranscriptionJob de
l'application principale (même file de travail, même worker run_worker) :
le contrat de données est identique à /jobs/create/ et /api/status/<id>/.
"""
from django.shortcuts import render

from transcriptions.views import api_job_create, api_job_status

# Ré-exporte pour widget/urls.py  : upload + statut partagent le même backend
upload_audio = api_job_create
job_status = api_job_status

# Vues pour les pages de démonstration du widget
def widget_standalone(request):
    """Page autonome qui héberge le widget (test sur le même serveur)."""
    return render(request, "widget/widget.html", {"active": "widget"})


def widget_demo(request):
    """Page de démonstration montrant comment intégrer le widget."""
    return render(request, "widget/widget_demo.html", {"active": "widget"})