# Feature Card — Épicerie Point de Vente (POS)

**Route React** : `/epicerie/pos`
**Rôles** : `staff`, `manager`
**Tenant** : `tenant_id = 2` (extrait du JWT)
**Statut** : VALIDÉE — cross-validée mockup + spec (2026-03-09) · RemisePanier spécifiée (2026-03-10)

---

## 1. Flows UI (source : mockup `epicerie_pos.html`)

| # | Flow | Déclencheur | Résultat |
|---|------|-------------|---------|
| 1 | Parcourir catalogue | Chargement page | Grille produits (recherche texte + filtre catégorie) |
| 2 | Recherche texte | `searchInput` keyup | Filtre `GET /produits?search=X` |
| 3 | Filtre catégorie | clic bouton filtre | `GET /produits?categorie=Y` |
| 4 | Scan EAN | bouton scanner → saisie EAN | `GET /produits/ean/{ean}` → ajoute au panier |
| 5 | Ajouter article | clic carte produit | Panier local mis à jour, totaux recalculés |
| 6 | Modifier quantité | `+` / `-` dans panier | Panier local mis à jour |
| 7 | Totaux temps réel | toute modification panier | HT + TVA + TTC recalculés (TVA extraite du TTC) |
| 8 | Sélectionner mode paiement | radio ESPECES / CB / VIREMENT | Champ monnaie rendue visible si ESPECES uniquement |
| 9 | Monnaie rendue | saisie montant espèces | `rendu = montant_especes - total_ttc`, jamais négatif |
| 10 | Valider vente | `validateBtn` | `POST /ventes/encaisser` → toast succès → reset panier |
| 11 | FAB mobile panier | mobile uniquement | Panel slide-in récapitulatif panier |
| 12 | Appliquer remise | clic bouton remise (rôle `manager` uniquement) | `RemisePanier` s'ouvre — toggle % / XPF, motif facultatif — totaux recalculés avec remise |

---

## 2. Endpoints API

| Méthode | Path | Params / Body | Réponse |
|---------|------|---------------|---------|
| `GET` | `/api/v2/epicerie/produits` | `?search=X&categorie=Y&actif_only=true&limit=50&offset=0` | `EpicerieProduitRead[]` |
| `GET` | `/api/v2/epicerie/produits/ean/{ean}` | — | `EpicerieProduitRead` ou `404` |
| `GET` | `/api/v2/epicerie/stock/{produit_id}` | — | `EpicerieStockRead` |
| `POST` | `/api/v2/epicerie/ventes/encaisser` | `EncaissementRequest` | `EncaissementResponse` |
| `GET` | `/api/v2/epicerie/ventes/{id}` | — | `VenteRead` |

> **ADR-14** : `GET /stock/{produit_id}` est une lecture directe DB — jamais en cache Redis.

---

## 3. Shapes JSON

### `EncaissementRequest` (body POST /ventes/encaisser)

```json
{
  "lignes": [
    {
      "produit_id": 42,
      "quantite": 2,
      "prix_unitaire_ttc": 350
    }
  ],
  "mode_paiement": "ESPECES",
  "montant_especes": 1000,
  "montant_cb": 0,
  "montant_virement": 0,
  "remise_centimes": 500,
  "remise_motif": "Fidélité client",
  "client_nom": null
}
```

> **Gap 3 résolu** : `montant_virement` ajouté. Validation backend : `montant_especes + montant_cb + montant_virement >= total_ttc_remisé` → 422 sinon.
>
> **`remise_centimes`** : 0 si pas de remise. Validation backend : `remise_centimes <= total_ttc` → 422 sinon. Défaut = 0.
> **`remise_motif`** : string libre facultatif (`null` accepté), enregistré sur la `EpicerieVente` pour traçabilité.

### `EncaissementResponse`

```json
{
  "id": 1234,
  "numero_ticket": "VTE-20260309-0047",
  "statut": "VALIDEE",
  "total_ht_brut": 7431,
  "total_tva_brut": 569,
  "total_ttc_brut": 8000,
  "remise_centimes": 500,
  "remise_motif": "Fidélité client",
  "total_ttc_remise": 7500,
  "total_ht_remise": 6978,
  "total_tva_remise": 522,
  "monnaie_rendue": 1500,
  "created_at": "2026-03-09T14:32:11Z"
}
```

### `EpicerieProduitRead` (extrait pertinent POS)

```json
{
  "id": 42,
  "designation": "Lait de coco Kara 400ml",
  "ean": "8888888000123",
  "prix_vente_ttc": 350,
  "categorie_id": 5,
  "categorie_nom": "Conserves",
  "taux_tva": 2000,
  "actif": true
}
```

> **ADR-06-BIS** : `taux_tva` = 2000 (20%) par défaut. La TVA DOM 8.5% (`taux_tva = 850`) sera configurée par catégorie via `categories_produit.tva_defaut` dans une évolution future.

---

## 4. Règles métier

### Invariant POS — transaction atomique `POST /encaisser`

L'encaissement est une opération **tout-ou-rien** :

1. Crée `EpicerieVente` (statut `EN_COURS`)
2. Crée toutes les `EpicerieVenteLigne`
3. Calcule `total_ttc_brut = sum(prix_unitaire_ttc * quantite)` sur les lignes
4. Valide `remise_centimes <= total_ttc_brut` → `422 REMISE_INVALIDE` sinon
5. Calcule `total_ttc_remise = total_ttc_brut - remise_centimes`
6. Vérifie `montant_especes + montant_cb + montant_virement >= total_ttc_remise` → `422` sinon
7. Si `check_stock=True` : vérifie stock suffisant ligne par ligne → `409` si rupture
8. Décrémente `epicerie_stock.quantite` + crée `EpicerieStockMovement(type=VENTE)` pour chaque ligne
9. Passe `statut = VALIDEE`
10. Crée `FinanceInvoice` + `FinancePayment` si entité Finance configurée

> La remise s'applique sur le TTC global — le mouvement de stock est inchangé (quantités non affectées).

> `check_stock = False` par défaut au POS (le badge stock est informatif, pas bloquant).

### Calcul TVA frontend

```
tva = Math.round(total_ttc * taux_tva_decimal / (1 + taux_tva_decimal))
ht  = total_ttc - tva
```

La TVA est **extraite du TTC** (prix de vente = TTC de référence).

### Remise panier

- Rôle requis : `manager` — bouton remise masqué pour `staff` (contrôle JWT côté UI + validation role côté backend)
- **Input UI** : toggle % / montant XPF. Conversion dans le composant : `remise_centimes = Math.round(total_ttc_brut * pct / 100)` si mode %
- **Motif** : string libre facultatif (`null` accepté) — affiché sur le ticket imprimé
- **Plafond** : `remise_centimes <= total_ttc_brut` uniquement (code `422 REMISE_INVALIDE`)
- **Recalcul totaux frontend** :
  ```
  total_ttc_remise = total_ttc_brut - remise_centimes
  // Répartition proportionnelle par ligne (respecte les taux TVA d'origine) :
  facteur = total_ttc_remise / total_ttc_brut
  tva_remise  = Math.round(total_tva_brut * facteur)
  ht_remise   = total_ttc_remise - tva_remise
  ```

### Monnaie rendue

- Calculée uniquement si `mode_paiement === 'ESPECES'`
- `rendu = montant_especes - total_ttc_remise` (après application de la remise)
- Jamais négative (UI bloque la validation si `montant_especes < total_ttc_remise`)

### Numéro de ticket

Format `VTE-YYYYMMDD-NNNN` — séquentiel journalier, généré côté backend.

### Stock temps réel sur les cartes produit

- Badge stock visible sur chaque carte (`CarteProduitPOS`)
- Lecture directe DB via `GET /stock/{produit_id}` — ADR-14
- Badge rouge si `quantite <= seuil_alerte`, gris si `quantite = 0`

---

## 5. Effets de bord sur le stock

| Action | Mouvement créé | Sens |
|--------|----------------|------|
| `POST /ventes/encaisser` (VALIDEE) | `VENTE` × N lignes | − stock épicerie |
| `POST /ventes/{id}/annuler` (était VALIDEE) | `AJUSTEMENT` × N lignes | + stock épicerie |

---

## 6. Composants React

```
PointDeVente (src/pages/epicerie/PointDeVente.tsx)
│
├── CataloguePOS (src/components/epicerie/pos/CataloguePOS.tsx)
│   ├── SearchBarPOS          — debounce 300ms, param ?search=
│   ├── FiltreCategoriePOS    — param ?categorie=
│   ├── ScannerEAN            — input EAN → GET /produits/ean/{ean}
│   └── GridProduits
│       └── CarteProduitPOS   — prix TTC, badge stock ADR-14
│
├── PanierPOS (src/components/epicerie/pos/PanierPOS.tsx)
│   ├── LignePanierPOS        — quantite, prix_unitaire_ttc, sous-total
│   ├── RemisePanier          — [Phase C] toggle %/XPF, input remise, motif, bouton manager uniquement
│   │   ├── ToggleModeRemise  — bascule "%" / "XPF fixe"
│   │   ├── InputRemise       — saisie montant (validation : remise <= total_ttc_brut)
│   │   ├── InputMotifRemise  — string libre facultatif
│   │   └── AffichageRemise   — ligne "Remise : -500 XPF" dans le récapitulatif
│   └── TotauxPanier          — HT brut, TVA brut, TTC brut, remise, TTC remisé
│
├── ModalEncaissement (src/components/epicerie/pos/ModalEncaissement.tsx)
│   ├── SelectModePaiement    — ESPECES | CB | VIREMENT
│   ├── InputMontantEspeces   — visible si ESPECES, calcule monnaie rendue
│   ├── AffichageRendu        — visible si ESPECES uniquement
│   └── BoutonEncaisser       — POST /ventes/encaisser + toast + reset
│
└── FABPanier                 — mobile uniquement, badge count articles
    └── PanelPanierMobile     — slide-in récapitulatif
```

> **`RemisePanier`** : non fonctionnel en Phase B (placeholder). Spécifié pour Phase C — Task #1. Contrôle rôle `manager` via JWT + validation backend `remise_centimes <= total_ttc`.

---

## 7. Références ADR & codes d'erreur

| ADR | Règle |
|-----|-------|
| **ADR-06-BIS** | TVA 20% par défaut. DOM 8.5% via `categories_produit.tva_defaut` — évolution future |
| **ADR-14** | Stock lu directement en DB, jamais en cache Redis |

| HTTP | Code | Déclencheur |
|------|------|-------------|
| 422 | `REMISE_INVALIDE` | `remise_centimes > total_ttc_brut` |
| 422 | `PAIEMENT_INSUFFISANT` | `montant_especes + montant_cb + montant_virement < total_ttc_remise` |
| 409 | `STOCK_INSUFFISANT` | Rupture stock ligne (si `check_stock=True`) |

---

## 8. Gaps résolus lors de cette cross-validation

| # | Gap identifié | Décision |
|---|---------------|---------|
| G1 | TVA mockup 8.5% vs spec 20% | ADR-06-BIS conservé — 20% par défaut, 8.5% DOM en évolution future |
| G2 | Scan EAN sans endpoint dédié | `GET /produits/ean/{ean}` ajouté (Option B — réponse exacte 1:1) |
| G3 | Mode VIREMENT absent de la shape | `montant_virement: int = 0` ajouté, validation 3-champs |
| G4 | `RemisePanier` non visible dans le mockup | Placeholder Phase B — spécifié Phase C (Task #1) : toggle %/XPF, motif facultatif, RBAC manager, remise proportionnelle HT+TVA |
