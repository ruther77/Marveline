# UX Restaurant V2 — Plan de refonte

Date : 2026-04-14
Scope : App Restaurant (épicerie-restaurant CaroCorp)
Device cible : **Tablette horizontale + téléphone** (usage sur place)
Thème : **Amber clair conservé** (primary `#d97706`)

---

## 0. Contexte & décisions

- **Deux rôles traités en parallèle** : gérant (scope `restaurant:write`) et employé (scope `restaurant:read` seulement)
- **Usage terrain** : le gérant vérifie souvent sur place → même device que le staff, mais vues différentes
- **Priorité** : bugs backend + flows cross-modules avant la refonte visuelle pure
- **Règles de référence** :
  - `~/.claude/projects/-home-ruuuzer-Documents-FUTUR-PROJ/memory/ui-ux.md` (implémentation)
  - skill `ux-strategy` (psychologie produit Clea)

---

## 1. Phase 0 — Audit bugs & intégrations

### 1.1 Bugs backend à identifier

À exécuter avant toute refonte frontend :

```bash
# Tests restaurant
docker compose run --rm --entrypoint "" api python -m pytest tests/restaurant/ -v

# Vérifier cohérence des endpoints
grep -rn "raise HTTPException" app/api/v1/endpoints/restaurant/ | wc -l

# Chercher les N+1 potentiels
grep -rn "async for.*in session\|for.*in await" app/services/restaurant/
```

**Livrable** : liste des bugs P0/P1 → `docs/plans/UX_RESTAURANT_V2_BUGS.md`

### 1.2 Intégrations cross-modules identifiées

| Depuis → Vers | État | Flow |
|---------------|------|------|
| **Restaurant ↔ Épicerie** | ✅ Existe | Transferts stock Épicerie → Restaurant (`app/services/epicerie/transfert.py`) — sens unique |
| **Restaurant → Loyalty** | ⚠️ Partiel | Page publique `/fidelite/rejoindre` pour programme #1, mais **aucun usage staff pour créditer points après vente** |
| **Restaurant → Finance** | ❌ Manquant | Les ventes restaurant ne créent pas de `FinanceInvoice`. À vérifier si voulu ou non |
| **Restaurant → Catalogue** | ❌ Absent | Les ingrédients restaurant sont indépendants du catalogue produits alimentaire — duplication possible |

### 1.3 Décisions actées (2026-04-14)

1. **Fidélité** : ✅ Scan QR client à la clôture → crédit points automatique
2. **Finance** : ✅ 1 invoice par ticket **+** agrégat journalier (les deux coexistent)
3. **Catalogue** : ✅ Unifier `catalogue_produits` et `restaurant_ingredients` en une table commune

### 1.4 Implications des décisions

#### D1 — Fidélité checkout
- **Backend** : endpoint existe déjà (`POST /loyalty/ledger/accrue`). Besoin de wiring côté flow clôture.
- **Frontend** : intégrer `<LoyaltyScanner>` (existe) dans modal encaissement
- **UX** : bouton "Scanner fidélité" optionnel avant "Encaisser". Si scan → toast "+X points 🎉"
- **Enjeu** : ne pas bloquer la clôture si le client refuse/n'a pas de carte

#### D2 — Double facturation ticket + agrégat
- **Nouveau modèle** : `finance_invoices.invoice_type` = `RESTAURANT_TICKET` | `RESTAURANT_DAILY_AGGREGATE` | etc.
- **Per ticket** : créé à la clôture d'une commande → `FinanceInvoice` immédiate (tenant=2, type=RESTAURANT_TICKET)
- **Agrégat journalier** : job Celery à 23:59 qui crée 1 `FinanceInvoice` type=RESTAURANT_DAILY_AGGREGATE avec lignes = tous les tickets du jour
- **Relation** : les tickets individuels gardent un FK optionnel vers l'agrégat journalier (`parent_invoice_id`)
- **UX gérant** : dashboard montre les 2 vues (ticket par ticket + résumé du jour)
- **Migration** : nouvelle colonne `parent_invoice_id` nullable sur `finance_invoices`

#### D3 — Unification catalogue (BIG migration)
- **Principe** : une seule table `catalogue_produits` avec une colonne `domaine` ou `scope` (ARRAY : ['epicerie', 'restaurant'])
- **Étapes** :
  1. Alembic migration : `catalogue_produits.domaines ARRAY[] DEFAULT '[epicerie]'`
  2. Data migration : créer entrées catalogue pour chaque `restaurant_ingredient` existant
  3. `restaurant_ingredients.catalogue_produit_id` FK vers `catalogue_produits.id`
  4. Les recettes continuent de référencer `restaurant_ingredients` (qui devient une vue/shim)
  5. Long terme : migration progressive des endpoints, puis suppression de la table dédupliquée
- **Risque** : cette migration touche l'ETL Épicerie ET le stock Restaurant. **À faire APRÈS** les phases UX pour éviter chevauchement.
- **Phase dédiée** : Phase 5bis — Unification catalogue (3-5j à part, hors phases UX)

---

## 2. Phase 1 — Fondations rôles (1-2 jours)

### 2.1 Hook `useRestaurantScopes`

```tsx
// frontend/apps/restaurant/src/hooks/useRestaurantScopes.ts
export function useRestaurantScopes() {
  const { user } = useMassaCorpAuthStore()
  const scopes = new Set(user?.scopes ?? [])
  return {
    canRead: scopes.has('restaurant:read'),
    canEdit: scopes.has('restaurant:write'),
    isManager: scopes.has('restaurant:write'),
    isStaff: scopes.has('restaurant:read') && !scopes.has('restaurant:write'),
  }
}
```

### 2.2 Composant gardien `<RequireScope>`

```tsx
<RequireScope scope="restaurant:write" fallback={null}>
  <AjouterPlatButton />
</RequireScope>

// Ou avec fallback visuel :
<RequireScope scope="restaurant:write" fallback={<ReadOnlyBadge />}>
  <EditIngredientForm />
</RequireScope>
```

### 2.3 Landing conditionnelle

- Staff → redirect `/salle` (vue opérationnelle immédiate)
- Gérant → redirect `/dashboard` (KPI business)
- Pattern : `/dashboard.tsx` fait le routing dans `beforeLoad`

### 2.4 Backend : exposer scopes dans `/auth/v2/me`

Vérifier que `GET /auth/v2/me` retourne bien `scopes: ["restaurant:read", ...]`. Sinon, l'ajouter.

---

## 3. Phase 2 — Navigation adaptative (1 jour)

### 3.1 Bottom nav tactile téléphone (4 items)

```
Staff service :  [Salle] [Cuisine] [Stock] [···]
Staff cuisine :  [Cuisine] [Bar] [Stock] [···]
Gérant       :  [Dashboard] [Salle] [Cuisine] [···]
```

Drawer `···` : reste de la nav filtrée par scope.

### 3.2 Sidebar tablette horizontale / desktop

**Opérations** (tous) :
- Salle, Cuisine, Bar, Stock

**Gestion** (scope `restaurant:write` uniquement) :
- Dashboard, Carte, Catalogue, Préparations, Historique

### 3.3 Retirer les role-tabs dupliqués

Actuellement `SallePage.tsx` et `CuisinePage.tsx` réaffichent en interne `[Salle, Cuisine, Stock, Menu]` — redondance avec la sidebar. **Supprimer**.

---

## 4. Phase 3 — Service (tactile, priorité haute) — 3-5 jours

### 4.1 SallePage — grille tactile optimisée

**Taille tactile minimum 44×44** (règle `ui-ux.md` §V). Actuellement les boutons modal sont à 40×40.

**Layout tablette horizontale** :
```
┌────────────────────────────────────────────────────┐
│ 🏠 Restaurant   🔔 3 alertes    👤 Jean  [Déconn] │
├──────────┬─────────────────────────────────────────┤
│          │ Filtre : [Tout] [Libre] [Occupé] [⚠]  │
│          ├─────────────────────────────────────────┤
│ Sidebar  │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐  │
│ 220px    │ │  T1  │ │  T2  │ │  T3  │ │  T4  │  │
│          │ │  ●   │ │  ●   │ │  ●   │ │  ●   │  │
│          │ │ 4 c. │ │ 2 c. │ │Libre │ │Libre │  │
│          │ └──────┘ └──────┘ └──────┘ └──────┘  │
│          │                                        │
│          │ [+ Emporter]                          │
└──────────┴─────────────────────────────────────────┘
```

**Tables tactiles** : 120×120px (tablette) ou 96×96px (téléphone)
- **Dot status** (jamais couleur seule — ajouter numéro couverts texte) :
  - 🟢 Libre
  - 🟠 Commandée (+ temps écoulé)
  - 🔵 Servie (+ temps depuis service)
  - 🔴 À encaisser (clignotement discret)
- **Tap court** → ouvrir commande
- **Tap long** → menu actions (transférer, annuler, paramètres table)
- **Swipe droite** sur table occupée → fiche ticket direct
- **Swipe gauche** → encaisser

**Modal ouverture commande** :
- Fullscreen sur téléphone (pas centré-popup)
- Bottom sheet sur tablette
- Boutons 1-6 couverts → 48×48px minimum, espacés 12px

### 4.2 CuisinePage — Kitchen Display System (KDS)

**Vue Kanban tablette horizontale** :
```
┌─ Reçues (3) ─┐ ┌─ Préparation (2) ─┐ ┌─ Prêtes (1) ─┐
│              │ │                   │ │              │
│ T3 ────────  │ │ T1 ────────       │ │ T2 ────────  │
│ 2 entrées    │ │ 3 plats    ⏱5:30  │ │ 1 dessert    │
│ ⏱2:10   🟢   │ │            🟠     │ │        🔴    │
│ [Commencer]  │ │ [Prête]           │ │ [Servie]     │
│              │ │                   │ │              │
└──────────────┘ └───────────────────┘ └──────────────┘
```

**Points clés** :
- **Buzzer auto** si carte > 15min (sonore + flash rouge)
- **Drag-and-drop** entre colonnes OU boutons action (tablette = drag, téléphone = boutons)
- **Couleur + minuteur + icône** (règle `ui-ux.md` §VII — jamais couleur seule)
- **Filtre cuisine/bar** en toggle segmenté (pas de tabs page entière)
- **Mode plein écran** (⤢) sans sidebar pour le chef

### 4.3 PanelCommande — bottom sheet mobile

**Problème actuel** : modale fixe desktop.

**Cible** :
- **Téléphone** : bottom sheet glissable, drag handle visible
- **Tablette** : panneau latéral 40% largeur qui slide
- **Contenu** :
  - Tabs `[🍽 Plats] [🍹 Boissons] [📋 Menus]`
  - Grille d'icônes 4 col (mobile) / 6 col (tablette), 88×88px minimum
  - Badge quantité + qty controls (tap long = +1, double tap = saisie custom)
  - Total sticky + bouton Envoyer grosse taille (64px haut)

---

## 5. Phase 4 — Gestion (gérant, priorité moyenne) — 2-3 jours

### 5.1 Dashboard hub-cards

**Hero KPI** :
```
┌─────────────────────────────────────────┐
│  CA du jour                             │
│  1 247,80 €          ↑ +12% vs hier     │
│  ─────────────────────────────────────  │
│  63 couverts · 19,80 € ticket moyen     │
└─────────────────────────────────────────┘
```

**3 hub-cards** (tap = drill down) :
- 🔥 **Ruptures** (badge rouge si > 0) → `/stock?filter=ruptures`
- 🍲 **Marmites** (nb actives) → drawer live cuisine
- 📋 **Tables actives** (nb) → `/salle`

**Timeline activité** (5 derniers événements) en bas.

**Empty states actifs** (règle `ui-ux.md` §IV) :
- Pas de vente → "Aucune vente aujourd'hui. [Ouvrir une table]"
- Pas d'activité → "🍽️ Premier service ? Commencez par [Nouvelle table]"

### 5.2 IngredientsPage — split en composants

`IngredientsPage.tsx` = **1531 lignes** actuellement.

**Découpage cible** :
```
pages/stock/
  ├── StockPage.tsx           (~200 lignes, lecture par défaut)
  ├── IngredientsAdminPage.tsx (~200 lignes, CRUD gérant)
  └── components/
      ├── IngredientsList.tsx
      ├── IngredientRow.tsx
      ├── IngredientFormModal.tsx
      ├── IngredientDetailDrawer.tsx
      ├── AjusterStockModal.tsx
      └── CategorieSelector.tsx
```

### 5.3 Preparations & Catalogue (gérant only)

- Gardés dans la sidebar section "Gestion" (scope write uniquement)
- Staff : caché dans la nav, mais toujours accessible via URL directe → 403 page propre

---

## 6. Phase 5 — Intégrations cross-modules — 2-3 jours (selon décisions §1.3)

### 6.1 Fidélité au checkout

Quand une commande est clôturée/payée :
1. Proposer scan QR fidélité (bouton optionnel)
2. Si scanné → créditer points via `/loyalty/ledger/accrue`
3. Montrer toast "+12 points 🎉" (règle `ui-ux.md` §IV — célébration)

**Composant** : `<LoyaltyScanner>` existe déjà (`components/LoyaltyScanner.tsx`). À intégrer dans le flow encaissement.

### 6.2 Stock Restaurant ↔ Épicerie

**Problème actuel** : les transferts existent côté épicerie (`/epicerie/transferts`), mais aucune vue côté restaurant pour :
- Demander un transfert (staff)
- Accepter/valider une réception (gérant)

**Cible** :
- Dans StockPage restaurant : bouton "Demander à l'épicerie" (staff) qui crée une demande
- Dashboard gérant : alerte "2 demandes de transfert en attente"

### 6.3 Ventes → Finance (D2 acté : ticket + agrégat)

**Implémentation** :

1. **FinanceInvoice par ticket** (temps réel)
   - Trigger : `POST /restaurant/commandes/{id}/cloturer`
   - Service `create_ticket_invoice(commande_id)` :
     ```python
     invoice = FinanceInvoice(
         tenant_id=..., type="RESTAURANT_TICKET",
         invoice_number=f"TICKET-{date}-{seq}",
         lines=[...],
         montant_ht_cts=..., montant_ttc_cts=...,
     )
     ```
   - Numérotation séquentielle quotidienne : `TICKET-20260414-0001`

2. **Agrégat journalier** (batch)
   - Job Celery `create_daily_aggregate_invoice` à 23:59
   - Agrège tous les `RESTAURANT_TICKET` du jour → 1 `RESTAURANT_DAILY_AGGREGATE`
   - Les tickets enfants pointent vers l'agrégat via `parent_invoice_id`
   - Numérotation : `JOUR-20260414`

3. **Migration Alembic** :
   ```sql
   ALTER TABLE finance_invoices
     ADD COLUMN invoice_type VARCHAR(40) NOT NULL DEFAULT 'MANUAL',
     ADD COLUMN parent_invoice_id BIGINT REFERENCES finance_invoices(id) ON DELETE SET NULL;
   CREATE INDEX ix_finance_invoices_parent ON finance_invoices(parent_invoice_id) WHERE parent_invoice_id IS NOT NULL;
   CREATE INDEX ix_finance_invoices_type_date ON finance_invoices(invoice_type, date_facture);
   ```

4. **UX gérant — Dashboard finance**
   - Toggle `[Tickets détaillés] [Résumés journaliers]`
   - Lien "Voir tickets" depuis un agrégat

### 6.4 Unification catalogue (D3 acté, phase 5bis à part)

**Scope séparé** : cette migration touche Épicerie + Restaurant + ETL. Elle mérite sa propre phase de 3-5 jours, à faire **APRÈS** les Phases 3-4 UX pour ne pas mélanger les risques.

Voir section 1.4 "Implications D3" pour les étapes.

---

## 7. Phase 6 — Polish & cohérence — 2 jours

### 7.1 Unification thème amber clair

**Problème actuel** : mélange `bg-stone-*` (SallePage) et `bg-dark-*` (IngredientsPage = thème sombre).

**Cible** :
- Tout l'app Restaurant en **thème clair amber** (`#d97706`)
- `bg-stone-50` comme fond par défaut
- Remplacer tous les `bg-dark-*` → `bg-stone-*`

Script de migration :
```bash
# Preview
grep -rn "bg-dark-\|text-dark-\|border-dark-" frontend/apps/restaurant/src --include="*.tsx"
```

### 7.2 États obligatoires partout (règle `ui-ux.md` §IV)

| Page | Empty state à créer | Error state à améliorer |
|------|--------------------|--------------------------|
| Salle | "Aucune table configurée. [Paramètres]" | Perte réseau → "Reconnexion…" (pas "Erreur") |
| Cuisine | "🍳 Pas de commande. Profitez-en !" | Buzzer off → badge silencieux |
| Stock | "Ajoutez votre premier ingrédient" | Article inconnu → suggestion catalogue |
| Historique | "Premier service ? Vos tickets apparaîtront ici." | Filtre vide → réinitialiser |

### 7.3 Skeletons obligatoires

Règle `ui-ux.md` §XI : tout `isLoading` data = skeleton, jamais `<Loader2>` seul.

À vérifier sur chaque page.

### 7.4 Célébrations (règle `ux-strategy`)

- 1ère commande du jour → toast "Premier service lancé 🚀"
- Clôture journée avec +10% vs hier → toast "Record battu 📈"
- 100ème couvert → confettis discrets

### 7.5 Notifications in-app

- **Badge rouge** sur icône Cuisine (staff service) quand nouvelle commande à préparer
- **Badge orange** sur icône Salle (staff service) quand plat prêt
- **Drawer notifications** dans le header (cloche)

---

## 8. Matrice pages × rôles × actions

| Page | Route | Staff | Gérant | Notes |
|------|-------|-------|--------|-------|
| Dashboard | `/dashboard` | ❌ caché | ✅ landing | KPI + hub-cards |
| Salle | `/salle` | ✅ landing | ✅ | Tactile, swipe |
| Cuisine | `/cuisine` | ✅ | ✅ | KDS kanban |
| Bar | `/bar` | ✅ | ✅ | Vue filtrée boissons |
| Stock | `/stock` | 👁 lecture | ✅ CRUD | Dual mode |
| Historique | `/historique` | ✅ lecture tickets du jour | ✅ + export + filtres | |
| Carte | `/menu` | 👁 consultation | ✅ CRUD plats | |
| Catalogue | `/catalogue` | ❌ | ✅ | Gestion catalogue |
| Préparations | `/preparations` | ❌ | ✅ | Recettes |
| Ingrédients | `/ingredients` | ❌ | ✅ | CRUD ingrédients |

**Légende** : ✅ Accès complet · 👁 Lecture seule · ❌ Caché dans nav (403 si URL)

---

## 9. Composants à créer (design system)

```
frontend/apps/restaurant/src/components/
  ├── auth/
  │   ├── RequireScope.tsx          [new]
  │   └── ReadOnlyBadge.tsx         [new]
  ├── table/
  │   ├── TableCard.tsx             [refonte, tactile 44px+]
  │   ├── TableStatusDot.tsx        [new, dot + icon + texte]
  │   └── TableGrid.tsx             [refonte responsive]
  ├── commande/
  │   ├── PanelCommande.tsx         [refonte bottom sheet]
  │   ├── AjouterPlatModal.tsx      [existant, ajuster tactile]
  │   └── PlatQuickTile.tsx         [new, 88×88 tap + badge qty]
  ├── kds/
  │   ├── KdsKanbanColumn.tsx       [new]
  │   ├── KdsOrderCard.tsx          [new, timer + swipe]
  │   └── KdsFilterToggle.tsx       [new, segmented]
  ├── dashboard/
  │   ├── HubCard.tsx               [new, inspiré Marveline]
  │   ├── KpiHero.tsx               [new]
  │   └── ActivityTimeline.tsx      [new]
  └── shared/
      ├── EmptyState.tsx            [new, réutilisable]
      ├── BottomSheet.tsx           [new]
      └── LoyaltyScanner.tsx        [existant, à intégrer]
```

---

## 10. Planning d'exécution

| Phase | Durée | Dépendances | Livrable |
|-------|-------|-------------|----------|
| **0. Audit** | 0.5j | — | Liste bugs |
| **1. Fondations rôles** | 1-2j | Phase 0 | Hook + guard + landing |
| **2. Navigation** | 1j | Phase 1 | Nav adaptative live |
| **3. Service (tactile)** | 3-5j | Phase 2 | SallePage + KDS + Panel |
| **4. Gestion** | 2-3j | Phase 2 | Dashboard + split Ingredients |
| **5a. Loyalty checkout** | 1j | Phase 3 | Scan QR + crédit points |
| **5b. Stock ↔ Épicerie** | 1j | Phase 4 | Demandes transfert UI |
| **5c. Finance ticket+agrégat** | 2-3j | Phase 3 | Migration + service + job Celery |
| **5bis. Unification catalogue** | 3-5j | Phases 3-5c terminées | Migration + data + refactor |
| **6. Polish** | 2j | Phases 3-5 | Thème unifié + empty states + célébrations |

**Total estimé : 16-24 jours** (avec tests et itérations, phase 5bis incluse).

**Séquencement recommandé** :
1. Semaine 1 : Phases 0 → 1 → 2 (fondations + nav)
2. Semaine 2 : Phase 3 (service tactile)
3. Semaine 3 : Phase 4 + 5a + 5b (gestion + intégrations légères)
4. Semaine 4 : Phase 5c (finance ticket+agrégat) + Phase 6 (polish)
5. Semaine 5 : Phase 5bis (unification catalogue, si prêt stabilité)

---

## 11. Tests d'acceptation par rôle

### Staff service (scope `restaurant:read`)
- [ ] Connexion → arrive sur `/salle` directement
- [ ] Bottom nav affiche Salle, Cuisine, Stock, ···
- [ ] Dashboard/Catalogue/Préparations absents de la nav
- [ ] Tentative d'ajuster stock → 403 UI propre (pas popup brutal)
- [ ] Peut ouvrir une table, prendre commande, envoyer cuisine
- [ ] Voit les notifs cuisine/service (badges)

### Gérant (scope `restaurant:write`)
- [ ] Connexion → arrive sur `/dashboard`
- [ ] Voit toutes les sections (Opérations + Gestion)
- [ ] Peut faire CRUD ingrédients/recettes/plats
- [ ] Ajustements stock possibles
- [ ] Voit les alertes ruptures en badge dashboard

### Tablette horizontale
- [ ] Sidebar visible sans scroll
- [ ] Grille tables 4+ colonnes
- [ ] KDS kanban 3 colonnes visibles
- [ ] Modales en bottom sheet, pas popup

### Téléphone
- [ ] Bottom nav 4 items + thumb-zone OK
- [ ] Tables 2 colonnes, 96×96px
- [ ] Modales fullscreen
- [ ] Swipe actions sur listes

---

## 12. Ce qui n'est PAS dans ce plan (hors scope V2)

- App client final (commande en ligne, scan QR table pour autocommande)
- Intégration imprimante ticket (côté hardware)
- KDS son (buzzer audio) — nécessite webaudio + permissions
- Multi-site (plusieurs restaurants)
- Mode offline (PWA + sync) — déjà planifié séparément

---

## 13. Références

- `~/.claude/projects/-home-ruuuzer-Documents-FUTUR-PROJ/memory/ui-ux.md` — règles techniques
- Skill `ux-strategy` — psychologie produit Clea
- `docs/plans/UX_REDESIGN_MARVELINE_V2.md` — précédent exercice, patterns réutilisables
- `docs/plans/FC_RESTAURANT_*.md` — FC fonctionnelles existantes
- `app/core/permissions.py:358-359` — scopes restaurant
- `app/services/rbac.py:111-162` — mappings rôles → scopes
