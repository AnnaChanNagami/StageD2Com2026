# Widget Qwen3-ASR — intégration

Bouton de transcription embarquable : enregistrement micro ou dépôt de fichier
audio, transcription par le serveur Qwen3-ASR, texte affiché dans un panneau
flottant. Le script est autonome (aucune dépendance, aucun build) et
s'intègre sur n'importe quel site tiers en deux lignes de HTML.

## Démarrage rapide

```bash
cd webapp
../.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8003 --noreload
# dans un second terminal — OBLIGATOIRE, sinon les jobs restent bloqués à 12 %
../.venv/Scripts/python.exe manage.py run_worker
```

Pages de test :
- `/widget/` — page autonome (thème marine/azur) avec le widget actif
- `/widget/demo/` — page « site tiers » qui montre l'intégration et liste les options

## Intégration sur un site tiers

Deux balises, n'importe où dans le `<body>` :

```html
<script>
  window.QWEN3ASR_WIDGET = {
    apiBase: "http://127.0.0.1:8003",   // origine du serveur ASR
    position: "bottom-right",
    accent: "#3a6fd8",
    title: "Transcription vocale"
  };
</script>
<script src="http://127.0.0.1:8003/static/widget/qwen3asr-widget.js"></script>
```

Si le script est chargé depuis le serveur ASR lui-même, `apiBase` est déduit
automatiquement de l'origine du `<script>` : la configuration devient facultative.

Fichier : `webapp/static/widget/qwen3asr-widget.js` (~26 Ko, IIFE, `use strict`).

## Options (`window.QWEN3ASR_WIDGET`)

| Option      | Défaut                | Rôle                                              |
|-------------|-----------------------|---------------------------------------------------|
| `apiBase`   | origine du script     | origine du serveur Django (requis si script hébergé ailleurs) |
| `position`  | `"bottom-right"`      | `bottom-left` \| `top-right` \| `top-left`        |
| `accent`    | `"#3a6fd8"`           | couleur principale (bouton, accents)              |
| `title`     | `"Transcription vocale"` | titre du panneau                                |
| `lang`      | `""`                  | langue forcée pour l'ASR (`"fr"`, `"en"`… ; vide = auto) |
| `timestamps`| `false`               | `true` = segments avec timestamps (SRT)           |
| `maxTokens` | —                     | limite de tokens générés (`max_new_tokens`)       |

Toutes les options sont facultatives sauf `apiBase` si le script est servi par
un autre domaine que le serveur ASR.

## Mécanisme

1. Le script injecte son CSS encapsulé (préfixe `qw3-`, `z-index` 2147483000)
   et crée un bouton flottant : **clic** = ouvrir le panneau, **appui long
   (600 ms)** = menu (Dashboard / Transcription / Historique).
2. Deux modes dans le panneau : enregistrement micro (MediaRecorder → WAV
   envoyé tel quel) ou dépôt de fichier (drag & drop accepté).
3. L'audio est envoyé en `multipart/form-data` à `POST /jobs/create/` (champ
   `audio_file`, plus `language`, `timestamps`, `max_new_tokens` si renseignés).
4. Le widget interroge `GET /api/status/<uuid>/` jusqu'à `completed`, puis
   affiche le texte (bouton **Copier**, métadonnées langue / nombre de mots).
5. Sans `apiBase`, un message d'erreur clair s'affiche dans le panneau.

Endpoints utilisés (déjà existants, inchangés) :

```
POST /jobs/create/            créer un job à partir d'un fichier audio
GET  /api/status/<job_id>/    état + texte transcrit
```

## CORS

Le middleware `webapp/qwenweb/middleware.py` (`CorsAllowAllMiddleware`, branché
dans `settings.py`) répond aux pré-vols `OPTIONS` et ajoute sur **toutes** les
réponses :

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-CSRFToken
Access-Control-Max-Age: 86400
```

Zéro dépendance externe (`django-cors-headers` non installé). Vérification :

```bash
curl -i -X OPTIONS http://127.0.0.1:8003/jobs/create/ \
  -H "Origin: https://site-tiers.example.com" \
  -H "Access-Control-Request-Method: POST"
```

## Points d'attention

- **Le worker doit tourner** : sans `manage.py run_worker`, le job reste
  bloqué à 12 % et le widget tourne indéfiniment sur « en cours… ».
- **API sans authentification** : le CORS allow-all expose la transcription à
  qui pointe le serveur. Acceptable en usage local / réseau fermé ; à
  restreindre (origines autorisées + jeton) avant toute mise en ligne publique.
- **Isolation CSS** : tous les éléments portent le préfixe `qw3-` et sont
  montés en `position: fixed` — pas de conflit avec le CSS hôte, mais le
  thème du panneau reste celui du widget (il ne reprend pas celui du site).
- **Micro** : l'accès `getUserMedia` nécessite HTTPS (ou `localhost`) sur le
  site hôte ; le dépôt de fichier fonctionne partout.
- Le texte transcrit reste consultable côté serveur dans l'historique
  (`/jobs/`) — le widget n'est qu'une surface d'entrée.

## Fichiers

```
webapp/static/widget/qwen3asr-widget.js        le widget (autonome)
webapp/qwenweb/middleware.py                   CORS allow-all
webapp/templates/transcriptions/widget.html     page autonome /widget/
webapp/templates/transcriptions/widget_demo.html démo d'intégration /widget/demo/
webapp/transcriptions/views.py                 vues widget_standalone + widget_demo
webapp/transcriptions/urls.py                  routes /widget/ et /widget/demo/
webapp/qwenweb/settings.py                     middleware branché
```
