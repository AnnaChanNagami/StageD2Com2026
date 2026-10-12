# Guide — Suivi des bugs

## Créer un nouveau bug

1. Copier le modèle : `docs/templates/bug-report.md`
2. Créer `docs/bugs/BUG-XXX.md` (dossier à créer) **OU** coller directement dans une nouvelle section de `docs/BUGS.md` (plus simple).
   - Méthode recommandée (historique propre) : créer `docs/bugs/` et un fichier par bug.

3. Incrémenter l'ID : chercher le dernier `BUG-XXX` dans `docs/BUGS.md` (colonne ID) et +1.
4. Remplir **Étapes pour reproduire**, **Attendu** et **Observé** (obligatoires). Sans reproduction, le bug reste `nouveau`.
5. Ajouter une ligne dans `docs/BUGS.md` → tableau `Bugs ouverts`.

## Mettre à jour un bug

1. Changer le **Statut** dans la fiche + dans le tableau (`BUGS.md`).
2. Quand reproduit : passer `nouveau` → `confirmé`.
3. En correction : `confirmé` → `en-cours`.
4. Après correctif/test : `en-cours` → `à-tester` → `corrigé`.
5. Fermeture : déplacer la ligne vers `Bugs fermés`, renseigner `Commit/PR` + `Date fermeture` + compléter `Résolution`.

## Bonnes pratiques

- **Un seul bug par fiche**. Si plusieurs problèmes distincts → plusieurs fiches + lier (`Lié à`).
- **Être factuel** : décrire ce qui se passe, pas d'interprétations non vérifiées.
- **Fournir des preuves** : commandes `curl`, réponses HTTP (codes + corps tronqué), stacktrace, chemins `fichier.py:Ligne`.
- **Ne jamais inclure de secrets/tokens**. Utiliser `[REDACTED]`.
- **Prioriser par gravité + impact** : `critique` en premier.
- **Fermer uniquement quand vérifié** (tests manuels + éventuellement automatisés).

## Workflow rapide

```text
Remontée (nouveau)
→ Reproduction/confirmation (confirmé)
→ Correction (en-cours)
→ Test (à-tester)
→ Corrigé + vérifié (corrigé/fermé)
```

## Dossier par bug (recommandé)

Créer le dossier :

```bash
mkdir -p "docs/bugs"
```

Nom de fichier : `BUG-001-titre-court.md` (kebab-case, max 60 caractères).
