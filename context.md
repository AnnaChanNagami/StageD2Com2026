# Context.md — Projet Scribe (Qwen3-ASR)

> Document destiné à un agent IA externe pour comprendre et travailler sur le projet Scribe.
> Dernière mise à jour : 16 septembre 2026.

---

## 1. Présentation

**Scribe** est une application web de transcription vocale (speech-to-text) développée dans le cadre d'un stage. Elle repose sur le modèle **Qwen3-ASR-0.6B** (Alibaba) via la bibliothèque Python `qwen_asr`. L'interface web est Django ; le front-end est en **TypeScript** (compilé en JS vanilla, chargé en module ES sans framework).

Fonctionnalités :
- Upload audio (drag & drop ou sélecteur) → envoi en POST multipart
- Transcription automatique par le worker (process séparé)
- Dashboard avec statistiques et graphiques Chart.js
- Liste des jobs avec statut en temps réel (polling)
- Page détail : texte complet, segments horodatés, comparaison (diff) éditeur/traducteur, exports TXT/JSON/SRT
- Page corrections : score WER/CER, éditeur segment par segment
- CLI TypeScript (`npm run cli`) pour interroger l'API depuis le terminal

---

## 2. Arborescence du projet

```
Qwen3-ASR/
├── .venv/                          # Environnement Python 3.11 (pip install django torch qwen_asr waitress ...)
├── .gitignore
├── SYNTHESE_CONVERSATION.md        # Synthèse historique du développement (jour 1)
├── context.md                      # ← Ce fichier
├── LISEZMOI-DEMARRAGE.txt          # Guide de démarrage (texte brut, à jour)
└── webapp/                         # CWD obligatoire pour toutes les commandes Django
    ├── manage.py                   # Point d'entrée Django
    ├── db.sqlite3                  # Base SQLite (données de transcription)
    ├── serve.py                    # Serveur production : waitress + fallback statique (port 8002)
    ├── media/                      # Fichiers audio uploadés (MEDIA_ROOT)
    │   └── scribe/
    │       └── jobs/<uuid>/
    ├── static/
    │   ├── js/chart.umd.min.js     # Chart.js (vendored)
    │   └── ts/                     # Modules TS compilés (output du tsc)
    │       ├── main.js             # Point d'entrée frontend
    │       ├── api.js              # Client API typé
    │       ├── dashboard.js        # Graphiques dashboard
    │       ├── jobDetail.js        # Page détail (polling, diff, Chart)
    │       ├── upload.js           # Upload drag & drop
    │       ├── corrections.js      # Graphiques WER/CER
    │       ├── correction.js       # Éditeur segment par segment
    │       ├── diff.js             # Moteur de diff (word/char/line)
    │       └── *.d.ts              # Déclarations de types
    ├── templates/transcriptions/   # Templates Django (Jinja2/DTL)
    │   ├── base.html               # Layout principal (sidebar + nav)
    │   ├── dashboard.html          # Dashboard stats + chart
    │   ├── upload.html             # Page d'upload
    │   ├── job_list.html           # Liste des jobs
    │   ├── job_detail.html         # Détail d'un job (texte + segments + diff)
    │   ├── corrections.html        # Vue globale WER/CER
    │   └── correction.html         # Éditeur par segment
    ├── qwenweb/                    # Package Django (settings, urls root)
    │   ├── settings.py
    │   └── urls.py
    └── transcriptions/             # App Django principale
        ├── __init__.py
        ├── models.py               # Modèle TranscriptionJob
        ├── views.py                # Vues HTML + API JSON (600+ lignes)
        ├── urls.py                 # Routes
        ├── qwen_service.py         # Pont Django ↔ bibliothèque qwen_asr
        ├── admin.py
        ├── apps.py
        ├── forms.py
        ├── migrations/
        │   └── 0001_initial.py
        ├── management/
        │   └── commands/
        │       └── run_worker.py   # Commande worker (process séparé)
        └── tests.py                # 37 tests (tous OK)
```

---

## 3. Configuration

Fichier : `webapp/qwenweb/settings.py`

| Clé | Valeur par défaut | Description |
|---|---|---|
| `QWEN_ASR_MODEL` | `"Qwen/Qwen3-ASR-0.6B"` | Identifiant du modèle |
| `QWEN_DEVICE` | `"cuda"` | `"cuda"` (GPU) ou `"cpu"` |
| `QWEN_DTYPE` | `"bfloat16"` | Type des poids du modèle |
| `QWEN_MAX_NEW_TOKENS` | `1024` | Limite de tokens générés |
| `QWEN_FORCED_ALIGNER` | `"whisper-large-v3-turbo"` | Aligneur pour timestamps (optionnel) |
| `QWEN_BATCH_SIZE` | `16` | Taille de batch d'inférence |
| `PORT` | `8002` | Port du serveur |
| `DJANGO_DEBUG` | `True` | Mode debug |
| `MEDIA_ROOT` | `<webapp>/media` | Dossier d'upload |
| `STATICFILES_DIRS` | `["<webapp>/static"]` | Fichiers statiques |

---

## 4. Lancement (depuis `webapp/`)

```bash
# Terminal 1 — Serveur web (waitress, stable sous Windows)
cd "C:/Users/elodi/Desktop/Stage/Outil Speech to text/Qwen3-ASR/webapp"
winpty ../.venv/Scripts/python.exe serve.py 8002

# Terminal 2 — Worker de transcription (process séparé, tourne en boucle)
cd "C:/Users/elodi/Desktop/Stage/Outil Speech to text/Qwen3-ASR/webapp"
../.venv/Scripts/python.exe manage.py run_worker
```

**Important** : sous Windows avec bash MSYS (git-bash), `manage.py runserver` crash systématiquement (`tcsetattr: Inappropriate ioctl for device`, exit 139). La solution est d'utiliser **waitress** via `serve.py` + **winpty** pour fournir un TTY. Le process python se détache du bash et survit.

Pour arrêter le serveur : `taskkill /F /PID <pid>`

---

## 5. Modèle de données

Modèle : `TranscriptionJob` (fichier `transcriptions/models.py`)

| Champ | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Identifiant unique |
| `original_name` | CharField | Nom du fichier audio uploadé |
| `audio_file` | FileField | Chemin vers le fichier audio dans MEDIA_ROOT |
| `prompt` | TextField | Contexte / prompt optionnel pour guider la transcription |
| `language` | CharField | Langue demandée (ou vide = détection auto) |
| `language_detected` | CharField | Langue détectée par le modèle |
| `status` | CharField | `queued` / `running` / `completed` / `failed` |
| `progress` | FloatField | 0.0 → 1.0 |
| `stage` | CharField | Étape courante (loading_model, transcribing, aligning, parsing, done, error) |
| `error` | TextField | Message d'erreur si échec |
| `transcript_text` | TextField | Texte brut de la transcription |
| `segments_json` | JSONField | Segments horodatés (liste de dicts) |
| `segment_count` | IntegerField | Nombre de segments |
| `duration_sec` | FloatField | Durée de l'audio en secondes |
| `elapsed_sec` | FloatField | Temps de traitement |
| `processing_time` | FloatField | completed_at - created_at |
| `device` | CharField | GPU/CPU utilisé |
| `generated_tokens` | IntegerField | Nombre de tokens générés |
| `created_at` | DateTimeField | Date de création |
| `completed_at` | DateTimeField | Date de fin |
| `updated_at` | DateTimeField | Dernière modification |

Méthodes dérivées :
- `total_words()` → nombre de mots dans le texte transcrit
- `total_chars()` → nombre de caractères
- `to_dict()` → sérialisation complète pour l'API (inclut `total_words`, `total_chars`, `segment_count`)

---

## 6. API REST — Endpoints et shapes

### POST `/jobs/create/`
Crée un job + upload audio.
- Body : `multipart/form-data` avec champ `audio_file`, `prompt` (optionnel), `language` (optionnel)
- Réponse : `{ "id": "<uuid>", "status": "queued" }` (ou `{"error": "..."}`)
- Gère le CSRF via header `X-CSRFToken`

### GET `/api/jobs/?page=1&per_page=20&status=completed`
Liste paginée des jobs.
- Réponse : `{ "count": N, "total": N, "results": [...] }` où chaque élément est un objet avec les champs de `to_dict()`
- Filtres : `page`, `per_page`, `status`

### GET `/api/stats/`
Statistiques globales pour le dashboard.
- Réponse : `{
    "total": N, "completed": N, "failed": N, "running": N,
    "total_audio_sec": float, "total_process_sec": float,
    "total_words": int, "total_size_bytes": int,
    "jobs": [...]  // les 10 derniers jobs (pour le chart)
  }`

### GET `/api/status/<uuid:job_id>/`
Statut d'un job spécifique.
- Réponse : objet complet `to_dict()` du modèle (avec `total_words`, `total_chars`, `segment_count`, etc.)

### GET `/api/segments/<uuid:job_id>/`
Segments horodatés d'un job.
- Réponse : `[{"id": "seg_0001", "start": 0.0, "end": 2.5, "text": "..."}, ...]`

### POST `/jobs/<uuid>/delete-api/`
Supprime un job.
- Réponse : `{ "ok": true }`

### GET `/api/languages/`
Liste des langues supportées par le modèle.
- Réponse : `{ "languages": ["Chinese", "English", ...] }`

### GET `/api/runtime/`
Informations sur l'état du backend (modèle, device, dtype).
- Réponse : `{ "backend": "qwen3-asr (transformers)", "model": "...", "device": "...", "dtype": "...", "languages": 30, "forced_aligner": true }`

---

## 7. Frontend TypeScript

Le front-end est en **TypeScript**, compilé vers `webapp/static/ts/` en JS vanilla (pas de bundler, pas de framework). Les modules sont chargés en `type="module"` dans `base.html`.

### Architecture

```
webapp/frontend/
├── package.json          # scribe-frontend 1.0.0, "type": "module"
├── tsconfig.json         # ES2020, strict, rootDir=src, outDir=../static/ts
├── src/                  # Sources TS
│   ├── main.ts           # Point d'entrée, branche les init() selon la page
│   ├── api.ts            # Client API typé (fetch + CSRF)
│   ├── dashboard.ts      # Graphiques Chart.js (données via <script id="dashboardData">)
│   ├── jobDetail.ts      # Polling statut, Chart timestamps, comparaison diff
│   ├── upload.ts         # Drag & drop + création de job
│   ├── corrections.ts    # Chart WER/CER global
│   ├── correction.ts     # Éditeur segment par segment
│   └── diff.ts           # Moteur de diff (word/char/line)
└── backend/
    ├── cli.ts            # CLI TypeScript (stats/jobs/status/segments)
    └── tsconfig.json     # Config séparée CommonJS/ES2022 pour Node
```

### Données injectées dans les templates

Les données transitent par des balises `<script type="application/json">` avec des IDs :

| ID dans le HTML | Utilisé par | Contenu |
|---|---|---|
| `scribeJobData` | `jobDetail.ts` | Objet complet du job (to_dict) |
| `dashboardData` | `dashboard.ts` | Objet stats complet |
| `corrChartData` | `corrections.ts` | Données chart WER/CER |
| Attributs `data-*` | `upload.ts` | `data-api-create` (URL de création) |

Les init functions sont toutes appelées depuis `main.ts` : chaque module expose une `initXxx()` qui vérifie si l'élément attendu existe dans le DOM avant de s'exécuter (pattern guard).

### Compilation

```bash
cd webapp/frontend
npm run build          # tsc -p tsconfig.json
```

Les imports TS doivent inclure l'extension `.js` (le navigateur en mode ES module les exige) :
```ts
import { initJobDetail } from "./jobDetail.js";
```

---

## 8. CLI TypeScript

```bash
cd webapp/frontend
npm run cli -- stats
npm run cli -- jobs [limit]
npm run cli -- status <jobId>
npm run cli -- segments <jobId>
```

Utilise `node --experimental-strip-types` (Node 24 nativement supporte le TS). Serveur API sur `http://127.0.0.1:8002` (configurable via `SCRIBE_API_URL`).

---

## 9. Tests

```bash
cd webapp
../.venv/Scripts/python.exe manage.py test
```

37 tests couvrant :
- Modèle TranscriptionJob (CRUD, status, to_dict)
- Vues API (api_job_list, api_stats, api_job_status, api_job_segments)
- Vues HTML (dashboard, upload, job_list, job_detail, correction, corrections)
- Service qwen_service (exports SRT/JSON, calcul durée)
- Commande run_worker

---

## 10. Pièges connus / Notes importantes

1. **Crash bash MSYS** : `manage.py runserver` crash systématiquement sous git-bash (tcsetattr segfault). Solution : `winpty serve.py 8002` (waitress).

2. **Imports TS sans extension** : les imports `from "./jobDetail"` (sans `.js`) provoquent des 404 dans le navigateur ES module. Toujours écrire `from "./jobDetail.js"` dans les sources TS.

3. **`total_words` / `total_chars` sont des méthodes** : ils ne sont pas inclus automatiquement dans `to_dict()`. Ils sont explicitement ajoutés dans la méthode.

4. **Segments** : si le forced aligner ne retourne pas de timestamps, un seul segment couvrant tout le texte est créé (`seg_0001`).

5. **Worker séparé** : le worker (`manage.py run_worker`) doit tourner en process séparé. Il charge le modèle au premier job (timeout de 300s).

6. **SQLite** : base `webapp/db.sqlite3`. Les données disparaissent si le fichier est supprimé.

7. **Node 24** : le CLI utilise `--experimental-strip-types` (disponible en Node 24+). Pas besoin de tsx ou ts-node.

---

## 11. Synthèse de la conversation de développement

Voir `SYNTHESE_CONVERSATION.md` pour l'historique détaillé du développement (jour 1, 16 septembre 2026). Résumé :
- Création du projet Django + modèle `qwen_asr`
- Templates Bootstrap dark theme
- Extract TS complet du JS inline (7 modules)
- CLI TypeScript pour interroger l'API
- Résolution des bugs (extensions .js, crash MSYS, API shapes)

---

*Fin du context.md*
