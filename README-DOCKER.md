# Conteneur Docker « tout-en-un » pour lancer le widget Qwen3-ASR sur tous les OS

Ce dépôt contient maintenant un **Docker Compose multi-service (CPU)** prêt à l'emploi.

## Fichiers ajoutés

- `docker/Dockerfile.cpu` — Image CPU (PyTorch 2.8 CPU) installant le projet `[webapp,widget]` + Gunicorn/Whitenoise.
- `docker-compose.yml` — Services : `redis`, `web` (Django+Gunicorn sur 8000), `worker` (`run_worker` sur DB + Redis). Volume `hf_cache` pour le cache HuggingFace. Montage RW de `webapp/db.sqlite3` et `webapp/media/`.
- `.dockerignore` — Réduit le contexte de build.
- `.env.example` — Modèle de configuration à copier en `.env`.

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et démarré (Windows/macOS/Linux).
- Espace disque : ~4–6GB (image + cache modèles). Première exécution télécharge le(s) modèle(s) HuggingFace.

## Démarrage rapide

1. Copier l'environnement
   ```bash
   cp .env.example .env
   ```

2. Lancer tous les services
   ```bash
   docker compose up --build -d
   ```

3. Ouvrir l'application
   - Interface principale : [http://localhost:8000](http://localhost:8000)
   - Widget autonome : [http://localhost:8000/widget/](http://localhost:8000/widget/)
   - Démo intégration : [http://localhost:8000/widget/demo/](http://localhost:8000/widget/demo/)

4. Consulter les logs
   ```bash
   docker compose logs -f web
   docker compose logs -f worker
   docker compose logs -f redis
   ```

5. Arrêter / relancer
   ```bash
   docker compose down        # arrête tout
   docker compose up -d       # relance
   docker compose down -v     # arrête + supprime volumes (perd hf_cache)
   ```

## Configuration (`.env`)

| Variable | Défaut | Notes |
|---|---|---|
| `QWEN_DEVICE` | `cpu` | `cpu` par défaut pour cross-OS. Si GPU NVIDIA local, passer `cuda:0`. |
| `QWEN_ASR_MODEL` | `Qwen/Qwen3-ASR-0.6B` | Peut être changé vers une autre taille/variant (prend de l'espace). |
| `QWEN_FORCED_ALIGNER` | `Qwen/Qwen3-ForcedAligner-0.6B` | Vide `""` pour désactiver timestamps/SRT. |
| `QWEN_ALLOWED_HOSTS` | `*` | À restreindre en prod (liste séparée par virgules). |
| `QWEN_CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,...` | Ajouter vos domaines si exposé. |
| `HF_HOME` / `TRANSFORMERS_CACHE` | `/app/.cache/huggingface` | Persisté via volume `hf_cache`. |

> Le worker **doit** tourner : sans lui, les jobs restent bloqués à 12% (cf. `widget/WIDGET.md`).

## CORS / Widget tiers

Les endpoints `/widget/*` répondent `Access-Control-Allow-Origin: *` via `widget/middleware.py` (aucune dépendance externe). C'est OK pour usage local/réseau fermé. À restreindre avant mise en ligne publique.

## Données persistées

- `webapp/db.sqlite3` (monté en RW) — base de jobs/transcriptions.
- `webapp/media/` (monté en RW) — fichiers audio uploadés/traités.
- `hf_cache` (volume Docker) — modèles HuggingFace téléchargés (réutilisés entre rebuilds).

## GPU (optionnel, NVIDIA)

Le `docker-compose.yml` force `QWEN_DEVICE=cpu`. Pour utiliser CUDA sur l'hôte :

1. Installer [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
2. Dans `.env`, fixer `QWEN_DEVICE=cuda:0`.
3. Dans `docker-compose.yml`, ajouter `deploy.gpu` ou `runtime: nvidia` selon votre setup Docker. Ex. :
   ```yaml
   services:
     web:
       deploy:
         resources:
           reservations:
             devices:
               - driver: nvidia
                 count: 1
                 capabilities: [gpu]
   ```

Le `docker/Dockerfile.qwen3-asr-cu128` existant reste disponible pour un usage GPU dédié (non réutilisé ici : il est orienté inférence GPU uniquement, alors que ce setup vise un lancement cross-OS simple pour le widget+worker).

## Tests rapides

```bash
# Santé web
curl -I http://localhost:8000/

# Upload widget (test CORS pré-vol)
curl -i -X OPTIONS http://localhost:8000/widget/api/upload/ -H "Origin: https://example.com" -H "Access-Control-Request-Method: POST"
```

## Remarques

- Gunicorn timeout à 300s pour laisser le temps à l'ASR sur CPU (premiers appels peuvent être lents).
- `collectstatic` est exécuté au build.
- Le montage `db.sqlite3` suppose que le fichier existe localement (`touch webapp/db.sqlite3` s'il manque). Docker crée un dossier vide sinon — éviter ça.
- `whitenoise` est installé pour servir les statiques en prod-like.