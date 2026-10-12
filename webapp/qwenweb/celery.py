"""Application Celery pour qwenweb.

Le broker et le backend de résultats sont Redis. Le worker Celery remplace
`manage.py run_worker` : il consomme les tâches de transcription depuis la
file et met à jour le modèle TranscriptionJob.
"""
from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "qwenweb.settings")

app = Celery("qwenweb")

# Configuration depuis Django settings (prefixe CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-découverte des tâches dans les apps installées
app.autodiscover_tasks()

# Health-check du backend Redis (reconnexion après idle)
app.conf.redis_backend_health_check_interval = 30

# Robustesse de connexion au broker (démarrage quand Redis n'est pas encore prêt)
app.conf.broker_connection_retry_on_startup = True
app.conf.broker_connection_max_retries = 10


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")