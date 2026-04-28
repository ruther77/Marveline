# Feature Card — Épicerie Fournisseurs

**Route React** : `/epicerie/fournisseurs`
**Rôles** : `staff` (lecture), `manager` (écriture)
**Tenant** : `tenant_id = 2` (extrait du JWT)
**Statut** : VALIDÉE — cross-validée mockup + spec (2026-03-10)

---

## 1. Flows UI (source : mockup `epicerie_fournisseurs.html`)

| # | Flow | Déclencheur | Résultat |
|---|------|-------------|---------|
| 1 | Lister fournisseurs | Chargement page | Accordéons dépliables : nom, code, nb articles, dette totale, badge statut |
| 2 | Ouvrir détail fournisseur | Clic accordéon | `GET /fournisseurs/{id}/stats` + factures chargées — stat-cards + distribution catégories |
| 3 | Filtrer factures du fournisseur | Onglets Toutes / En attente / Payées / En retard | Filtre local sur `finance_invoices` déjà chargées |
| 4 | Voir onglet Synthèse dettes | Clic onglet "Synthèse dettes" | Tableau récapitulatif + distribution % dette (calculé frontend sur `GET /fournisseurs`) |
| 5 | Créer nouvelle commande | Clic "+ Nouvelle commande" (dans accordéon) | Modal `ModalNouvelleCommande` → `POST /commandes` |
| 6 | Rechercher fournisseur | Champ recherche | `GET /fournisseurs?search=X` |

---

## 2. Endpoints API

| Méthode | Path | Params / Body | Réponse | Rôle |
|---------|------|---------------|---------|------|
| `GET` | `/api/v2/epicerie/fournisseurs` | `?search=X` | `FournisseurRead[]` | `staff` |
| `GET` | `/api/v2/epicerie/fournisseurs/{id}/stats` | — | `FournisseurStats` | `staff` |
| `GET` | `/api/v2/epicerie/fournisseurs/{id}/invoices` | `?statut=EN_ATTENTE\|PAYEE\|EN_RETARD&page&per_page` | `FinanceInvoiceRead[]` | `staff` |
| `GET` | `/api/v2/epicerie/commandes` | `?vendor_id=&statut=&page&per_page` | `SupplyOrderRead[]` | `staff` |
| `POST` | `/api/v2/epicerie/commandes` | `SupplyOrderCreate` | `SupplyOrderRead` | `manager` |
| `PUT` | `/api/v2/epicerie/commandes/{id}` | `SupplyOrderUpdate` | `SupplyOrderRead` | `manager` |
| `POST` | `/api/v2/epicerie/commandes/{id}/confirmer` | — | `SupplyOrderRead` | `manager` |
| `POST` | `/api/v2/epicerie/commandes/{id}/annuler` | — | `SupplyOrderRead` | `manager` |

> **ADR-02** : `finance_vendors` (fournisseurs) est une table partagée **sans `tenant_id`** — référence catalogue globale.
> Le filtre tenant s'applique sur les `supply_orders` et `finance_invoices` (qui portent `tenant_id`).

---

## 3. Shapes JSON

### `GET /fournisseurs` — shape liste

```json
{
  "items": [
    {
      "vendor_id": "metro",
      "nom": "METRO",
      "code": "MET-001",
      "nb_articles": 340,
      "ca_mensuel_cts": 124500000,
      "dette_cts": 124500000,
      "badge_statut": "en_retard"
    }
  ]
}
```

> **`dette_cts`** : somme des `finance_invoices.montant_cts` où `statut IN ('EN_ATTENTE', 'EN_RETARD')` pour ce `vendor_id` + `tenant_id=2`.
> **`badge_statut`** : `"a_jour"` si `dette_cts = 0`, `"en_attente"` si dette > 0 sans retard, `"en_retard"` si au moins 1 invoice dépasse son échéance.

### `GET /fournisseurs/{id}/stats`

```json
{
  "vendor_id": "metro",
  "livraisons_mois": 8,
  "achats_mois_cts": 45600000,
  "delai_paiement_moyen_jours": 22,
  "distribution_categories": [
    {
      "categorie_nom": "Épicerie sèche",
      "pct": 42
    },
    {
      "categorie_nom": "Boissons",
      "pct": 28
    },
    {
      "categorie_nom": "Surgelés",
      "pct": 18
    },
    {
      "categorie_nom": "Autres",
      "pct": 12
    }
  ]
}
```

> **`livraisons_mois`** : `supply_orders` en statut `livree` sur le mois courant.
> **`achats_mois_cts`** : somme des montants de ces commandes livrées.
> **`delai_paiement_moyen_jours`** : moyenne `(invoice.date_paiement - invoice.date_echeance)` sur les 3 derniers mois (invoices payées uniquement). Positif = retard moyen, négatif = paiement anticipé.
> **`distribution_categories`** : répartition % des lignes de commandes sur le mois courant, par `categorie_nom`. Somme = 100.

### `GET /fournisseurs/{id}/invoices`

```json
{
  "items": [
    {
      "invoice_id": 1012,
      "numero": "FAC-20260301-0012",
      "date_facture": "2026-03-01",
      "date_echeance": "2026-03-31",
      "montant_cts": 48700000,
      "statut": "EN_ATTENTE",
      "supply_order_id": 88
    }
  ]
}
```

> **`statut`** : `EN_ATTENTE` | `PAYEE` | `EN_RETARD` (calculé : `date_echeance < today AND statut != PAYEE`).
> **`supply_order_id`** : FK vers la commande d'achat ayant déclenché cette facture (créée lors de la réception, cf. invariant `POST /commandes/{id}/recevoir`).
> Les invoices sont distinctes des `supply_orders` — une commande peut générer plusieurs factures (réceptions partielles successives).

### `POST /commandes` — body

```json
{
  "vendor_id": "metro",
  "lignes": [
    {
      "produit_id": 42,
      "quantite": 50,
      "prix_unitaire_cts": 18000
    }
  ],
  "notes": "Commande hebdomadaire"
}
```

### `SupplyOrderRead` (extrait)

```json
{
  "id": 88,
  "vendor_id": "metro",
  "vendor_nom": "METRO",
  "statut": "confirmee",
  "total_cts": 900000,
  "date_commande": "2026-03-01",
  "date_livraison_prevue": null,
  "notes": "Commande hebdomadaire",
  "lignes": [
    {
      "produit_id": 42,
      "designation": "Lait de coco Kara 400ml",
      "quantite": 50,
      "prix_unitaire_cts": 18000,
      "total_ligne_cts": 900000
    }
  ]
}
```

---

## 4. Règles métier

### Transitions statut commande fournisseur

| Transition | Déclencheur | Rôle |
|------------|-------------|------|
| `en_attente → confirmee` | `POST /commandes/{id}/confirmer` | `manager` |
| `confirmee → expediee` | Mise à jour manuelle (`PUT`) | `manager` |
| `expediee → livree` | `POST /commandes/{id}/recevoir` (page Réception) | `manager` |
| `en_attente → annulee` | `POST /commandes/{id}/annuler` | `manager` |
| `confirmee → annulee` | `POST /commandes/{id}/annuler` | `manager` |

> Transition `livree → *` : **impossible** — commande livrée est immuable.
> La transition `→ livree` déclenche la création de `finance_invoice` (invariant atomique dans la page Réception).

### Badge statut dette (onglet Synthèse dettes)

- **`"a_jour"`** : `dette_cts = 0` pour ce fournisseur
- **`"en_attente"`** : `dette_cts > 0` + aucune invoice dépassant son `date_echeance`
- **`"en_retard"`** : au moins 1 invoice `statut = EN_RETARD` (date_echeance < today)

### Distribution graphique Synthèse dettes (frontend)

Calculé côté frontend depuis `GET /fournisseurs` :
```
total_dette_globale = sum(fournisseurs[].dette_cts)
pct_fournisseur = (fournisseur.dette_cts / total_dette_globale) * 100
```
Aucun endpoint dédié requis.

### Chargement différé de l'accordéon

Les stats et invoices sont chargées **à l'ouverture** de l'accordéon, pas au chargement de la page :
- `GET /fournisseurs/{id}/stats` → déclenché au premier `onOpen` de l'accordéon
- `GET /fournisseurs/{id}/invoices` → déclenché au premier `onOpen`
- Résultats mis en cache local (React state) pour éviter les rechargements à la rouverture

---

## 5. Composants React

```
FournisseursPage (src/pages/epicerie/FournisseursPage.tsx)
│
├── OngletFournisseurs (src/components/epicerie/fournisseurs/OngletFournisseurs.tsx)
│   ├── SearchBarFournisseurs    — debounce 300ms, param ?search=
│   └── ListeFournisseurs
│       └── AccordeonFournisseur  — chargement différé au premier onOpen
│           ├── AccordeonHeader   — code couleur, nom, code, nb_articles, dette, badge_statut
│           ├── StatCardsFournisseur
│           │   ├── StatCard "Livraisons mois"       (livraisons_mois)
│           │   ├── StatCard "Achats mois XPF"       (achats_mois_cts / 100)
│           │   └── StatCard "Délai paiement moyen"  (delai_paiement_moyen_jours)
│           ├── DistributionCategories               — barres % (distribution_categories[])
│           ├── TableFactures
│           │   ├── OngletsFiltreFactures            — Toutes / En attente / Payées / En retard
│           │   └── LigneFacture                     — numero, date, montant XPF, badge statut
│           └── BoutonNouvelleCommande               → ouvre ModalNouvelleCommande
│
├── OngletSyntheseDettes (src/components/epicerie/fournisseurs/OngletSyntheseDettes.tsx)
│   ├── TableSyntheseDettes      — Fournisseur | Factures en attente | Total dû | Retard max | Statut
│   └── DistributionDettesGraph  — barres % calculées frontend (dette / total_global)
│
└── ModalNouvelleCommande (src/components/epicerie/fournisseurs/ModalNouvelleCommande.tsx)
    ├── SelectFournisseur        — vendor_id (depuis liste déjà chargée)
    ├── LignesCommande
    │   └── LigneCommandeInput   — produit_id, quantite, prix_unitaire_cts
    ├── InputNotes               — facultatif
    └── BoutonCreerCommande      — POST /commandes + toast succès
```

---

## 6. Références ADR

| ADR | Règle |
|-----|-------|
| **ADR-02** | `finance_vendors` partagée sans `tenant_id` — filtre tenant sur `supply_orders` et `finance_invoices` |
| **ADR-14** | Stock lu directement en DB, jamais en cache Redis |

---

## 7. Codes d'erreur métier

| HTTP | Code | Déclencheur |
|------|------|-------------|
| 409 | `TRANSITION_INVALIDE` | Transition statut interdite (ex: `livree → annulee`) |
| 404 | `VENDOR_NOT_FOUND` | `vendor_id` inconnu |
| 422 | `COMMANDE_VIDE` | `POST /commandes` avec `lignes = []` |

---

## 8. Gaps résolus lors de cette cross-validation

| # | Gap identifié | Décision |
|---|---------------|---------|
| G1 | "Factures" mockup vs "Commandes" spec | Deux entités distinctes — `supply_orders` (commandes achat) + `finance_invoices` (créées à la livraison via réception). L'accordéon affiche les invoices via `GET /fournisseurs/{id}/invoices` |
| G2 | Source `dette_cts` non précisée | Somme `finance_invoices.montant_cts` non payées (`EN_ATTENTE` + `EN_RETARD`) pour ce vendor + tenant |
| G3 | Distribution catégories absente de la spec | Incluse dans `GET /fournisseurs/{id}/stats` → `distribution_categories[]` |
| G4 | Stat-cards (livraisons, achats, délai) partiellement spécifiées | Endpoint dédié `GET /fournisseurs/{id}/stats` couvre les 3 + distribution (G3+G4 fusionnés) |
| G5 | Distribution graphique Synthèse dettes | Calculé frontend sur `GET /fournisseurs` (`dette_cts / total_global`) — aucun endpoint supplémentaire |
