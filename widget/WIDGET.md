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

Fichier : `widget/static/widget/qwen3asr-widget.js` (~26 Ko, IIFE, `use strict`).

## Options (`window.QWEN3ASR_WIDGET`)

| Option      | Défaut                | Rôle                                              |
|-------------|-----------------------|---------------------------------------------------|
| `apiBase`   | origine du script     | origine du serveur Django (requis si script hébergé ailleurs) |
| `position`  | `"bottom-right"`      | `bottom-left` \| `top-right` \| `top-left`        |
| `accent`    | `"#3a6fd8"`           | couleur principale (bouton, accents)              |
| `title`     | `"Transcription vocale"` | titre du panneau                                |
| `lang`      | `""`                  | langue forcée pour l'ASR (`"fr"`, `"en"`… ; vide = auto) |
| `timestamps`| `false`               | `true` = segments avec timestamps (SRT)           |
|| `maxTokens` | —                     | limite de tokens générés (`max_new_tokens`)       ||
|| `history`   | `true`                 | `false` = masque l'historique (bouton + stockage)   ||
|| `historyMax`| `30`                   | nombre max de transcriptions conservées             ||
|| `download`  | `true`                 | `false` = masque le bouton de téléchargement        ||
|| `format`    | `\"txt\"`               | `\"txt\"` ou `\"json\"` — format du fichier exporté ||

Toutes les options sont facultatives sauf `apiBase` si le script est servi par
un autre domaine que le serveur ASR.

## Mécanisme

1. Le script injecte son CSS encapsulé (préfixe `qw3-`, `z-index` 2147483000)
   et crée un bouton flottant : **clic** = ouvrir le panneau, **appui long
   (600 ms)** = menu (Dashboard / Transcription / Historique).
2. Deux modes dans le panneau : enregistrement micro (MediaRecorder → WAV
   envoyé tel quel) ou dépôt de fichier (drag & drop accepté).
3. L'audio est envoyé en `multipart/form-data` à `POST /widget/api/upload/`
   (champ `audio_file`, plus `language`, `timestamps`, `max_new_tokens` si
   renseignés).
4. Le widget interroge `GET /widget/api/status/<uuid>/` jusqu'à `completed`,
   puis affiche le texte (bouton **Copier**, métadonnées langue / nombre de mots).
5. Sans `apiBase`, un message d'erreur clair s'affiche dans le panneau.

## Historique

Chaque transcription réussie **et** chaque échec sont ajoutés à un historique
conservé dans le `localStorage` du navigateur (clé `qw3asr.history.v1`).

- Bouton **Historique** (icône horloge) en bas du panneau : affiche la liste
  (nom du fichier, heure, aperçu du texte), la plus récente en premier.
- Un clic sur une entrée recharge le texte dans le panneau principal, avec les
  métadonnées d'origine (langue, durée) et le bouton **Copier** de nouveau actif.
- **Retour** ramène à la vue principale, **Tout effacer** vide l'historique.
- Les entrées sont dédupliquées par `job_id` ; au-delà de `historyMax`, les plus
  anciennes sont supprimées.

Deux points importants :

- **L'historique est local au navigateur**, il n'est jamais envoyé au serveur et
  n'est pas partagé entre deux postes. C'est un choix délibéré : le widget est
  servi en CORS ouvert, donc aucun endpoint « liste des transcriptions » n'est
  exposé, ce qui éviterait qu'une page tierce puisse lire les transcriptions des
  autres utilisateurs. Seuls le texte, le nom de fichier et la date sont stockés
  — jamais l'audio.
- Si le `localStorage` est indisponible (navigation privée, cookies tiers
  bloqués, iframe sandboxé), l'historique se désactive silencieusement : le widget
  reste pleinement fonctionnel, seul le bouton Historique n'a rien à afficher.

Endpoints utilisés (propres au widget, sous l'app `widget/`) :

```
POST /widget/api/upload/              créer un job à partir d'un fichier audio
GET  /widget/api/status/<job_id>/     état + texte transcrit
```

## CORS

Les endpoints `/widget/*` sont servis par le middleware dédié
`widget/middleware.py` (`WidgetCorsMiddleware`, branché dans `settings.py`) :
il répond aux pré-vols `OPTIONS` et ajoute sur **ces réponses uniquement**
(toute l'application principale reste sans CORS) :

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type, X-CSRFToken
Access-Control-Max-Age: 86400
```

Zéro dépendance externe (`django-cors-headers` non installé). Vérification :

```bash
curl -i -X OPTIONS http://127.0.0.1:8003/widget/api/upload/ \
  -H "Origin: https://site-tiers.example.com" \
  -H "Access-Control-Request-Method: POST"
```

## Téléchargement

Chaque transcription (récupérée depuis l'historique ou l'onglet courant) peut être
téléchargée en un clic, sans appel serveur :

- **Bouton global** dans le pied du panneau (icône flèche vers le bas) —
  télécharge la transcription en cours.
- **Bouton par entrée** dans la liste d'historique — télécharge cette transcription
  précise.
- Deux formats via l'option `format` :
  - `txt` (défaut) : texte brut + métadonnées (nom fichier, langue, mots, durée, date).
  - `json` : objet structuré (`text`, `file`, `language`, `words`, `elapsed`, `date`, `source`).
- Désactivation : `download: false` masque tous les boutons de téléchargement.

Le nom de fichier proposé dérive du nom du média d'origine (`lastFileName`) ou,
pour une entrée d'historique, de son champ `name`. Extension `.txt` ou `.json`
selon le format.

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
widget/                                  app Django autonome (racine du dépôt)
widget/static/widget/qwen3asr-widget.js  le widget (autonome)
widget/templates/widget/widget.html      page autonome /widget/
widget/templates/widget/widget_demo.html démo d'intégration /widget/demo/
widget/middleware.py                     CORS sur /widget/* uniquement
widget/views.py                          pages + ré-export API upload/status
widget/urls.py                           routes /widget/ et /widget/api/*
widget/WIDGET.md                         ce document
webapp/qwenweb/settings.py               app 'widget' branchée (installed/templates/static)
```
