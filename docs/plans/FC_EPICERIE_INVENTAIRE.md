# Feature Card — Épicerie Inventaire

**Route React** : `/epicerie/inventaire`
**Rôles** : `staff` (lecture), `manager` (écriture)
**Tenant** : `tenant_id = 2` (extrait du JWT)
**Statut** : VALIDÉE — cross-validée mockup + spec (2026-03-10)

---

## 1. Flows UI (source : mockup `epicerie_inventaire.html`)

| # | Flow | Déclencheur | Résultat |
|---|------|-------------|---------|
| 1 | Charger vue stock | Chargement page onglet "Stock" | Barre stats + tableau articles filtrable |
| 2 | Rechercher article | `searchInput` keyup | `GET /stock?search=X` |
| 3 | Filtrer par catégorie | select catégorie | `GET /stock?categorie=X` |
| 4 | Filtrer par fournisseur | select fournisseur | `GET /stock?fournisseur=Y` |
| 5 | Filtrer ruptures / bas | checkboxes is_low / is_empty | `GET /stock?is_low=true` ou `?is_empty=true` |
| 6 | Toggle vue tableau / cartes | bouton toggle | Rendu local — pas d'appel API |
| 7 | Éditer seuil alerte | clic cellule "Stock mini" | Input inline → `PUT /stock/{id}/seuil` |
| 8 | Ajuster stock | clic "Ajuster" sur ligne | Modal → sélection type + quantité + raison → `POST /stock/ajustement` |
| 9 | Lancer comptage physique | onglet "Comptage physique" | Chargement liste complète via `GET /stock` |
| 10 | Saisir quantités comptées | input par ligne | Calcul écart local (comptée − système), colorisation, barre progression |
| 11 | Valider l'inventaire | clic "Valider l'inventaire" | `POST /stock/comptage` — atomique → toast résumé écarts |
| 12 | Consulter historique | onglet "Historique mouvements" | `GET /stock/mouvements` avec filtres type + produit + dates |

---

## 2. Endpoints API

| Méthode | Path | Params / Body | Réponse | Rôle |
|---------|------|---------------|---------|------|
| `GET` | `/api/v2/epicerie/stock` | `?search=&categorie=&fournisseur=&is_low=&is_empty=&page&per_page` | `EpicerieStockRead[]` | `staff` |
| `GET` | `/api/v2/epicerie/stock/{produit_id}` | — | `EpicerieStockRead` | `staff` |
| `GET` | `/api/v2/epicerie/stock/stats` | — | `EpicerieStockSummary` | `staff` |
| `PUT` | `/api/v2/epicerie/stock/{produit_id}/seuil` | `SeuilAlerteUpdate` | `EpicerieStockRead` | `manager` |
| `POST` | `/api/v2/epicerie/stock/ajustement` | `AjustementCreate` | `AjustementResponse` | `manager` |
| `POST` | `/api/v2/epicerie/stock/comptage` | `ComptageRequest` | `ComptageResponse` | `manager` |
| `GET` | `/api/v2/epicerie/stock/mouvements` | `?produit_id=&type=&date_debut=&date_fin=&limit=&offset=` | `EpicerieStockMovementRead[]` | `staff` |

> **ADR-14** : `stock.quantite` lu directement en DB — jamais en cache Redis.

---

## 3. Shapes JSON

### `GET /stock` — shape complète

```json
{
  "items": [
    {
      "id": 42,
      "produit_id": 42,
      "designation": "Riz Camellia 5 kg",
      "categorie": "Féculents & riz",
      "fournisseur_source": "METRO",
      "quantite": 47,
      "seuil_alerte": 10,
      "prix_unitaire_cts": 149000,
      "statut_badge": "ok",
      "derniere_mise_a_jour": "2026-03-09T08:12:00Z",
      "actif": true
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 1247
}
```

> **`statut_badge`** calculé backend : `"ok"` si `quantite > seuil_alerte`, `"bas"` si `0 < quantite <= seuil_alerte`, `"rupture"` si `quantite = 0`.

### `GET /stock/stats`

```json
{
  "total_articles": 1247,
  "nb_ruptures": 2,
  "nb_stock_bas": 8,
  "valeur_stock_cts": 4872300000
}
```

> Alimente la barre de stats en haut de page. `valeur_stock_cts` = `sum(quantite × prix_unitaire_cts)`.

### `PUT /stock/{produit_id}/seuil` — body

```json
{ "seuil": 10 }
```

### `POST /stock/ajustement` — body

```json
{
  "produit_id": 42,
  "type_ajustement": "PERTE",
  "quantite": 2.5,
  "raison": "Casse rayon"
}
```

> **Mapping types UI → API** :
> | Bouton UI | `type_ajustement` API |
> |-----------|----------------------|
> | Entrée | `ENTREE` |
> | Sortie | `SORTIE` |
> | Correction | `AJUSTEMENT` |
> | Perte | `PERTE` |
>
> Le bouton UI est libellé **"Correction"** (et non "Inventaire") pour éviter la confusion avec l'onglet Comptage physique.
> Types `VENTE` et `TRANSFERT_RESTAURANT` créés automatiquement — non exposés dans le modal.

### `AjustementResponse`

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

### `POST /stock/comptage` — body

```json
{
  "lignes": [
    {
      "produit_id": 42,
      "quantite_comptee": 12.0,
      "notes": "Rayon A — quelques boîtes abîmées"
    },
    {
      "produit_id": 57,
      "quantite_comptee": 0.5,
      "notes": null
    }
  ],
  "notes": "Inventaire mensuel mars 2026"
}
```

> **`notes`** (global) : obligatoire — identifie la session d'inventaire (ex : "Inventaire mensuel mars 2026").
> **`lignes[].notes`** : facultatif — observation par article.
> Seules les lignes avec `quantite_comptee ≠ quantite_systeme` génèrent un `EpicerieStockMovement(type=AJUSTEMENT)`.

### `ComptageResponse`

```json
{
  "success": true,
  "nb_produits_comptes": 47,
  "nb_ajustements": 3,
  "date_comptage": "2026-03-10T10:00:00Z",
  "lignes": [
    {
      "produit_id": 42,
      "produit_designation": "Riz Camellia 5 kg",
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

### `GET /stock/mouvements` — shape

```json
{
  "items": [
    {
      "id": 888,
      "produit_id": 42,
      "produit_designation": "Riz Camellia 5 kg",
      "type": "AJUSTEMENT",
      "quantite": 2.5,
      "signed_quantite": -2.5,
      "date_mouvement": "2026-03-10T10:00:00Z",
      "reference": "INVENTAIRE-20260310-1000",
      "created_by_name": "Marie Dupont",
      "notes": "Rayon A — quelques boîtes abîmées"
    }
  ]
}
```

---

## 4. Règles métier

### Types de mouvement épicerie

| Type API | Libellé UI | Sens | Créé par |
|----------|-----------|------|---------|
| `ENTREE` | Entrée | + stock | Modal Ajustement (manuel) |
| `SORTIE` | Sortie | − stock | Modal Ajustement (manuel) |
| `AJUSTEMENT` | Correction | ± stock | Modal Ajustement + `POST /comptage` |
| `PERTE` | Perte | − stock | Modal Ajustement (manuel) |
| `VENTE` | Vente | − stock | `POST /ventes/encaisser` (automatique) |
| `TRANSFERT_RESTAURANT` | Transfert | − stock | `POST /transferts/{id}/valider` (automatique) |

> Les types `VENTE` et `TRANSFERT_RESTAURANT` sont visibles dans l'historique mais **non accessibles** depuis le modal Ajustement.

### Invariant `POST /stock/ajustement` atomique

1. Vérifier `produit_id` appartient au `tenant_id = 2`
2. Calculer `nouveau_stock = quantite_actuelle + (signe × quantite)`
3. Vérifier `nouveau_stock >= 0` → `422 STOCK_NEGATIF` sinon
4. Mettre à jour `epicerie_stock.quantite`
5. Créer `EpicerieStockMovement`
6. Si `nouveau_stock <= seuil_alerte` → créer ou mettre à jour alerte

### Invariant `POST /stock/comptage` atomique

1. Charger `quantite_actuelle` pour chaque `produit_id` des lignes
2. Vérifier tous les `produit_id` appartiennent au `tenant_id = 2`
3. Pour chaque ligne avec `quantite_comptee ≠ quantite_actuelle` :
   - Calculer `ecart = quantite_comptee − quantite_actuelle`
   - Mettre à jour `epicerie_stock.quantite = quantite_comptee`
   - Créer `EpicerieStockMovement(type=AJUSTEMENT, quantite=|ecart|, signed_quantite=ecart)`
4. Toutes les écritures dans la même transaction — rollback global si erreur

> Lignes sans écart (`quantite_comptee = quantite_actuelle`) sont ignorées sans erreur.

### Édition inline seuil alerte

- Clic sur la cellule "Stock mini" → transforme en `<input type="number" min="0">`
- `onBlur` ou `Enter` → `PUT /stock/{produit_id}/seuil` + mise à jour locale du `statut_badge`
- `Escape` → annule sans appel API

### Onglet Comptage physique — workflow

1. Chargement via `GET /stock` (tous les articles actifs, sans pagination — `per_page=1000`)
2. L'utilisateur saisit les quantités comptées ligne par ligne
3. Barre de progression : `comptés / total_articles`
4. Écart coloré : rouge si négatif, vert si positif, gris si nul
5. Bouton "Valider" activé si `notes` global renseigné ET au moins 1 écart non nul
6. `POST /stock/comptage` → toast résumé : "3 ajustements sur 47 articles"

### Boutons hors scope

- **"Nouvel article"** : placeholder roadmap — création produit hors périmètre inventaire
- **"Exporter"** : placeholder roadmap — `GET /stock/export-csv` à définir en Phase ultérieure

---

## 5. Composants React

```
InventairePage (src/pages/epicerie/InventairePage.tsx)
│
├── StatsBarInventaire (src/components/epicerie/inventaire/StatsBarInventaire.tsx)
│   ├── StatCard "Total articles"   (total_articles)
│   ├── StatCard "Ruptures"         (nb_ruptures — badge rouge)
│   ├── StatCard "Stock bas"        (nb_stock_bas — badge orange)
│   └── StatCard "Valeur stock"     (valeur_stock_cts / 100 XPF)
│
├── OngletVueStock (src/components/epicerie/inventaire/OngletVueStock.tsx)
│   ├── StockToolbar
│   │   ├── SearchBarStock          — debounce 300ms, ?search=
│   │   ├── FiltreCategorie         — ?categorie=
│   │   ├── FiltreFournisseur       — ?fournisseur=
│   │   ├── CheckboxIsLow           — ?is_low=true
│   │   ├── CheckboxIsEmpty         — ?is_empty=true
│   │   └── ToggleVue               — tableau / cartes (local)
│   └── TableauStock / GrilleCartes
│       └── LigneStock / CarteStock
│             ├── CelluleStatutBadge     — ok / bas / rupture
│             ├── CelluleSeuilEditable   — inline PUT /seuil
│             └── BoutonAjuster         → AjustementStockModal
│
├── AjustementStockModal (src/components/epicerie/inventaire/AjustementStockModal.tsx)
│   ├── TypeMouvementGrid           — 4 boutons : Entrée | Sortie | Correction | Perte
│   ├── QuantiteControl             — input float + boutons −/+
│   ├── RaisonInput                 — string libre facultatif
│   └── BoutonEnregistrer           — POST /stock/ajustement + toast
│
├── OngletComptage (src/components/epicerie/inventaire/OngletComptage.tsx)
│   ├── BarreProgressionComptage    — "X / total_articles comptés"
│   ├── NotesGlobalesInput          — obligatoire avant validation
│   ├── TableComptage
│   │   └── LigneComptage
│   │         ├── ColStockSysteme   — lecture seule (quantite actuelle)
│   │         ├── ColQuantiteInput  — float, step=0.1
│   │         ├── ColEcart          — calculé local, coloré
│   │         └── ColNotesLigne     — textarea facultatif
│   ├── BoutonReinitialiser         — reset tous les inputs localement
│   └── BoutonValiderInventaire     — POST /stock/comptage (activé si notes + ≥1 écart)
│
└── OngletHistorique (src/components/epicerie/inventaire/OngletHistorique.tsx)
    ├── FiltresHistorique
    │   ├── FiltreProduit           — search produit_id
    │   ├── FiltreTypeMouvement     — select type
    │   ├── DateDebutPicker
    │   └── DateFinPicker
    └── TableMouvements
        └── LigneMouvement
              ├── BadgeType         — ENTREE (vert) | SORTIE (orange) | AJUSTEMENT (bleu) | PERTE (rouge) | VENTE (vert épicerie) | TRANSFERT_RESTAURANT (violet)
              ├── ColQuantiteSignee — `signed_quantite` formaté (+/−)
              └── ColReference      — reference (lien traçabilité)
```

---

## 6. Références ADR

| ADR | Règle |
|-----|-------|
| **ADR-14** | `epicerie_stock.quantite` lu directement en DB, jamais en cache Redis |

---

## 7. Codes d'erreur métier

| HTTP | Code | Déclencheur |
|------|------|-------------|
| 422 | `STOCK_NEGATIF` | `nouveau_stock < 0` après ajustement |
| 404 | `PRODUIT_NOT_FOUND` | `produit_id` inconnu ou cross-tenant |
| 422 | `COMPTAGE_VIDE` | `POST /comptage` avec `lignes = []` |
| 422 | `NOTES_OBLIGATOIRES` | `POST /comptage` sans `notes` global |

---

## 8. Gaps résolus lors de cette cross-validation

| # | Gap identifié | Décision |
|---|---------------|---------|
| G1 | "Inventaire" UI vs `AJUSTEMENT` API | Bouton UI renommé **"Correction"** — mapping documenté dans la section types |
| G2 | Notes comptage absentes du mockup | Ajoutées : `notes` global **obligatoire** + `lignes[].notes` facultatif |
| G3 | Sélection articles pour comptage | `GET /stock?per_page=1000` — comptage de tous les articles actifs |
| G4 | Filtres historique incomplets | 3 filtres ajoutés : produit (search), date_debut, date_fin |
| G5 | Seuil alerte non éditable | Édition inline sur cellule "Stock mini" → `PUT /stock/{id}/seuil` |
| G6 | Boutons "Nouvel article" et "Exporter" | Hors scope page Inventaire — placeholders roadmap |
| G7 | `GET /stock/stats` non utilisé | Barre de stats ajoutée en haut de page (4 indicateurs clés) |
