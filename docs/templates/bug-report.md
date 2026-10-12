# Modèle de fiche de bug

Copier ce fichier pour chaque nouveau bug et renommer : `BUG-XXX.md` (numérotation séquentielle).

## Informations générales

- **ID** : BUG-XXX
- **Titre** : (court, explicite)
- **Gravité** : `critique` | `haute` | `moyenne` | `basse`
- **Statut** : `nouveau`
- **Composant** : `webapp` | `widget` | `worker` | `API` | `UI` | `exports` | `CORS` | `autre`
- **Priorité** : `P0` | `P1` | `P2` | `P3`
- **Reproduit** : `Oui` | `Non` | `Inconnu`
- **Remonté par** : 
- **Assigné à** : 
- **Date de remontée** : YYYY-MM-DD
- **Date de fermeture prévue** : YYYY-MM-DD (facultatif)
- **Lié à** : (BUG-XXX, commit, test, issue externe...)

## Environnement

- **OS** : Windows 11
- **Navigateur** (si UI/widget) : Chrome/Firefox/Edge + version
- **Python** : 3.11/3.12/...
- **Django** : (version si utile)
- **Serveur** : `manage.py runserver 127.0.0.1:8009 --noreload`
- **Worker actif** : `Oui` | `Non`
- **Branche/commit** : `git rev-parse --short HEAD`
- **Fichiers modifiés localement** : (facultatif)

## Étapes pour reproduire

1. ...
2. ...
3. ...

## Comportement attendu

(ce qui *devrait* se produire)

## Comportement observé

(ce qui se *produit* réellement)

## Preuves (logs, requêtes, réponses)

```bash
# Commande curl/test utilisée
curl -i -X POST http://127.0.0.1:8009/jobs/create/ -F "audio_file=@test.wav"
```

```text
# Réponse/erreur observée (tronquer les secrets)
...
```

```text
# Trace Django/worker (stacktrace pertinente uniquement)
...
```

## Impact

(Décrire l'impact utilisateur/technique : données perdues, blocage, contournement possible ?)

## Contournement

(Si existe, décrire la solution temporaire)

## Cause probable

(Hypothèse technique : fichier/fonction/ligne)

## Fichiers concernés

- `webapp/transcriptions/views.py:XXX`
- `webapp/transcriptions/...`
- `widget/...`

## Tests à ajouter (critère d'acceptation)

- [ ] Test unitaire/reproduisant le bug
- [ ] Vérifie que le correctif résout le cas
- [ ] Vérifie qu'aucune régression (cas nominal)

## Résolution

- **Statut final** : `corrigé` | `fermé` | `wontfix` | `dupliqué`
- **Commit corrigé** : `abc1234`
- **Explication de la correction** : (court)
- **Date de fermeture** : YYYY-MM-DD
- **Vérifié par** : (tests manuels/automatisés)
