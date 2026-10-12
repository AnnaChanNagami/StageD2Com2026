# Tests de cas limites — widget de transcription

## Fichier source

`widget/test_widget_edge_cases.py` — **28 tests**, 286 lignes.

L'app `widget/` (widget embarquable) n'avait **aucun test** avant cette suite. Le
fichier vit dans le paquet `widget/` à la racine du dépôt, aux côtés de
`views.py` / `urls.py`, et non sous `webapp/`.

Exécution ciblée :

```bash
./.venv/Scripts/python.exe -m pytest widget/test_widget_edge_cases.py -q
```

Le fichier est déclaré dans `testpaths` (`pyproject.toml`) avec un **basename
unique** : les deux autres modules de test du dépôt s'appellent `tests.py`, et
pytest lève `import file mismatch` sur des basenames dupliqués en mode
`prepend`. Le fichier est donc nommé `test_widget_edge_cases.py`.

## Convention de harness

Le projet utilise `django.test.TestCase` / `SimpleTestCase`, **pas** les
`@pytest.mark.django_db`. Les classes qui appellent `reverse()` doivent être en
`TestCase` et non `SimpleTestCase` : la résolution d'URL touche la base.

## Principe directeur

**Une erreur de validation renvoie un 4xx + un JSON contenant `error`, jamais 500.**

C'est le contrat que consomme `qwen3asr-widget.js` : le panneau affiche le champ
`error`, et un 500 lui fait afficher une page d'erreur technique au lieu du
message utile. L'utilitaire `_assert_rejected` formalise cette règle.

## Couverture

### `TestWidgetUploadCasseLimites` — 16 tests

Endpoint `POST /widget/api/upload/` (nom d'URL : `widget-upload`).

| Cas limite | Attendu |
|---|---|
| Extension non prise en charge (`.exe`) | refus 4xx, message `non prise en charge` |
| Fichier sans extension | refus 4xx |
| Extension en majuscules (`.WAV`) | accepté — symétrique de `.wav` |
| Aucun fichier dans le POST | refus 4xx, message `Aucun fichier audio` |
| Champ fichier mal nommé (`piece_jointe`) | refus 4xx **et** 0 job créé |
| `max_new_tokens` non numérique | pas de 500 (voir bug BUG-1) |
| `max_new_tokens` négatif | pas de 500 |
| `max_new_tokens` vide | repli sur le défaut `512` |
| WAV de 0 octet | job créé — la validation porte sur l'extension, le worker tranche |
| Nom unicode + espaces + guillemets | réponse JSON décodable |
| Nom de 900 caractères | stocké tronqué à 500 |
| Langue inconnue (`klingon`) | retombe sur l'auto-détection (`language == ""`) |
| Langue valide (`French`) | conservée telle quelle |
| Langue avec espaces (`"  French  "`) | normalisée |
| `timestamps` : `1`/`true`/`on` vs `0`/`""`/`oui` | booléens corrects — protège l'export SRT |
| `GET` sur l'upload | 405 |

### `TestWidgetStatusCasseLimites` — 6 tests

Endpoint `GET /widget/api/status/<uuid>/` (nom d'URL : `widget-status`), celui
que le widget interroge toutes les 2 s.

- Job inconnu → 404
- UUID malformé (`/pas-un-uuid/`) → 404, pas de 500
- `POST` sur le statut → 405
- La réponse expose bien `id`, `status`, `stage`, `progress`, `transcript_text`,
  `url` — un champ manquant afficherait `undefined` dans le panneau
- Job en erreur → `status == "failed"` et le message du modèle exposé
- `progress` toujours dans `[0, 100]` (voir bug BUG-2)

### `TestWidgetPages` — 2 tests

`/widget/` et `/widget/demo/` servent 200 et un HTML contenant
`qwen3asr-widget.js` ainsi que `window.QWEN3ASR_WIDGET`. Le widget ne place pas
ses endpoints dans le HTML : il déduit son `API_BASE` de l'origine de sa propre
balise `<script src>`.

### `TestWidgetInjectedPartout` — 4 tests

Le widget est le seul point d'entrée de transcription depuis la fusion : il doit
être injecté sur **toutes** les pages qui étendent `base.html`.

- Script présent sur `home`, `upload`, `dashboard`, `job_list`, `corrections`
- `timestamps: true` exposé globalement (sinon l'export SRT de la page de détail
  n'a plus de données)
- L'accueil ne poste plus vers `/jobs/create/` (ancien JS inline mort)
- `/upload/` ne contient plus de `<form>` — deux points d'entrée concurrents
  casseraient le widget (deux inputs file, deux boutons)

## Bugs trouvés et corrigés

Ces deux bugs sont de vrais défauts de production, découverts par les tests et
corrigés dans `webapp/transcriptions/views.py` — pas contournés dans les tests.

### BUG-1 — `max_new_tokens` non numérique → HTTP 500

`int(request.POST.get(...) or 512)` sans garde : une valeur non numérique
levait `ValueError` et renvoyait un 500.

Le chemin est réellement atteignable : `widget.js:459` recopie `CONFIG.maxTokens`
tel quel dans le POST, et cette valeur est fixée par la page qui intègre le
widget.

**Correctif** — helper `_coerce_positive_int(raw, default=512)` : repli sur le
défaut sur `TypeError`/`ValueError` ou valeur ≤ 0, plafond `8192` pour ne pas
saturer la mémoire du modèle.

### BUG-2 — `progress` renvoyé hors bornes

Le widget bornait la barre avec `Math.min(100, pct)` mais affichait le
pourcentage brut en texte. La valeur a été bornée **dans la vue**, puisque le
contrat 0–100 vaut pour tout client de l'API, pas seulement le widget.

## Vérification bout en bout

Contre le vrai serveur (`manage.py runserver 127.0.0.1:8001 --noreload`,
redémarré après la modification du code — un serveur `--noreload` garde l'ancien
code en mémoire) :

| Requête | Réponse |
|---|---|
| `max_new_tokens=beaucoup` | 201, `512` en base |
| `max_new_tokens=-1` | 201, `512` en base |
| `max_new_tokens=999999999` | 201, `8192` en base (plafond) |
| `/widget/api/status/pas-un-uuid/` | 404 |
| `/widget/api/status/00000000-...-000000000000/` | 404 |

## Non régression

**312 tests verts** (284 préexistants + 28 nouveaux), 0 échec, ~42 s.

```bash
cd "C:/Users/elodi/Desktop/Stage/Outil Speech to text/Qwen3-ASR bouton"
./.venv/Scripts/python.exe -m pytest -q
```

## Limites connues

- Le `input[type=file]` caché et l'envoi réel pilotés depuis un navigateur ne sont
  pas couverts : l'injection CDP dans un input caché n'est pas fiable. Le chemin
  serveur est validé (voir « Vérification bout en bout »).
- L'upload réel en navigateur reste à vérifier manuellement.