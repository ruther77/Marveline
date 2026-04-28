# PRODUCTS MODULE — Roadmap alignement LAYER.html

> Source de vérité : `docs/LAYER.html`
> Principe : coller **identiquement** à chaque écran du LAYER, sans approximation.

---

## Gap Analysis — État actuel vs LAYER

| # | Écran LAYER | Route actuelle | État | Priorité |
|---|-------------|---------------|------|----------|
| 1 | `s-catalogue` — Discovery catalogue avec workflow strip | `/products` (CRUD admin) | ❌ À réécrire entièrement | P0 |
| 2 | `s-catalogue-produit` — Fiche produit riche | `/products/$id` (inexistant) | ❌ À créer | P0 |
| 3 | `s-catalogue-photos` — Galerie angles + docs | `/products/$id/photos` | ⚠️ Partiel | P1 |
| 4 | `s-catalogue-variantes` — Variantes par finition | `/products/$id/variants` | ⚠️ Partiel | P1 |
| 5 | `s-catalogue-etats` — États matériel (4 états) | `/products/$id/states` | ⚠️ Partiel | P1 |
| 6 | `s-catalogue-disponibilite` — Planner 7 jours | `/products/$id/availability` | ⚠️ Partiel | P1 |
| 7 | `s-catalogue-outils` — Hub options avancées (3 scénarios) | `/products/tools` | ❌ Structure différente | P1 |
| 8 | `s-catalogue-collections` — Grid 4 collections + filtres | `/products/collections` | ⚠️ Partiel | P1 |
| 9 | `s-catalogue-fournisseurs` — List fournisseurs + info grid | `/products/suppliers` | ⚠️ À aligner | P2 |
| 10 | `s-maintenance-produit` — Timeline + photos état | `/products/$id/maintenance` | ⚠️ À aligner | P2 |
| 11 | `s-catalogue-recherche` — Recherche avancée | `/products/search` | ❌ Manquant | P1 |
| 12 | `s-catalogue-packs` — Packs recommandés | `/products/bundles` | ⚠️ Partiel | P2 |
| 13 | `s-catalogue-builder` — Builder d'offre | `/products/builder` | ❌ Manquant | P2 |
| 14 | SubNav products | `/products` layout | ❌ 4 items → 13 items requis | P0 |

---

## Différences backend à noter

### `/products` (liste)
- Actuel : CRUD admin avec filtres simples
- LAYER : discovery catalogue avec filtres par catégorie (pills), grid catalogue (image, sku, prix/j, qty dispo)
- Backend OK : `GET /products` retourne bien `image_url`, `price_per_day_euros`, `available_quantity`, `stock_quantity`
- **Pas de changement backend requis** — endpoint existant suffit

### Fiche produit `$id`
- LAYER : hero section + info grid 4 (tarif/j, caution, état moyen, sortie min) + galerie rapide + section disponibilité + état du parc + retours
- Backend : `GET /products/{id}` existe, retourne `deposit_cents`, `min_quantity` — **OK**
- Section "état du parc" : `GET /inventory/products/{id}/stock` → champs `qty_available/damaged/in_repair/on_location/reserved/retired` — **OK**
- Section "retours" : endpoint `GET /inventory/movements?product_id=X` — **OK**

### Disponibilité
- LAYER : planner 7 jours avec compteurs par date, réservations impactantes
- Backend : `GET /reservations?product_id=X&from=...&to=...` à construire côté frontend
- **Potentiel gap** : pas d'endpoint `product availability calendar` dédié — à vérifier

### Fournisseurs
- LAYER : list fournisseurs avec lead time, MOQ, contrat status, info grid coût/délai
- Backend : endpoints `/suppliers` existent (voir `app/api/v1/endpoints/suppliers.py`)
- **Lien produit→fournisseur** : vérifier si `product_id` filtrable sur `/suppliers`

### Maintenance
- LAYER : timeline avec dot couleur (vert/orange/rouge), photos état, coût par intervention, countdown prochaine vérif
- Backend : `GET /products/{id}/maintenances` — OK
- **Countdown** : calculé frontend à partir de `next_check_date`

---

## Plan d'exécution — 5 Sprints

### Sprint 1 — SubNav + Layout (P0)
**Fichiers** : `src/routes/_app/products.tsx`

SubNav 13 items selon LAYER :
1. Catalogue → `/products`
2. Nouveau produit → `/products/create`
3. Catégories → `/products/categories`
4. Bundles → `/products/bundles`
5. Collections → `/products/collections`
6. Disponibilité → `/products/availability`
7. Fournisseurs → `/products/suppliers`
8. Formules → `/products/formulas`
9. Tarification → `/products/pricing`
10. Maintenance → `/products/maintenance`
11. Imports → `/products/import`
12. QR → `/products/qr`
13. Outils → `/products/tools`

→ **Regroupement par section** (dropdown ou tabs groupés selon le pattern du LAYER)

---

### Sprint 2 — Discovery Catalogue `/products` (P0)
**Fichiers** : `src/pages/products/ProductsPage.tsx`

**LAYER s-catalogue éléments** :
- Barre recherche clickable → `/products/search` (chip "Avancée")
- Workflow strip 3 étapes : Découvrir collections | Qualifier l'inventaire | Orchestrer la sélection
- Filtres pills catégories : Tout | Verrerie | Mobilier | Vaisselle | Textile | + Plus
- Grid 6 catalog-cards : image + nom + sku + prix/j + qty dispo + chip catégorie + badge stock faible
- Section "Parcours opérationnels" (3 rows) : Repérage | Qualification | Structuration
- Lien "Options avancées" → `/products/tools`

---

### Sprint 3 — Fiche Produit `$id` (P0)
**Fichiers** : `src/routes/_app/products/$id.tsx` (nouveau), `src/pages/products/ProductEditorPage.tsx`

**LAYER s-catalogue-produit éléments** :
- Hero : image + titre + ref + badge qty dispo
- Info grid 4 : Tarif/j | Caution | État moyen | Sortie min
- Galerie rapide 3 mini → lien "Voir tout" → `/products/$id/photos`
- Disponibilité 14j (3 rows OK/Prévu/Tension)
- Workflow strip retour 3 étapes : Collecter état | Tracer déplacements | Déclencher actions
- État du parc : info grid 4 (Bon état %, À contrôler, Endommagé, Retours inspectés)
- Liste déplacements/retours (journal)
- Section vérification avec checklist
- Buttons : "Ajouter à la proposition" | "Analyser la disponibilité" | "Options avancées"
- SubNav fiche : Éditeur | Photos | Variantes | Disponibilité | États | Maintenance | Audit

---

### Sprint 4 — Sous-pages fiche produit (P1)
**Fichiers** : ProductStatesPage, ProductPhotosPage, ProductAvailabilityCalendarPage, ProductVariantsPage

Alignement par rapport au LAYER :
- **s-catalogue-etats** : info grid 4 + filtres compact + list 4 états avec emplacement
- **s-catalogue-photos** : grid 6 angles + docs section + boutons upload/QR
- **s-catalogue-disponibilite** : planner 7 jours avec slots colorés + réservations impactantes
- **s-catalogue-variantes** : filtres (Toutes/Disponibles/Faible/Premium) + list variantes avec prix différentiel

---

### Sprint 5 — Pages globales & manquantes (P1-P2)
- **s-catalogue-outils** : hub 3 scénarios (Qualifier/Documenter/Construire) avec module cards
- **s-catalogue-collections** : grid + filtres Mariage/Entreprise/Outdoor
- **s-catalogue-fournisseurs** : list + info grid coût/délai
- **s-maintenance-produit** : timeline dot-colored + photos état + countdown
- **`/products/search`** : page recherche avancée (MANQUANTE — à créer)

---

## Ordre d'exécution immédiat

1. ✅ Ce fichier roadmap créé
2. → **Sprint 1** : `products.tsx` SubNav réécrit (13 items groupés)
3. → **Sprint 2** : `ProductsPage.tsx` discovery catalogue
4. → **Sprint 3** : Fiche produit `$id` layout + page
5. → **Sprint 4** : Sous-pages
6. → **Sprint 5** : Pages globales

---

*Dernière mise à jour : 2026-02-25*
