# V2 API Epicerie — Documentation Technique

**Domaine** : Epicerie
**Tenant fixe** : `tenant_id = 2`
**Base URL** : `/api/v2/`
**Auth** : Bearer JWT — tous les endpoints protégés
**RBAC** : `manager` → write (POST/PUT/DELETE) | `staff` → read (GET)
**Montants** : centimes dans l'API, conversion affichage côté frontend (`/ 100`)
**Pagination** : `?page=1&per_page=20` (défaut)

---

## Conventions globales

### Extraction tenant_id
Le `tenant_id` est extrait du JWT côté backend. Il ne doit **jamais** apparaître en paramètre URL ni en body de requête. Toute query repository ajoute `WHERE tenant_id = 2` de manière systématique.

### Shapes communes

```json
// Erreur standard
{ "detail": "Message erreur non-technique" }

// Liste paginée
{
  "items": [...],
  "total": 150,
  "page": 1,
  "per_page": 20,
  "pages": 8
}
```

### Types de mouvement de stock (`EpicerieStockMovementType`)
| Valeur | Sens | Déclencheur |
|--------|------|-------------|
| `ENTREE` | +stock | Réception commande fournisseur |
| `SORTIE` | -stock | Sortie manuelle |
| `VENTE` | -stock | Encaissement POS |
| `AJUSTEMENT` | +stock | Inventaire (écart positif) |
| `PERTE` | -stock | Inventaire (écart négatif) ou déclaration perte |
| `TRANSFERT_RESTAURANT` | -stock | Transfert interne vers restaurant |

### Invariant critique stock
> `confirmer vente (VALIDEE)` → décrémente `epicerie_stock.quantite` **atomiquement** dans la même transaction que la création du `EpicerieStockMovement` de type `VENTE`. Rollback complet si un produit est introuvable ou si le stock est insuffisant (quand `check_stock=True`).

---

## Page: Dashboard

Route React : `/epicerie/dashboard`
Rôles : `staff`, `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/stats/jour` | `?date=YYYY-MM-DD` (défaut: today) | `DashboardStats` |
| GET | `/api/v2/epicerie/stock/ruptures` | — | `EpicerieStockRead[]` |
| GET | `/api/v2/epicerie/ventes/top-jour` | `?date=YYYY-MM-DD&limit=5` | `TopVenteItem[]` |
| GET | `/api/v2/epicerie/stock/alertes` | — | `EpicerieStockRead[]` |
| GET | `/api/v2/epicerie/activite-recente` | `?limit=5` | `ActiviteItem[]` |

#### Shape `DashboardStats`
```json
{
  "date": "2026-03-09",
  "ca_ttc": 158430,
  "ca_ttc_euros": 1584.30,
  "nb_transactions": 47,
  "ticket_moyen_euros": 33.71,
  "nb_articles_vendus": 182,
  "stock_total_produits": 312,
  "ruptures_count": 4,
  "alertes_stock_bas_count": 11,
  "commandes_en_attente_count": 2,
  "par_mode_paiement": {
    "ESPECES": 89300,
    "CB": 69130
  }
}
```

#### Shape `TopVenteItem`
```json
{
  "produit_id": 18,
  "designation": "Poulet entier 1.5kg",
  "quantite_vendue": 12.0,
  "ca_ttc": 43200,
  "ca_ttc_euros": 432.00
}
```

#### Shape `ActiviteItem`
```json
{
  "type": "VENTE",
  "reference": "VTE-20260309-0042",
  "description": "Vente 3 articles — 28,50€",
  "produit_designation": null,
  "created_at": "2026-03-09T14:22:11Z"
}
```

### Règles métier
- Les stats du jour sont calculées sur `epicerie_ventes.date_vente` filtré `tenant_id=2` et `statut=VALIDEE`.
- `ruptures_count` : `epicerie_stock.quantite <= 0` pour `tenant_id=2` (lecture directe DB, ADR-14 — jamais en cache Redis).
- `alertes_stock_bas` : `quantite > 0 AND quantite < seuil_alerte` (hors ruptures).
- L'activité récente agrège les 5 derniers `EpicerieStockMovement` + `EpicerieVente` triés par `created_at DESC`.
- `commandes_en_attente_count` : `supply_orders.statut IN ('en_attente', 'confirmee', 'expediee')` filtré `tenant_id=2`.

### Arbre de composants React

```
DashboardEpicerie (src/pages/epicerie/DashboardEpicerie.tsx)
  StatsBarJour (src/components/epicerie/dashboard/StatsBarJour.tsx)
    StatCard                          (composant générique)
  BandeauRuptures (src/components/epicerie/dashboard/BandeauRuptures.tsx)
    RuptureAlert
  TopVentesJour (src/components/epicerie/dashboard/TopVentesJour.tsx)
    TopVenteRow
  AlertesStockBas (src/components/epicerie/dashboard/AlertesStockBas.tsx)
    AlerteStockCard
  ActiviteRecente (src/components/epicerie/dashboard/ActiviteRecente.tsx)
    ActiviteItem
```

---

## Page: Inventaire

Route React : `/epicerie/inventaire`
Rôles : read → `staff` | write → `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/stock` | `?categorie=X&fournisseur=Y&search=Z&is_low=true&is_empty=true` | `EpicerieStockRead[]` |
| GET | `/api/v2/epicerie/stock/{produit_id}` | — | `EpicerieStockRead` |
| PUT | `/api/v2/epicerie/stock/{produit_id}/seuil` | `SeuilAlerteUpdate` | `EpicerieStockRead` |
| POST | `/api/v2/epicerie/stock/ajustement` | `AjustementCreate` | `AjustementResponse` |
| POST | `/api/v2/epicerie/stock/comptage` | `ComptageRequest` | `ComptageResponse` |
| GET | `/api/v2/epicerie/stock/mouvements` | `?produit_id=X&type=VENTE&date_debut=&date_fin=&limit=100&offset=0` | `EpicerieStockMovementRead[]` |
| GET | `/api/v2/epicerie/stock/stats` | — | `EpicerieStockSummary` |

#### Shape `AjustementCreate` (body POST)
```json
{
  "produit_id": 42,
  "type_ajustement": "PERTE",
  "quantite": 2.5,
  "raison": "Casse rayon"
}
```
`type_ajustement` accepte : `AJUSTEMENT` | `PERTE` | `ENTREE` | `SORTIE`

#### Shape `AjustementResponse`
```json
{
  "success": true,
  "mouvement_id": 887,
  "produit_id": 42,
  "ancien_stock": 14.5,
  "nouveau_stock": 12.0,
  "quantite_ajustee": -2.5
}
```

#### Shape `ComptageRequest` (body POST)
```json
{
  "lignes": [
    { "produit_id": 42, "quantite_comptee": 12.0, "notes": "Rayon A" },
    { "produit_id": 57, "quantite_comptee": 0.5, "notes": null }
  ],
  "notes": "Inventaire mensuel mars 2026"
}
```

#### Shape `ComptageResponse`
```json
{
  "success": true,
  "nb_produits_comptes": 2,
  "nb_ajustements": 1,
  "date_comptage": "2026-03-09T10:00:00",
  "lignes": [
    {
      "produit_id": 42,
      "produit_designation": "Poulet entier 1.5kg",
      "quantite_theorique": 14.5,
      "quantite_comptee": 12.0,
      "ecart": -2.5,
      "ecart_pct": -17.24,
      "ajustement_cree": true,
      "mouvement_id": 888
    }
  ]
}
```

#### Shape `EpicerieStockMovementRead`
```json
{
  "id": 888,
  "produit_id": 42,
  "produit_designation": "Poulet entier 1.5kg",
  "type": "PERTE",
  "quantite": 2.5,
  "signed_quantite": -2.5,
  "date_mouvement": "2026-03-09T10:00:00Z",
  "reference": "INVENTAIRE-20260309-1000",
  "created_by_id": 5,
  "created_by_name": "Marie Dupont"
}
```

### Règles métier
- `ajustement` : crée un `EpicerieStockMovement` ET met à jour `epicerie_stock.quantite` dans la même transaction.
- `comptage` : pour chaque ligne, compare `quantite_comptee` vs `epicerie_stock.quantite`. Si écart > 0 → type `AJUSTEMENT` (entré). Si écart < 0 → type `PERTE` (sortie). Met à jour `last_inventory_date` dans tous les cas.
- `seuil_alerte` : lecture directe DB uniquement (ADR-14). Pas de cache Redis pour le stock.
- L'historique des mouvements est filtré `tenant_id=2` au niveau repository — aucune fuite cross-tenant possible.
- `PERTE` et `SORTIE` decrementent le stock. `AJUSTEMENT` et `ENTREE` l'incrémentent.

### Effets de bord sur le stock
- `POST /ajustement` → crée `EpicerieStockMovement` + modifie `epicerie_stock.quantite`
- `POST /comptage` → crée N `EpicerieStockMovement` (un par ligne en écart) + modifie N `epicerie_stock.quantite`

### Arbre de composants React

```
InventaireEpicerie (src/pages/epicerie/InventaireEpicerie.tsx)
  InventaireNav (src/components/epicerie/inventaire/InventaireNav.tsx)
    TabButton

  VueStock (src/components/epicerie/inventaire/VueStock.tsx)
    FiltresStock (categorie, fournisseur, search, is_low, is_empty)
    TableauStock
      LigneStock
        BadgeStockStatus       (OK | BAS | RUPTURE)
        BoutonAjustement

  ModalAjustementStock (src/components/epicerie/inventaire/ModalAjustementStock.tsx)
    SelectTypeAjustement       (AJUSTEMENT | PERTE | ENTREE | SORTIE)
    InputQuantite
    InputRaison

  VueComptagePhysique (src/components/epicerie/inventaire/VueComptagePhysique.tsx)
    TableauComptage
      LigneComptage            (produit + saisie quantite_comptee)
    BoutonValiderComptage
    ResultatComptage
      LigneResultatComptage    (ecart, badge OK/AJUSTE)

  HistoriqueMouvements (src/components/epicerie/inventaire/HistoriqueMouvements.tsx)
    FiltresMouvements          (type, date_debut, date_fin, produit_id)
    TableauMouvements
      LigneMouvement           (signed_quantite coloré +/-)
```

---

## Page: Point de Vente (POS)

Route React : `/epicerie/pos`
Rôles : `staff`, `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/produits` | `?search=X&categorie=Y&actif_only=true&limit=50&offset=0` | `EpicerieProduitRead[]` |
| GET | `/api/v2/epicerie/produits/{id}` | — | `EpicerieProduitRead` |
| GET | `/api/v2/epicerie/stock/{produit_id}` | — | `EpicerieStockRead` |
| POST | `/api/v2/epicerie/ventes/encaisser` | `EncaissementRequest` | `EncaissementResponse` |
| GET | `/api/v2/epicerie/ventes/{id}` | — | `VenteRead` |

#### Shape `EncaissementRequest` (body POST)
```json
{
  "lignes": [
    { "produit_id": 42, "quantite": 2.0, "remise_pct": 0 },
    { "produit_id": 57, "quantite": 1.0, "remise_pct": 10 }
  ],
  "mode_paiement": "ESPECES",
  "montant_especes": 5000,
  "montant_cb": 0,
  "client_nom": null,
  "client_email": null,
  "remise_pct": 0,
  "notes": null
}
```
`mode_paiement` accepte : `ESPECES` | `CB` | `MIXTE` | `CHEQUE` | `VIREMENT`

#### Shape `EncaissementResponse`
```json
{
  "success": true,
  "vente_id": 334,
  "numero_ticket": "VTE-20260309-0042",
  "total_ttc": 4280,
  "total_ttc_euros": 42.80,
  "montant_rendu": 720,
  "montant_rendu_euros": 7.20,
  "message": "Vente VTE-20260309-0042 encaissée avec succès — Facture #89",
  "invoice_id": 89
}
```

#### Shape `EpicerieProduitRead` (extrait)
```json
{
  "id": 42,
  "tenant_id": 2,
  "ean": "3256224000000",
  "designation_clean": "Poulet entier 1.5kg",
  "nom_court": "Poulet entier",
  "categorie": "Viandes",
  "unite_vente": "U",
  "prix_unitaire": 1490,
  "prix_unitaire_euros": 14.90,
  "fournisseur_source": "METRO",
  "actif": true
}
```

### Règles métier
- **Invariant POS** : `POST /encaisser` est une transaction atomique :
  1. Crée `EpicerieVente` (statut `EN_COURS`)
  2. Crée toutes les `EpicerieVenteLigne`
  3. Vérifie `montant_especes + montant_cb >= total_ttc` → erreur `422` sinon
  4. Calcule `montant_rendu = total_paye - total_ttc`
  5. Pour chaque ligne : crée `EpicerieStockMovement(type=VENTE)` + décrémente `epicerie_stock.quantite`
  6. Passe `statut = VALIDEE`
  7. Crée `FinanceInvoice` + `FinancePayment` (si entité configurée pour le tenant)
- Le numéro de ticket suit le format `VTE-YYYYMMDD-NNNN` (séquentiel journalier).
- TVA : taux par défaut 20% (`DEFAULT_TVA_RATE = 2000`). ADR-06-BIS : la TVA DOM à 8,5% devra être configurée via `categories_produit.tva_defaut` lors d'une évolution future.
- Monnaie rendue calculée uniquement pour le mode `ESPECES` ou `MIXTE`. Jamais négative.
- `check_stock` : le flag est disponible dans le service mais est `False` par défaut au POS. Activer à `True` pour bloquer les ventes en rupture.
- Le stock temps réel est lu directement en DB avant affichage (ADR-14 — aucun cache).

### Effets de bord sur le stock
- `POST /encaisser` → N `EpicerieStockMovement(type=VENTE)` + décrémentation N stocks

### Arbre de composants React

```
PointDeVente (src/pages/epicerie/PointDeVente.tsx)
  CataloguePOS (src/components/epicerie/pos/CataloguePOS.tsx)
    SearchBarPOS
    FiltreCategoriePOS
    GridProduits
      CarteProduitPOS            (prix TTC affiché, badge stock temps réel)

  PanierPOS (src/components/epicerie/pos/PanierPOS.tsx)
    LignePanierPOS               (quantite, prix unitaire, sous-total)
    RemisePanier
    TotauxPanier                 (HT, TVA, TTC)

  ModalEncaissement (src/components/epicerie/pos/ModalEncaissement.tsx)
    SelectModePaiement
    InputMontantEspeces
    InputMontantCB
    MonnaieRendue                (calcul temps réel = paye - total_ttc)
    BoutonConfirmerPaiement

  TicketVente (src/components/epicerie/pos/TicketVente.tsx)
    EnteteTicket                 (numero_ticket, date_vente)
    LignesTicket
    TotauxTicket
    InfoPaiement
    BoutonNouvelleVente
```

---

## Page: Fournisseurs

Route React : `/epicerie/fournisseurs`
Rôles : read → `staff` | write → `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/fournisseurs` | `?search=X` | `FournisseurRead[]` |
| GET | `/api/v2/epicerie/fournisseurs/{vendor_id}` | — | `FournisseurDetail` |
| GET | `/api/v2/epicerie/commandes` | `?vendor_id=X&statut=confirmee&page=1&per_page=20` | Paginé `SupplyOrderRead[]` |
| GET | `/api/v2/epicerie/commandes/{id}` | — | `SupplyOrderDetail` |
| POST | `/api/v2/epicerie/commandes` | `SupplyOrderCreate` | `SupplyOrderDetail` |
| PUT | `/api/v2/epicerie/commandes/{id}` | `SupplyOrderUpdate` | `SupplyOrderRead` |
| POST | `/api/v2/epicerie/commandes/{id}/confirmer` | `ConfirmOrderRequest` | `SupplyOrderRead` |
| POST | `/api/v2/epicerie/commandes/{id}/annuler` | `CancelOrderRequest` | `SupplyOrderRead` |

#### Shape `FournisseurRead`
```json
{
  "id": 3,
  "name": "METRO Cash & Carry",
  "code": "METRO",
  "nb_articles": 487,
  "nb_commandes_actives": 2,
  "ca_mensuel_cts": 284500,
  "ca_mensuel_euros": 2845.00,
  "dette_cts": 0
}
```

#### Shape `SupplyOrderCreate` (body POST)
```json
{
  "vendor_id": 3,
  "reference": "CMD-METRO-2026-031",
  "date_commande": "2026-03-09",
  "date_livraison_prevue": "2026-03-14",
  "notes": "Commande hebdomadaire",
  "lines": [
    {
      "produit_id": 42,
      "designation": "Poulet entier 1.5kg",
      "quantity": 20.0,
      "prix_unitaire": 890,
      "notes": null
    }
  ]
}
```

#### Shape `SupplyOrderRead`
```json
{
  "id": 77,
  "tenant_id": 2,
  "vendor_id": 3,
  "vendor": { "id": 3, "name": "METRO Cash & Carry", "code": "METRO" },
  "reference": "CMD-METRO-2026-031",
  "date_commande": "2026-03-09",
  "date_livraison_prevue": "2026-03-14",
  "date_livraison_reelle": null,
  "statut": "en_attente",
  "montant_ht": 17800,
  "montant_tva": 3560,
  "montant_ttc": 21360,
  "nb_lignes": 1,
  "nb_produits": 20,
  "is_pending": true,
  "is_delivered": false,
  "is_cancelled": false,
  "is_late": false,
  "created_at": "2026-03-09T09:15:00Z",
  "updated_at": "2026-03-09T09:15:00Z"
}
```

### Règles métier
- Les fournisseurs sont dans `finance_vendors` — **sans tenant_id** (ADR-02). METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM sont des référentiels partagés.
- Les `supply_orders` ont un `tenant_id` — isolation garantie par le repository.
- Transitions de statut autorisées : `en_attente → confirmee` | `confirmee → expediee` | `expediee → livree` | `{en_attente,confirmee} → annulee`.
- La transition `confirmee` ne génère pas de mouvement de stock (seulement la transition `livree` via la page Réception).
- `date_commande` ne peut pas être dans le futur (validateur Pydantic).
- Les stats CA mensuel et dette sont calculées sur les `finance_invoices` liées au vendor pour le mois courant, filtrées `tenant_id=2`.

### Arbre de composants React

```
FournisseursEpicerie (src/pages/epicerie/FournisseursEpicerie.tsx)
  ListeFournisseurs (src/components/epicerie/fournisseurs/ListeFournisseurs.tsx)
    SearchBarFournisseur
    CarteFournisseur             (nom, code, stats CA, dette, nb commandes actives)

  DetailFournisseur (src/components/epicerie/fournisseurs/DetailFournisseur.tsx)
    InfosFournisseur
    StatsFournisseur             (CA mensuel, dette, nb articles)
    ListeCommandesFournisseur
      FiltreStatutCommande
      LigneCommande
        BadgeStatutCommande      (en_attente | confirmee | expediee | livree | annulee)

  ModalNouvelleCommande (src/components/epicerie/fournisseurs/ModalNouvelleCommande.tsx)
    SelectFournisseur
    InputReference
    InputDateCommande
    InputDateLivraisonPrevue
    TableauLignesCommande
      LigneCommandeEditable      (search produit, quantite, prix_unitaire)
      BoutonAjouterLigne
    TotauxCommande
    BoutonCreerCommande
```

---

## Page: Historique Ventes

Route React : `/epicerie/historique`
Rôles : read → `staff` | write (annulation) → `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/ventes` | `?statut=VALIDEE&date_debut=&date_fin=&search=&limit=50&offset=0` | `VenteRead[]` |
| GET | `/api/v2/epicerie/ventes/{id}` | — | `VenteRead` |
| GET | `/api/v2/epicerie/ventes/ticket/{numero_ticket}` | — | `VenteRead` |
| POST | `/api/v2/epicerie/ventes/{id}/annuler` | `{ "raison": "..." }` | `VenteRead` |
| GET | `/api/v2/epicerie/ventes/stats` | `?date_debut=&date_fin=` | `VenteStats` |
| GET | `/api/v2/epicerie/ventes/export-csv` | `?date_debut=&date_fin=&statut=VALIDEE` | `text/csv` |

#### Shape `VenteRead` (complet)
```json
{
  "id": 334,
  "tenant_id": 2,
  "numero_ticket": "VTE-20260309-0042",
  "date_vente": "2026-03-09T14:22:11Z",
  "statut": "VALIDEE",
  "mode_paiement": "ESPECES",
  "montant_especes": 5000,
  "montant_cb": 0,
  "montant_rendu": 720,
  "total_ht": 3567,
  "total_tva": 713,
  "total_ttc": 4280,
  "remise_pct": 0,
  "remise_montant": 0,
  "client_nom": null,
  "client_email": null,
  "vendeur_id": 5,
  "notes": null,
  "nb_articles": 3,
  "is_paid": true,
  "total_ttc_euros": 42.80,
  "lignes": [
    {
      "id": 891,
      "produit_id": 42,
      "produit_designation": "Poulet entier 1.5kg",
      "produit_ean": "3256224000000",
      "quantite": 2.0,
      "prix_unitaire_ht": 1242,
      "taux_tva": 2000,
      "montant_ht": 2484,
      "montant_tva": 497,
      "montant_ttc": 2981,
      "remise_pct": 0,
      "montant_ttc_euros": 29.81
    }
  ]
}
```

#### Shape `VenteStats`
```json
{
  "total_ventes": 47,
  "ca_ttc": 158430,
  "ca_ttc_euros": 1584.30,
  "ca_ht": 132025,
  "total_tva": 26405,
  "nb_articles_vendus": 182,
  "panier_moyen": 33.71,
  "par_mode_paiement": {
    "ESPECES": 89300,
    "CB": 69130
  }
}
```

### Règles métier
- `annuler` une vente `VALIDEE` : crée un `EpicerieStockMovement(type=AJUSTEMENT, reference="ANNULATION-VTE-...")` pour **chaque ligne** et réincrémente le stock. Atomique — rollback si un produit est introuvable.
- `annuler` une vente `EN_COURS` : passe `statut = ANNULEE` sans toucher au stock (stock non encore décrémenté).
- Une vente déjà `ANNULEE` : appel idempotent, retourne la vente sans modification.
- L'export CSV contient : `numero_ticket, date_vente, statut, mode_paiement, total_ttc_euros, nb_articles, client_nom`. Filtré `tenant_id=2`.
- `search` filtre sur `numero_ticket` ou `client_nom` (ILIKE).
- La TVA affichée sur le détail d'une vente est `taux_tva / 100` % (ex: `2000` → 20%). Pour DOM 8.5% → `850`.

### Effets de bord sur le stock
- `POST /ventes/{id}/annuler` (si statut était `VALIDEE`) → N `EpicerieStockMovement(type=AJUSTEMENT)` + réincrémentation N stocks

### Arbre de composants React

```
HistoriqueVentes (src/pages/epicerie/HistoriqueVentes.tsx)
  FiltresHistorique (src/components/epicerie/historique/FiltresHistorique.tsx)
    RangeDatePicker
    SelectStatutVente
    SearchBarTicket

  TableauVentes (src/components/epicerie/historique/TableauVentes.tsx)
    LigneVente
      BadgeStatutVente           (EN_COURS | VALIDEE | ANNULEE | REMBOURSEE)
      BoutonDetailVente

  DetailVente (src/components/epicerie/historique/DetailVente.tsx)
    EnteteVente
    LignesVente
      LigneDetailVente           (designation, qte, prix_ht, TVA %, TTC)
    TotauxDetailVente            (HT, TVA 8.5%, TTC)
    InfoPaiementDetail           (mode, especes, CB, rendu)
    BoutonAnnulerVente           (manager uniquement, si statut=VALIDEE)
    ModalConfirmAnnulation
      InputRaisonAnnulation

  BoutonExportCSV
  VenteStatsBar (src/components/epicerie/historique/VenteStatsBar.tsx)
    StatsMiniCard
```

---

## Page: Réception Commandes

Route React : `/epicerie/reception`
Rôles : `staff`, `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/commandes` | `?statut=confirmee&statut=expediee` | Paginé `SupplyOrderRead[]` |
| GET | `/api/v2/epicerie/commandes/{id}` | — | `SupplyOrderDetail` |
| PUT | `/api/v2/epicerie/commandes/{id}/lignes/{line_id}` | `SupplyOrderLineUpdate` | `SupplyOrderLineRead` |
| POST | `/api/v2/epicerie/commandes/{id}/recevoir` | `ReceiveOrderRequest` | `SupplyOrderRead` |
| POST | `/api/v2/epicerie/commandes/{id}/signaler-ecart` | `EcartSignalRequest` | `{ "ok": true }` |

#### Shape `ReceiveOrderRequest` (body POST)
```json
{
  "date_livraison_reelle": "2026-03-14",
  "lines": [
    { "line_id": 201, "received_quantity": 18.0 },
    { "line_id": 202, "received_quantity": 10.0 }
  ]
}
```
Si `lines` est `null`, toutes les lignes sont considérées comme entièrement reçues (`received_quantity = quantity`).

#### Shape `EcartSignalRequest` (body POST)
```json
{
  "line_id": 202,
  "quantite_commandee": 20.0,
  "quantite_recue": 10.0,
  "motif": "Rupture fournisseur — livraison partielle prévue semaine prochaine"
}
```

#### Shape `SupplyOrderDetail`
```json
{
  "id": 77,
  "statut": "confirmee",
  "vendor": { "id": 3, "name": "METRO Cash & Carry" },
  "date_commande": "2026-03-09",
  "date_livraison_prevue": "2026-03-14",
  "montant_ht": 17800,
  "montant_ttc": 21360,
  "nb_lignes": 2,
  "lines": [
    {
      "id": 201,
      "designation": "Poulet entier 1.5kg",
      "quantity": 20.0,
      "prix_unitaire": 890,
      "received_quantity": null,
      "montant_ligne": 17800,
      "is_fully_received": false,
      "is_partially_received": false
    }
  ]
}
```

### Règles métier
- La page liste uniquement les commandes `statut IN ('confirmee', 'expediee')` pour ce tenant.
- **Invariant réception** : `POST /recevoir` est atomique :
  1. Met à jour `received_quantity` sur chaque ligne
  2. Crée un `EpicerieStockMovement(type=ENTREE)` par ligne reçue (quantite = `received_quantity`)
  3. Incrémente `epicerie_stock.quantite` par `received_quantity` pour chaque produit
  4. Passe `supply_order.statut = livree` et enregistre `date_livraison_reelle`
- Une réception partielle (certaines lignes < quantité commandée) est autorisée et documentée dans `received_quantity`. La commande passe quand même en `livree`.
- Signaler un écart : endpoint informatif uniquement — crée une note dans `supply_order.notes`, ne modifie pas le statut.
- Si `produit_id` d'une ligne est `null` (produit non mappé dans le catalogue unifié), le mouvement de stock **n'est pas créé** mais la réception est enregistrée. Alerte loggée.

### Effets de bord sur le stock
- `POST /recevoir` → N `EpicerieStockMovement(type=ENTREE)` + incrémentation N stocks (selon `received_quantity`)

### Arbre de composants React

```
ReceptionCommandes (src/pages/epicerie/ReceptionCommandes.tsx)
  ListeCommandesARecevoir (src/components/epicerie/reception/ListeCommandesARecevoir.tsx)
    FiltreStatutReception        (confirmee | expediee)
    CarteCommandeARecevoir
      BadgeStatutCommande
      BoutonCommencerReception

  FlowReception (src/components/epicerie/reception/FlowReception.tsx)
    HeaderCommandeReception      (vendor, ref, date_livraison_prevue)
    TableauLignesReception
      LigneReception
        InfoProduit              (designation, quantite commandee)
        InputQuantiteRecue       (saisie par ligne)
        BadgeReception           (OK | PARTIEL | EN ATTENTE)
    InputDateLivraisonReelle
    BoutonFinaliserReception
    BoutonSignalerEcart

  ModalSignalerEcart (src/components/epicerie/reception/ModalSignalerEcart.tsx)
    InfoEcart                    (commandee vs saisie)
    TextareaMotif
    BoutonConfirmerSignalement

  ConfirmationReception (src/components/epicerie/reception/ConfirmationReception.tsx)
    ResumeReception              (nb lignes reçues, montant total)
    ListeMouvementsCreés
```

---

## Page: Transferts Internes

Route React : `/epicerie/transferts`
Rôles : read → `staff` | write → `manager`

### Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| GET | `/api/v2/epicerie/transferts` | `?statut=PENDING&page=1&per_page=20` | Paginé `InternalTransferRead[]` |
| GET | `/api/v2/epicerie/transferts/{id}` | — | `InternalTransferDetail` |
| POST | `/api/v2/epicerie/transferts` | `InternalTransferCreate` | `InternalTransferDetail` |
| POST | `/api/v2/epicerie/transferts/{id}/valider` | `{ "notes": "..." }` | `InternalTransferRead` |
| POST | `/api/v2/epicerie/transferts/{id}/annuler` | `{ "raison": "..." }` | `InternalTransferRead` |

#### Shape `InternalTransferCreate` (body POST)
```json
{
  "entity_source_id": 1,
  "entity_dest_id": 2,
  "reference": "TRF-20260309-001",
  "notes": "Approvisionnement restaurant semaine 10",
  "lines": [
    {
      "produit_id": 42,
      "ingredient_id": 15,
      "quantite": 5.0,
      "unite": "KG",
      "prix_unitaire": 890,
      "tva_pct": 850
    }
  ]
}
```
`tva_pct` : 850 = 8,5% (DOM, ADR-06-BIS) | 2000 = 20%

#### Shape `InternalTransferRead`
```json
{
  "id": 12,
  "tenant_id": 2,
  "entity_source_id": 1,
  "entity_dest_id": 2,
  "entity_source_nom": "Epicerie MassaCorp",
  "entity_dest_nom": "Restaurant MassaCorp",
  "reference": "TRF-20260309-001",
  "status": "PENDING",
  "nb_lignes": 1,
  "montant_ht": 4450,
  "montant_ttc": 4828,
  "invoice_id": null,
  "notes": "Approvisionnement restaurant semaine 10",
  "created_by": 5,
  "created_at": "2026-03-09T08:00:00Z",
  "validated_at": null,
  "validated_by": null
}
```

#### Shape `InternalTransferDetail`
Inclut `InternalTransferRead` plus :
```json
{
  "lines": [
    {
      "id": 45,
      "produit_id": 42,
      "ingredient_id": 15,
      "quantite": 5.0,
      "unite": "KG",
      "prix_unitaire": 890,
      "montant_ht": 4450,
      "tva_pct": 850,
      "montant_ttc": 4828,
      "mouvement_epicerie_id": null,
      "mouvement_restaurant_id": null,
      "prix_unitaire_euros": 8.90,
      "montant_ttc_euros": 48.28
    }
  ]
}
```

### Règles métier
- **ADR-03** : `internal_transfers` est sans `tenant_id` propre mais les FK brutes `entity_source_id`/`entity_dest_id` garantissent l'isolation via les entités Finance.
- **Invariant validation** : `POST /valider` est atomique :
  1. Pour chaque ligne : crée `EpicerieStockMovement(type=TRANSFERT_RESTAURANT)` → décrémente stock épicerie
  2. Pour chaque ligne : crée `RestaurantStockMovement(type=ENTREE)` → incrémente stock restaurant
  3. Crée une `FinanceInvoice` interne (entre les deux entités)
  4. Remplit `mouvement_epicerie_id` et `mouvement_restaurant_id` sur chaque ligne
  5. Passe `status = VALIDATED` + enregistre `validated_at` et `validated_by`
- Un transfert `PENDING` peut être annulé sans effet sur le stock.
- Un transfert `VALIDATED` **ne peut pas** être annulé (les mouvements sont historisés).
- `ingredient_id` est optionnel : permet de lier la ligne à un ingrédient restaurant pour la traçabilité. Si null, le mouvement restaurant est créé sans lien ingrédient.
- Les transferts sont affichés avec l'historique complet (PENDING + VALIDATED + CANCELLED).

### Effets de bord sur le stock
- `POST /valider` → N `EpicerieStockMovement(type=TRANSFERT_RESTAURANT)` + décrémentation N stocks épicerie + N `RestaurantStockMovement(type=ENTREE)` + incrémentation N stocks restaurant

### Arbre de composants React

```
TransfertsInternes (src/pages/epicerie/TransfertsInternes.tsx)
  HeaderTransferts
  OngletsTransferts              (En cours | Historique)

  ListeTransfertsEnCours (src/components/epicerie/transferts/ListeTransfertsEnCours.tsx)
    CarteTransfert
      BadgeStatutTransfert       (PENDING | VALIDATED | CANCELLED)
      BoutonValider              (manager uniquement, si PENDING)
      BoutonAnnuler              (manager uniquement, si PENDING)

  HistoriqueTransferts (src/components/epicerie/transferts/HistoriqueTransferts.tsx)
    FiltresTransferts            (statut, date)
    TableauTransferts
      LigneTransfert

  ModalNouveauTransfert (src/components/epicerie/transferts/ModalNouveauTransfert.tsx)
    SelectEntiteSource
    SelectEntiteDest
    InputReference
    TableauLignesTransfert
      LigneTransfertEditable
        SelectProduit
        SelectIngredientRestaurant  (optionnel)
        InputQuantite
        InputPrixUnitaire
        SelectTauxTVA              (8.5% DOM | 20%)
    TotauxTransfert
    BoutonCreerTransfert

  DetailTransfert (src/components/epicerie/transferts/DetailTransfert.tsx)
    InfosTransfert               (source, dest, reference, dates)
    TableauLignesDetail
      LigneDetailTransfert       (produit, qte, prix, montant_ttc)
    BoutonValiderTransfert       (manager, si PENDING)
    ModalConfirmValidation
```

---

## Matrice des effets de bord stock

| Endpoint | Type mouvement créé | Sens stock |
|----------|---------------------|------------|
| `POST /ventes/encaisser` | `VENTE` | -stock épicerie |
| `POST /ventes/{id}/annuler` (était VALIDEE) | `AJUSTEMENT` | +stock épicerie |
| `POST /stock/ajustement` (ENTREE/AJUSTEMENT) | `ENTREE` ou `AJUSTEMENT` | +stock épicerie |
| `POST /stock/ajustement` (SORTIE/PERTE) | `SORTIE` ou `PERTE` | -stock épicerie |
| `POST /stock/comptage` (écart positif) | `AJUSTEMENT` | +stock épicerie |
| `POST /stock/comptage` (écart négatif) | `PERTE` | -stock épicerie |
| `POST /commandes/{id}/recevoir` | `ENTREE` | +stock épicerie |
| `POST /transferts/{id}/valider` | `TRANSFERT_RESTAURANT` | -stock épicerie, +stock restaurant |

---

## Contraintes multi-tenant — Rappel

- Toute query sur `epicerie_produits`, `epicerie_stock`, `epicerie_stock_movements`, `epicerie_ventes`, `supply_orders` **doit** inclure `WHERE tenant_id = 2` au niveau repository.
- `finance_vendors` (ADR-02) et `internal_transfers` (ADR-03) n'ont pas de `tenant_id` — l'isolation passe par les FK et la logique applicative.
- Tests anti-cross-tenant obligatoires pour tout endpoint modifiant ou lisant des données épicerie.
- Violation d'isolation = incident **P0** immédiat.

---

## Index des fichiers sources clés

| Couche | Fichier |
|--------|---------|
| Modèle produit | `app/models/epicerie/produit.py` |
| Modèle stock | `app/models/epicerie/stock.py` |
| Modèle vente | `app/models/epicerie/vente.py` |
| Modèle commande | `app/models/epicerie/supply_order.py` |
| Modèle transfert | `app/models/internal_transfer.py` |
| Service vente (POS) | `app/services/epicerie/vente.py` |
| Service inventaire | `app/services/epicerie/inventaire.py` |
| Schemas Pydantic | `app/schemas/epicerie.py` |
| Endpoints commandes | `app/api/v1/endpoints/epicerie.py` |
| Endpoints stock async | `app/api/v1/endpoints/epicerie_async.py` |
| Endpoints transferts | `app/api/v1/endpoints/internal_transfers.py` |
