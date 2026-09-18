# Synthèse de la conversation — Projet Scribe (Qwen3-ASR)

Date : 16 septembre 2026

## 1. Contexte

Projet **Scribe** : application web Django de transcription audio multilingue, basée sur le modèle
**Qwen3-ASR-0.6B** (Alibaba). Le dépôt cloné contient le package Python `qwen_asr` (transformers +
backends vllm) et, en sous-dossier **webapp/**, l'interface web Django qui utilise ce modèle.

## 2. Objectif de la session

Relancer le projet Scribe (serveur web + worker de transcription) après arrêt.

## 3. Actions effectuées

1. **Lecture du guide de démarrage** (`LISEZMOI-DEMARRAGE.txt`) — l'application se lance en deux
   processus depuis le dossier `webapp/` :

   - **Terminal 1 — Serveur web** : `../.venv/Scripts/python.exe manage.py runserver 0.0.0.0:8002 --noreload`
     → accès sur http://127.0.0.1:8002
   - **Terminal 2 — Worker** : `../.venv/Scripts/python.exe manage.py run_worker`
     (le modèle Qwen3-ASR-0.6B est chargé sur le GPU RTX 3060 au premier job)

2. **Vérification de l'environnement** : le venv `.venv` existe bien à la racine du dépôt.

3. **Lancement du serveur web** en arrière-plan :
   - PID 15668, démarrage OK (« Starting development server at http://0.0.0.0:8002/ »)
   - Vérifié par HTTP : `/` → 200, `/api/stats/` → 200

4. **Lancement du worker** en arrière-plan :
   - PID 25276, « ✓ Worker Scribe démarré »

## 4. État du système (vérifié)

- Serveur web **opérationnel** sur http://127.0.0.1:8002 (Django 5.2.17)
- Worker **opérationnel**, en attente de jobs
- API `/api/stats/` : 2 transcriptions au total, **2 terminées**, 0 en cours, 0 échec
- Base SQLite : ~78 860 octets d'audio traités, 10 mots transcrits

## 5. Arborescence du projet

```
Qwen3-ASR/                           ← racine du dépôt
├── pyproject.toml                   ← package Python qwen-asr (v0.0.6, Apache-2.0)
├── README.md / LICENSE / MANIFEST.in
├── LISEZMOI-DEMARRAGE.txt           ← guide de démarrage (serveur + worker)
├── Cahier_des_Charges_Qwen3-ASR.pdf
├── Guide_Socle_Django_Qwen3-ASR.pdf
├── generate_cahier_des_charges.py   ← génère le cahier des charges PDF
├── docker/
│   └── Dockerfile-qwen3-asr-cu128   ← image Docker avec CUDA 12.8
├── examples/                        ← exemples d'utilisation
│   ├── example_qwen3_asr_transformers.py
│   ├── example_qwen3_asr_vllm.py
│   ├── example_qwen3_asr_vllm_streaming.py
│   └── example_qwen3_forced_aligner.py
├── finetuning/
│   ├── README.md
│   └── qwen3_asr_sft.py             ← fine-tuning SFT du modèle
├── qwen_asr/                        ← package Python du modèle
│   ├── __init__.py / __main__.py
│   ├── cli/
│   │   ├── demo.py / demo_streaming.py / serve.py
│   ├── core/
│   │   ├── transformers_backend/    ← backend HF Transformers
│   │   │   ├── configuration_qwen3_asr.py
│   │   │   ├── modeling_qwen3_asr.py
│   │   │   └── processing_qwen3_asr.py
│   │   └── vllm_backend/            ← backend vLLM
│   │       └── qwen3_asr.py
│   ├── inference/
│   │   ├── qwen3_asr.py             ← inférence principale
│   │   ├── qwen3_forced_aligner.py  ← alignement temporel (timestamps)
│   │   ├── utils.py
│   │   └── assets/korean_dict_jieba.dict
├── webapp/                          ← APPLICATION WEB DJANGO « Scribe »
│   ├── manage.py
│   ├── db.sqlite3                   ← base de données (jobs, transcriptions)
│   ├── upload_all.py                ← script d'upload batch
│   ├── dash_check.html / dash_new.html
│   ├── qwenweb/                     ← configuration projet Django
│   │   ├── settings.py              ← QWEN_MODEL_ID, QWEN_DEVICE, ports…
│   │   ├── urls.py / wsgi.py / asgi.py
│   ├── transcriptions/              ← application Django principale
│   │   ├── models.py                ← TranscriptionJob
│   │   ├── views.py                 ← vues HTML + API JSON
│   │   ├── urls.py                  ← routage
│   │   ├── admin.py / apps.py
│   │   ├── qwen_service.py          ← pont Django <-> qwen_asr
│   │   ├── upload_validation.py     ← validation des fichiers audio
│   │   ├── tests.py
│   │   ├── migrations/              ← 0001, 0002, 0003
│   │   └── management/commands/run_worker.py   ← le worker
│   ├── templates/transcriptions/    ← HTML (Bootstrap sombre)
│   │   ├── base.html / dashboard.html / upload.html
│   │   ├── job_list.html / job_detail.html
│   │   └── correction.html / corrections.html
│   └── static/js/chart.umd.min.js   ← Chart.js (graphiques du dashboard)
└── .venv/                           ← environnement virtuel (hors git)
```

## 6. Pages et API

| URL | Rôle |
|-----|------|
| `/` | Dashboard (stats + graphiques Chart.js) |
| `/upload/` | Nouvelle transcription |
| `/jobs/` | Historique des transcriptions |
| `/jobs/<id>/` | Détail + exports TXT / JSON / SRT |
| `POST /jobs/create/` | API — création d'un job (multipart, champ `audio_file`) |
| `GET /api/status/<id>/` | API — statut d'un job |
| `GET /api/stats/` | API — statistiques globales |

## 7. Paramètres clés (webapp/qwenweb/settings.py)

- `QWEN_MODEL_ID` → `Qwen/Qwen3-ASR-0.6B`
- `QWEN_DEVICE` → `cuda` (GPU) / `cpu`
- `QWEN_FORCE_ALIGN` → True = timestamps mot par mot (plus lent)
- `QWEN_MAX_NEW_TOKENS` → 1024

## 8. Pour relancer la prochaine fois (rappel)

```bash
cd "C:/Users/elodi/Desktop/Stage/Outil Speech to text/Qwen3-ASR/webapp"
../.venv/Scripts/python.exe manage.py runserver 0.0.0.0:8002 --noreload   # Terminal 1
../.venv/Scripts/python.exe manage.py run_worker                           # Terminal 2
```

## 9. Remarques

- Les deux processus tournent actuellement en arrière-plan (PID serveur 15668, PID worker 25276).
- Le worker ne charge le modèle sur le GPU qu'au **premier job** soumis.
- Aucune modification du code n'a été nécessaire pendant cette session : simple relance.