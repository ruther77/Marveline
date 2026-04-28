# Index Modules — Roadmaps L1→L5

> Mis à jour le 2026-02-25 | Audit approfondi complet 14/14 modules — 109 tâches identifiées
> Format : audit anti-patterns + tâches par priorité, prêt à implémenter

---

## Vue d'ensemble — État audit

| # | Module | Fichier | P0 | P1 | P2 | Total | Statut |
|---|--------|---------|----|----|----|----|-------|
| 01 | Catalogue | [01-catalogue.md](./01-catalogue.md) | 1 | 4 | 5 | 10 | ⚠️ tâches ouvertes |
| 02 | Clients | [02-clients.md](./02-clients.md) | 0 | 3 | 3 | 6 | ⚠️ tâches ouvertes |
| 03 | Devis | [03-devis.md](./03-devis.md) | 1 | 4 | 3 | 8 | ⚠️ tâches ouvertes |
| 04 | Ventes | [04-ventes.md](./04-ventes.md) | 1 | 4 | 2 | 7 | ⚠️ tâches ouvertes |
| 05 | Factures & Avoirs | [05-factures.md](./05-factures.md) | 2 | 4 | 5 | 11 | ⚠️ tâches ouvertes |
| 06 | Réservations | [06-reservations.md](./06-reservations.md) | 2 | 5 | 3 | 10 | ⚠️ tâches ouvertes |
| 07 | Événements terrain | [07-evenements.md](./07-evenements.md) | 1 | 3 | 3 | 7 | ⚠️ tâches ouvertes |
| 08 | Opérations terrain | [08-operations.md](./08-operations.md) | 1 | 3 | 3 | 7 | ⚠️ tâches ouvertes |
| 09 | Planning | [09-planning.md](./09-planning.md) | 1 | 5 | 3 | 9 | ⚠️ tâches ouvertes |
| 10 | Stock & Inventaire | [10-stock-inventory.md](./10-stock-inventory.md) | 1 | 4 | 3 | 7 | ⚠️ tâches ouvertes |
| 11 | Dashboard & Finances | [11-dashboard-finances.md](./11-dashboard-finances.md) | 2 | 4 | 2 | 8 | ⚠️ tâches ouvertes |
| 12 | Administration | [12-admin.md](./12-admin.md) | 1 | 7 | 1 | 9 | ⚠️ tâches ouvertes |
| 13 | Auth & Profil | [13-auth-profile.md](./13-auth-profile.md) | 1 | 1 | 0 | 2 | ⚠️ tâches ouvertes |
| 14 | Tarification & Relances | [14-tarification-relances.md](./14-tarification-relances.md) | 0 | 5 | 3 | 8 | ⚠️ tâches ouvertes |
| — | **TOTAL** | | **15** | **56** | **38** | **109** | |

---

## Tâches P0 consolidées — Bloquantes

| Réf | Module | Problème |
|-----|--------|---------|
| TASK-CAT-01 | Catalogue | SubNav layout `_app/catalogue.tsx` absent |
| TASK-CLI-? | Clients | SubNav layout `_app/clients.tsx` (vérifier) |
| TASK-DEV-01 | Devis | SubNav layout `_app/devis.tsx` absent |
| TASK-VEN-01 | Ventes | SubNav layout `_app/ventes.tsx` absent |
| TASK-FAC-01 | Factures | SubNav layout `_app/factures.tsx` absent |
| TASK-RES-01 | Réservations | SubNav layout `_app/reservations.tsx` absent |
| TASK-EVN-01 | Événements | SubNav `routes/_app/evenements.tsx` est `<Outlet />` nu |
| TASK-OPS-01 | Opérations | SubNav `routes/_app/operations.tsx` est `<Outlet />` nu |
| TASK-PLN-01 | Planning | SubNav `routes/_app/planning.tsx` est `<Outlet />` nu |
| TASK-STK-01 | Stock | SubNav `routes/_app/stock.tsx` est `<Outlet />` nu |
| TASK-DASH-01 | Dashboard | Loader2 isLoading sur DashboardPage (skeleton requis) |
| TASK-DASH-02 | Dashboard | Loader2 isLoading sur FinancesPage (skeleton requis) |
| TASK-ADM-01 | Admin | `routes/_app/admin.tsx` absent → pas de SubNav sur 7 sous-pages |
| TASK-AUTH-01 | Auth/Profil | `routes/_app/profile.tsx` absent → pas de SubNav sur 3 sous-pages |

> **Pattern commun P0** : absence de layout parent `_app/<module>.tsx` avec SubNav.
> Présent dans 12 modules sur 14. Admin et Profil sont les cas les plus critiques
> (7 et 3 sous-pages sans navigation commune).

---

## Anti-patterns transverses (tous modules)

### 1. Spinner `isLoading` → Skeleton (P0/P1)

Remplacer partout `<Loader2>` ou texte `"Chargement…"` sur chargement initial de données.
Règle UI/UX PDF #3 : skeleton obligatoire sur toute liste/page L1.

Les fichiers concernés sont listés dans chaque fichier module.

### 2. Classes design system non définies (P2)

| Classe invalide | Remplacement | Modules concernés |
|----------------|--------------|-------------------|
| `text-body` | *(supprimer — héritage white)* | 01, 04, 07, 08, 11, 12, 14 |
| `text-accent` | `text-primary-400` ou `text-gold-400` | 07, 11, 12 |
| `text-muted` | `text-dark-400` | 07, 11, 12 |
| `text-muted2` | `text-dark-500` | 12 |
| `bg-dark-9002` | `bg-dark-800` | 11 (faute de frappe) |
| `bg-primary-50/40` | `bg-primary-500/10` | 11 (light dans dark) |

### 3. Filtres non persistés dans l'URL (P2)

Statut + recherche + pagination en `useState` local → perdus au retour depuis une fiche.
Solution : `validateSearch` TanStack Router. Modules concernés : 01, 02, 03, 04, 06, 07.

### 4. SwipeActions mobile absentes (P1/P2)

PDF règle #5 : swipe-right = action principale. Modules sans SwipeActions sur vue mobile :
07 (événements), 08 (opérations), 14 (relances) + voir fichiers individuels.

### 5. Pattern erreur mutation incorrect (P1)

`onError: () => setError('message hardcodé')` — doit être :
`onError: (err) => setError((err as {...})?.response?.data?.detail || 'fallback')`
Concerné : `TarificationPage.tsx:58,60` (TASK-TAR-04).

---

## Ordre d'exécution recommandé

### Sprint A — P0 SubNav layouts (tous modules)
Créer/modifier les fichiers `routes/_app/<module>.tsx` pour ajouter `<SubNav>` + `<Outlet />`.
Ordre suggéré : Admin → Profil → Devis → Ventes → Factures → autres.

### Sprint B — P0/P1 Skeletons (tous modules)
Remplacer `Loader2 isLoading` et textes `"Chargement…"` par des composants skeleton.
Ordre suggéré : par module, les tâches sont indépendantes entre modules.

### Sprint C — P1 Corrections fonctionnelles
- Pattern erreur onError (TASK-TAR-04)
- SwipeActions (TASK-EVN-04, TASK-OPS-*, etc.)
- Corrections spécifiques par module

### Sprint D — P2 Design system + UX
- Classes invalides (text-body, etc.)
- Filtres URL persistés
- Indicateurs de progression

---

## Légende

- ✅ Complet : aucune tâche ouverte
- ⚠️ Tâches ouvertes : voir fichier module
- P0 : layout absent ou crash visuel
- P1 : UX dégradée (spinner, classes invalides critiques)
- P2 : amélioration non bloquante

---

## Référence — Conventions

- Conventions code : `docs/conventions/INDEX.md`
- UI/UX rules : `memory/ui-ux.md`
- SubNav composant : `frontend/src/components/layout/SubNav.tsx`
- SwipeActions : `frontend/src/components/ui/SwipeActions.tsx`
- Pattern erreur mutation : `memory/gotchas.md` → `GOTCHA:FRONTEND:ERROR-PATTERN`
