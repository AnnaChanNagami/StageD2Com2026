"""
Django settings for qwenweb project — Web UI Django pour Qwen3-ASR.

Projet d'application web (backend Django + templates rendus côté serveur)
autour du modèle Qwen/Qwen3-ASR (Alibaba) : transcription multilingue de
l'audio en texte, détection de langue, timestamps optionnels (forced aligner),
export SRT / TXT / JSON.
"""

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Répertoire racine du dépôt cloné (contient qwen_asr/).
# webapp/ est un sous-dossier du dépôt.
REPO_ROOT = BASE_DIR.parent

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-qwen3-asr-local-webapp-secret-key-7kd!$=^w&'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

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
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'qwenweb.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
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

# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

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
QWEN_DEVICE = "cuda:0"
QWEN_DTYPE = "bfloat16"           # bfloat16 | float16 | float32

QWEN_MAX_NEW_TOKENS = 512         # max de tokens générés par chunk
QWEN_MAX_CONTEXT_LEN = 500        # longueur max de texte de contexte / hotwords

# Backend d'inférence : "transformers" (CPU/GPU CUDA) — suffisant et portable.
# vLLM n'est utile que pour un service haute performance multi-requêtes.
QWEN_BACKEND = "transformers"

# Nom de la base affiché dans l'interface
QWEN_APP_TITLE = "Qwen3-ASR Web"

# DEFAULT_AUTO_FIELD
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
