# Audit Modules Metier — V1

**Date** : 2026-04-02
**Methode** : Requetes API reelles + inspection DB
**Compte** : admin@carocorp.dev (tenant_admin, tenant 1)

---

## Donnees en base (snapshot)

| Table | Lignes | Usage |
|-------|--------|-------|
| stock_items | 38830 | Stock unitaire par produit/variante |
| audit_logs | 3565 | Audit trail |
| account_sessions | 367 | Sessions actives/passees |
| product_variants | 246 | Variantes produit |
| products | 184 | Catalogue produits |
| movement_item_units | 162 | Unites dans les mouvements |
| movement_items | 13 | Lignes de mouvement |
| reservation_lines | 10 | Lignes de reservation |
| invoices | 8 | Factures |
| inventory_movements | 5 | Mouvements (depart/retour) |
| reservations | 4 | Reservations |
| customers | 3 | Clients |
| devis | 3 | Devis |
| api_keys | 3 | Cles API |
| accounts | 5 | Comptes utilisateurs |

---

## 1. Catalogue Produits

### Etat

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /products` | 200 | 75 produits actifs, 184 en DB total |
| `GET /products/{id}` | 200 | Detail complet avec stock, prix, image |
| `GET /categories` | 200 | 20 categories |
| `GET /bundles` | 200 | 13 formules (bundles) |
| `GET /products/{id}/variants` | 200 | Variantes par produit (246 total) |
| `GET /collections` | 200 | 0 collections |

### Structure produit

```
Produit
├── id, name, sku, category
├── price_per_day_cents (ex: 20000 = 200 EUR/jour)
├── stock_quantity, available_quantity
├── condition (bon, neuf, use)
├── image_url
├── weight_grams, volume_cm3
└── Variantes[]
    ├── label (Standard, Elegance, ...)
    ├── sku, color, size, gamme
    └── price_per_day (override)
```

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **CAT-01** | P3 | `unit_price_cents` absent de la reponse list (`price_per_day_cents` est a la place). Nommage incoherent selon le contexte (list vs reservation line). |
| **CAT-02** | P3 | `collections` vide — module cree mais jamais utilise. |
| **CAT-03** | P3 | 184 produits en DB mais 75 en API — les 109 autres sont `is_active=false`. Pas de moyen de les voir sauf requete directe DB. |

---

## 2. Clients

### Etat

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /customers` | 200 | 26 clients (3 en DB avec donnees, 23 test/seed) |
| `GET /customers/{id}` | 200 | Detail complet |

### Structure client

```
Customer
├── id, customer_type (individual/company)
├── email, phone
├── first_name, last_name, company_name
├── address, city, postal_code, country
├── notes
└── display_name (computed)
```

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **CUS-01** | P3 | Pas de champ `siret` ou `vat_number` pour les clients pro. Necessaire pour la facturation B2B. |
| **CUS-02** | P3 | Pas d'historique client integre a la reponse (nb reservations, CA total). Le frontend doit appeler separement. |

---

## 3. Reservations

### Etat

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /reservations` | 200 | 4 reservations |
| `GET /reservations/{id}` | 200 | Detail complet avec lignes, client, produits inline |
| `GET /operations/summary` | 200 | 2 departs programmes, 0 retours |

### Structure reservation

```
Reservation
├── reference (RES-2026-XXXX)
├── status (draft, confirmed, pre_check, en_cours, completed, cancelled)
├── customer_id → Customer inline
├── devis_id (optionnel)
├── event_date, delivery_date, return_date
├── event_location, event_type, event_name, guest_count
├── total_amount_cents, deposit_amount_cents
├── advance_payment_amount_cents, balance_due_date
├── payment_status (unpaid/partial/paid)
├── delivery_* (zone, method, address, fee, carrier)
├── signature_url
├── lines[]
│   ├── product_id → Product inline
│   ├── variant_id → Variant inline
│   ├── bundle_id (optionnel)
│   ├── quantity, unit_price_cents, subtotal_cents
│   └── unit_price_euros, subtotal_euros (computed)
└── computed fields
    ├── rental_days
    ├── is_confirmed, is_cancelled
    ├── total_weight_kg, total_volume_liters
    └── invoice_status, invoice_number, paid_amount_cents
```

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **RES-01** | P2 | `payment_status` toujours "unpaid" meme quand les factures sont payees (reservation 1 a 2 factures payees mais `payment_status=unpaid`, `paid_amount_cents=0`). Desynchro entre invoices et reservation. |
| **RES-02** | P2 | `deposit_amount_cents` = 3x le `total_amount_cents` (ex: reservation 4 : total=4500c, deposit=13500c). Le deposit est 300% du total. Bug de calcul probable. |
| **RES-03** | P3 | `invoice_status=null` et `invoice_number=null` meme quand des factures existent. Champs jamais mis a jour. |
| **RES-04** | P3 | `signature_url=null` et `signed_at=null` sur les devis convertis. Pas de flow signature visible. |

---

## 4. Devis

### Etat

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /devis` | 200 | 3 devis (2 converted, 1 refused) |
| `GET /devis/{id}` | 200 | Detail avec lignes, phases, negotiations |

### Structure devis

```
Devis
├── reference (DEV-2026-XXXX)
├── status (draft, sent, converted, refused, expired)
├── customer_id, customer_name
├── event_date, delivery_date, return_date, event_location
├── subtotal_cents, tva_rate, tva_cents, total_cents
├── discount_pct
├── caution_amount_cents, caution_required
├── conditions_paiement, message_accompagnement
├── valid_until
├── signature_url, signed_at
├── converted_reservation_id
├── refusal_reason
├── lines[]
│   ├── product_id, variant_id, bundle_id
│   ├── quantity, unit_price_cents
│   └── tva_rate (par ligne)
├── phases[] (vide dans les donnees actuelles)
├── negotiations[] (vide)
├── change_requests[] (vide)
├── modules[] (vide)
└── allowed_actions[] (vide pour converted)
```

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **DEV-01** | P2 | `phases`, `negotiations`, `change_requests`, `modules` sont toujours des listes vides. Features implementees cote schema/API mais jamais utilisees dans le flow reel. Code mort ou flow incomplet. |
| **DEV-02** | P2 | `allowed_actions` est vide pour un devis "converted". Normal. Mais devrait-il proposer "dupliquer" ou "creer un nouveau" ? Pas de moyen de reutiliser un devis passe. |
| **DEV-03** | P3 | `signature_url` et `signed_at` toujours null, meme sur un devis converted. Le flow signature n'est pas branche. |
| **DEV-04** | P3 | `total_cents` absent de la reponse list (seulement dans le detail). Le frontend ne peut pas afficher le montant dans la liste sans faire N+1 requetes. |

---

## 5. Facturation — PROBLEME STRUCTUREL

### Etat actuel

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /invoices` | 200 | 8 factures (2 par reservation) |
| `GET /invoices/{id}` | 200 | Detail complet avec reservation, charges, payments inline |
| `GET /payments` | **404** | Route non montee |
| `GET /invoices/credit-notes` | **422** | Erreur validation |

### Modele actuel (incorrect)

```
1 Reservation → 2 Factures
├── Facture "advance" (acompte ~40%)
│   └── Paiement integre sur la facture (payment_method, payment_date)
└── Facture "balance" (solde ~60%)
    └── Paiement integre sur la facture
```

### Modele cible (confirme par l'utilisateur)

```
1 Reservation → 1 Facture (montant total)
                  └── N Paiements (table payments)
                       ├── Acompte (configurable, a la signature)
                       ├── Portion(s) intermediaire(s)
                       └── Solde (avant livraison)
```

### Problemes identifies

| # | Severite | Description |
|---|----------|-------------|
| **INV-01** | **P1** | **2 factures par reservation au lieu d'une.** Le service cree systematiquement advance + balance. Logique entiere a revoir. |
| **INV-02** | **P1** | **Table `payments` jamais utilisee.** 0 lignes. Le paiement est stocke sur la facture (`payment_method`, `payment_date`). Empeche les paiements partiels. |
| **INV-03** | P1 | **`GET /payments` → 404.** La route n'est pas montee dans le routeur API. Le frontend ne peut pas lister/creer des paiements. |
| **INV-04** | P2 | `invoice_type` (advance/balance) n'a plus de sens dans le modele cible. |
| **INV-05** | P2 | `advance_rate` hardcode a 0.4 depuis les settings tenant. Devrait etre configurable par devis. |
| **INV-06** | P2 | Avoirs (`credit-notes`) → erreur validation. Module commence mais non fonctionnel. |
| **INV-07** | P2 | `payment_method` et `payment_date` sur la table `invoices` sont redondants avec la table `payments`. A migrer. |

---

## 6. Mouvements Inventaire

### Etat

| Endpoint | HTTP | Donnees |
|----------|------|---------|
| `GET /inventory-movements` | 200 | 5 mouvements |
| `GET /inventory-movements/{id}` | 200 | Detail avec items |

### Structure

```
Mouvement
├── movement_type (departure/return)
├── status (scheduled/in_progress/completed)
├── reservation_id
├── scheduled_date, actual_date
├── handled_by_user_id
├── inspection_status, inspection_notes
├── delivery_method, delivery_address, delivery_notes
├── damage_fee, damage_fee_euros
└── items[]
    ├── product_id, quantity
    └── units[] (movement_item_units: 162 en DB)
```

### Observations

| # | Severite | Description |
|---|----------|-------------|
| **MOV-01** | P3 | `damage_types` table vide (0). Le module dommages est code mais aucun type configure. |
| **MOV-02** | P3 | `delivery_zones` vide (0). Calcul frais livraison non fonctionnel. |

---

## 7. Modules non fonctionnels (routes 404 ou vides)

| Module | Route | Status | DB | Commentaire |
|--------|-------|--------|-----|-------------|
| Pricing rules | `GET /pricing` | 404 | Table absente | Feature flag `pricing_engine` non active |
| Planning | `GET /planning` | 404 | — | Route non montee |
| Stock items | `GET /stock/items` | 404 | 38830 lignes en DB | Route existe sous un autre chemin ? |
| Loyalty | `GET /loyalty/programs` | 404 | Tables vides | Module code mais non branche |
| Payments | `GET /payments` | 404 | Table existe, 0 lignes | Route non montee |
| Notifications | `GET /notifications` | 200 | 0 | Module vide |
| Relances | `GET /relances` | 200 | 0 | Module vide |
| Evenements | `GET /evenements` | 200 | 0 | Module vide |
| Ventes | `GET /ventes` | 200 | 0 | Module vide |
| Collections | `GET /collections` | 200 | 0 | Module vide |
| Damage types | `GET /damage-types` | 200 | 0 | Non configure |
| Delivery zones | `GET /delivery-zones` | 200 | 0 | Non configure |
| Formulas | `GET /formulas` | 200 | 0 | Non configure |

---

## 8. Desynchros reservation ↔ facture

Test sur reservation 1 (completed, 2 factures payees) :

| Champ reservation | Valeur | Attendu | Bug ? |
|-------------------|--------|---------|-------|
| `payment_status` | `unpaid` | `paid` | OUI — desynchro |
| `paid_amount_cents` | `0` | `139200` | OUI |
| `invoice_status` | `null` | `paid` | OUI |
| `invoice_number` | `null` | `INV-2026-0001` | OUI |
| `remaining_amount_cents` | `0` | `0` | OK (mais par defaut) |

Test sur reservation 4 (confirmed) :

| Champ | Valeur | Probleme |
|-------|--------|----------|
| `total_amount_cents` | `4500` | |
| `deposit_amount_cents` | `13500` | **3x le total** — bug calcul deposit |
| `advance_payment_amount_cents` | `1800` | 40% de 4500 = correct |

---

## 9. Flow nominal attendu vs realite

### Flow attendu (location de vaisselle/mobilier)

```
1. Client contacte → Creer devis
2. Devis envoye → Client accepte et signe
3. Devis converti → Reservation creee
4. Facture unique creee → Acompte paye
5. Pre-check terrain → Mouvement depart planifie
6. Livraison → Mouvement depart execute
7. Evenement
8. Retour → Mouvement retour + inspection
9. Paiement solde
10. Facture soldee → Reservation terminee
```

### Ce qui marche

- Devis → Reservation (conversion OK, `converted_reservation_id` present)
- Reservation avec lignes produits et variantes
- Mouvements inventaire (depart/retour avec items)
- Dashboard stats + operations summary
- Search globale fonctionne

### Ce qui ne marche pas

- Signature devis (jamais branchee)
- Facturation (2 factures au lieu d'1, paiements non utilises)
- Desynchro payment_status reservation
- Deposit calcule a 300% du total
- Planning 404
- Pricing 404
- Relances vides
- Notifications vides

---

## Resume des problemes par priorite

### P1 — Bloquants pour la production

| # | Module | Description |
|---|--------|-------------|
| INV-01 | Factures | 2 factures par reservation au lieu d'1 |
| INV-02 | Paiements | Table payments existe mais jamais utilisee |
| INV-03 | Paiements | Route GET /payments 404 |
| RES-01 | Reservations | payment_status toujours "unpaid" meme si paye |
| RES-02 | Reservations | deposit_amount = 3x total (bug calcul) |

### P2 — Importants

| # | Module | Description |
|---|--------|-------------|
| DEV-01 | Devis | phases/negotiations/modules toujours vides |
| DEV-03 | Devis | Flow signature non branche |
| INV-05 | Factures | advance_rate hardcode a 0.4 |
| INV-06 | Factures | Credit notes non fonctionnel |
| INV-07 | Factures | Champs paiement redondants sur invoices |
| RES-03 | Reservations | invoice_status/number jamais mis a jour |

### P3 — Mineurs / cosmetic

| # | Module | Description |
|---|--------|-------------|
| CAT-01 | Catalogue | Nommage prix incoherent (unit_price vs price_per_day) |
| CAT-02 | Catalogue | Collections vide |
| CAT-03 | Catalogue | 109 produits inactifs non visibles |
| CUS-01 | Clients | Pas de SIRET/VAT pour B2B |
| DEV-02 | Devis | Pas de duplication devis |
| DEV-04 | Devis | total_cents absent de la liste |
| MOV-01 | Inventaire | damage_types non configure |
| MOV-02 | Inventaire | delivery_zones non configure |
