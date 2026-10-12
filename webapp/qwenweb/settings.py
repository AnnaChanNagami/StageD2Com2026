"""
Django settings for qwenweb project — Web UI Django pour Qwen3-ASR.

Projet d'application web (backend Django + templates rendus côté serveur)
autour du modèle Qwen/Qwen3-ASR (Alibaba) : transcription multilingue de
l'audio en texte, détection de langue, timestamps optionnels (forced aligner),
export SRT / TXT / JSON.
"""

from pathlib import Path
import os

# Construit des chemins dans le projet comme ceci : BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Aide de lecture des variables d'environnement : les valeurs par défaut
# ci-dessous sont celles du poste de développement, donc un lancement local
# (sans variable d'env) se comporte exactement comme avant. Elles servent à
# décrire l'environnement sans éditer ce fichier — c'est ce qu'utilisent les
# conteneurs Docker (voir docker-compose.yml) pour choisir CPU/GPU, la base
# SQLite et le dossier du cache HuggingFace.
def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]

# Répertoire racine du dépôt cloné (contient qwen_asr/, widget/).
# webapp/ est un sous-dossier du dépôt.
REPO_ROOT = BASE_DIR.parent

# Rend l'app autonome widget/ (à la racine du dépôt) importable depuis webapp/.
import sys
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Quick-start des paramètres de développement - inadapté pour la production
SECRET_KEY = os.environ.get(
    "QWEN_SECRET_KEY",
    'django-insecure-qwen3-asr-local-webapp-secret-key-7kd!$=^w&',
)

# ATTENTION : ne pas utiliser DEBUG=True en production, car cela peut exposer des informations sensibles 
DEBUG = _env_bool("QWEN_DEBUG", True)

ALLOWED_HOSTS = _env_list("QWEN_ALLOWED_HOSTS", ["*"])

# Renseigné quand l'application est servie derrière un reverse proxy / une
# adresse IP (les POST des formulaires Django sont alors refusés sans cette
# liste). Vide par défaut : rien ne change en local.
CSRF_TRUSTED_ORIGINS = _env_list("QWEN_CSRF_TRUSTED_ORIGINS", [])

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
        'transcriptions',
        'widget',
    ]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'widget.middleware.WidgetCorsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'qwenweb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates', REPO_ROOT / 'widget' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'qwenweb.wsgi.application'

# Base de données
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Validation des mots de passe
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Europe/Paris'
USE_I18N = True
USE_TZ = True

# fichiers statiques ( CSS, JavaScript, images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static', REPO_ROOT / 'widget' / 'static']

# Fichiers statiques collectés (utilisés par Whitenoise en conteneur)
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media (fichiers audio téléversés + exports)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Fichiers téléversés
MAX_UPLOAD_SIZE_MB = 2000
DATA_UPLOAD_MAX_MEMORY_SIZE = 2000 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 5

# ---------------------------------------------------------------------------
# Configuration du modèle Qwen3-ASR
# ---------------------------------------------------------------------------
# Chemin du dossier de poids pré-téléchargé (local) ou id HuggingFace.
#   - "Qwen/Qwen3-ASR-0.6B"  → léger, recommandé pour RTX 3060 6 Go
#   - "Qwen/Qwen3-ASR-1.7B"  → plus précis mais plus gourmand en VRAM
QWEN_ASR_MODEL = "Qwen/Qwen3-ASR-0.6B"

# Forced aligner optionnel pour produire des timestamps de mots/sous-titres.
#   - "Qwen/Qwen3-ForcedAligner-0.6B" pour activer les timestamps
#   - "" pour désactiver (gain de VRAM, pas de SRT)
QWEN_FORCED_ALIGNER = "Qwen/Qwen3-ForcedAligner-0.6B"

# Device et dtype : cuda:0 recommandé (GPU), "cpu" sinon ('auto' peut se
# rabattre sur un CPU fp32 très lent).
QWEN_DEVICE = os.environ.get("QWEN_DEVICE", "cpu")  # défaut CPU : multi-OS, GPU optionnel (cuda:0 / mps)
QWEN_DTYPE = "bfloat16"           # bfloat16 | float16 | float32

QWEN_MAX_NEW_TOKENS = 512         # max de tokens générés par chunk
QWEN_MAX_CONTEXT_LEN = 500        # longueur max de texte de contexte / hotwords

# Backend d'inférence : "transformers" (CPU/GPU CUDA) — suffisant et portable.
# vLLM n'est utile que pour un service haute performance multi-requêtes.
QWEN_BACKEND = "transformers"

# Nom de la base affiché dans l'interface
QWEN_APP_TITLE = "Qwen3-ASR Web"

# Remplissage automatique du champ "prompt" avec des mots-clés pour guider la transcription
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Configuration Celery / Redis
# ---------------------------------------------------------------------------
# Broker et backend de résultats : Redis (défaut localhost:6379)
# Peut être surchargé par variables d'env : CELERY_BROKER_URL, CELERY_RESULT_BACKEND
# NB : le Redis local est en 3.0.504, qui ne connaît pas la commande HELLO (RESP3)
# envoyée par défaut par redis-py >= 6. D'où le pin redis==5.2.1 dans requirements.txt,
# qui reste en RESP2. Ne pas ajouter "?protocol=2" aux URLs : kombu le rejette
# (TypeError: Connection._init_params() got an unexpected keyword argument 'protocol').
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Sérialisation JSON uniquement (sécurité)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]

# Timezone
CELERY_TIMEZONE = "Europe/Paris"
CELERY_ENABLE_UTC = True

# Workers non pré-fetch pour jobs longs (transcription = minutes)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True

# Résultats expirent après 24h
CELERY_RESULT_EXPIRES = 86400

# Routage : file dédiée pour la transcription
CELERY_TASK_ROUTES = {
    "transcriptions.tasks.*": {"queue": "transcription"},
}

# Beat schedule : purge RGPD quotidienne (02:00)
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "purge-expired-jobs-daily": {
        "task": "transcriptions.tasks.purge_expired_jobs",
        "schedule": crontab(hour=2, minute=0),
    },
}

# ---------------------------------------------------------------------------
# Conservation des données (RGPD — art. 5.1.e : limitation de la conservation)
# ---------------------------------------------------------------------------
# Les audios et transcriptions contiennent potentiellement des données à
# caractère personnel : ils sont supprimés après RGPD_RETENTION_MONTHS mois.
# La purge est déclenchée automatiquement par le worker (voir run_worker.py)
# et peut aussi être lancée manuellement :  python manage.py purge_expired
RGPD_RETENTION_MONTHS = int(os.environ.get("QWEN_RGPD_RETENTION_MONTHS", "6"))
# False = ne purger que manuellement (via la commande), sans depuis le worker.
RGPD_AUTO_PURGE = os.environ.get("QWEN_RGPD_AUTO_PURGE", "1") not in ("0", "false", "False")
# Fréquence (en secondes) des vérifications de purge dans la boucle du worker.
RGPD_PURGE_INTERVAL_SEC = int(os.environ.get("QWEN_RGPD_PURGE_INTERVAL_SEC", str(6 * 3600)))
