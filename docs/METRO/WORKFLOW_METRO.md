# Workflow ETL METRO - Factures Fournisseur

## MassaCorp - NOUTAM SAS & L'Incontournable

---

## 1. Vue d'ensemble

Ce workflow traite les factures PDF du fournisseur METRO selon l'architecture **SID CIF** (Corporate Information Factory).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WORKFLOW ETL METRO                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FACTURES PDF           STAGING              ODS                 DWH        │
│  ┌───────────┐        ┌─────────┐        ┌─────────┐        ┌─────────┐    │
│  │ /docs/    │        │ stg_    │        │ ods_    │        │ fait_   │    │
│  │ METRO/    │──[1]──▶│facture_ │──[2]──▶│facture_ │──[3]──▶│ achats  │    │
│  │ *.pdf     │Extract │ ligne   │ Valid. │ ligne   │ Histor.│         │    │
│  └───────────┘        └─────────┘ Trans. └─────────┘        └─────────┘    │
│       │                    │                  │                   │        │
│       │                    │                  │                   │        │
│       ▼                    ▼                  ▼                   ▼        │
│   ~100+ PDFs          Données brutes    Données métier      Historique    │
│   Téléchargement(8)   7-30 jours        1-3 mois            10+ ans       │
│   Téléchargement(9)                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Structure des fichiers

### 2.1 Arborescence

```
MassaCorp/
├── docs/
│   └── METRO/
│       ├── WORKFLOW_METRO.md          # Cette documentation
│       ├── Téléchargement(8)/         # Factures 2023
│       │   └── 135_*.pdf              # ~100 factures
│       └── Téléchargement(9)/         # Factures 2024
│           └── 135_*.pdf              # ~50 factures
│
└── etl/
    └── metro/
        ├── extract_metro_pdf.py       # Extracteur PDF
        ├── run_pipeline.py            # Orchestrateur principal
        └── sql/
            ├── 01_schema_staging.sql  # Tables staging
            ├── 02_validation.sql      # Règles validation
            ├── 03_transformation_ods.sql  # Transfo ODS
            ├── 04_chargement_dwh.sql  # Chargement DWH
            └── 05_audit_monitoring.sql # Audit
```

### 2.2 Nomenclature des fichiers PDF

Pattern: `{client}_{magasin}_{numero}_{datetime}_invoice_cus_copy_main.pdf`

| Segment | Description | Exemple |
|---------|-------------|---------|
| client | Code client METRO | 135 |
| magasin | Code magasin | 11, 12, 15, 16, 21, 25, 26 |
| numero | Numéro séquentiel | 299014 |
| datetime | Date/heure impression | 20240607121530 |

Magasins identifiés:
- 11: METRO LA CHAPELLE
- 12: METRO GENNEVILLIERS
- 15: METRO VILLENEUVE
- 16: METRO IVRY
- 21: METRO AULNAY
- 25: METRO NANTERRE
- 26: METRO ÉVRY

---

## 3. Pipeline ETL

### 3.1 Étape 1 : EXTRACTION

**Script**: `etl/metro/extract_metro_pdf.py`

**Entrée**: Fichiers PDF METRO
**Sortie**: `staging.stg_facture_ligne`

```bash
# Extraction vers JSON (mode autonome)
python extract_metro_pdf.py --input /docs/METRO --output staging.json

# Extraction vers DB
python extract_metro_pdf.py --input /docs/METRO --db postgresql://user:pass@localhost/massacorp
```

**Données extraites**:

| Champ | Source PDF | Exemple |
|-------|------------|---------|
| numero_facture | En-tête | 0/0(135)0011/021323 |
| numero_interne | En-tête | 011-299014 |
| date_facture | En-tête | 2024-06-07 |
| client_numero | En-tête | 135 00712188 |
| ean | Ligne article | 5099873089057 |
| designation | Ligne article | WH JACK DANIEL'S 40D 35CL |
| categorie_source | Section | SPIRITUEUX |
| vol_alcool | Ligne | 40.0 |
| prix_unitaire | Ligne | 9.34 |
| quantite | Ligne | 2 |
| montant_ligne | Ligne | 18.68 |
| code_tva | Ligne | D |

---

### 3.2 Étape 2 : NETTOYAGE & VALIDATION

**Script SQL**: `sql/02_validation.sql`

#### Règles de nettoyage (N1-N6)

| Code | Règle | Action |
|------|-------|--------|
| N1 | Trim espaces | `TRIM(designation)` |
| N2 | Majuscules catégorie | `UPPER(categorie_source)` |
| N3 | Normalisation fournisseur | → "METRO France" |
| N4 | Déduction régie | SPIRITUEUX → 'S' |
| N5 | Enrichissement TVA | code_tva → taux_tva |
| N6 | Calcul montant | prix × quantité |

#### Règles de validation (V1-V10)

| Code | Règle | Sévérité |
|------|-------|----------|
| V1 | Numéro facture obligatoire | Bloquant |
| V2 | Date facture valide | Bloquant |
| V3 | Montant cohérent (prix × qté) | Warning |
| V4 | Format EAN (8 ou 13 chiffres) | Warning |
| V5 | TVA cohérente avec régie | Warning |
| V6 | Degré alcool pour alcools | Warning |
| V7 | Quantité positive | Bloquant |
| V8 | Prix unitaire positif | Warning |
| V9 | Désignation non vide | Warning |
| V10 | Taux TVA standard | Warning |

```sql
-- Exécution validation
SELECT * FROM staging.valider_facture_lignes('batch-id-uuid');

-- Rapport validation
SELECT * FROM staging.rapport_validation('batch-id-uuid');
```

---

### 3.3 Étape 3 : TRANSFORMATION ODS

**Script SQL**: `sql/03_transformation_ods.sql`

**Calculs métier appliqués**:

| Calcul | Formule | Description |
|--------|---------|-------------|
| montant_tva | `montant_ht × taux_tva / 100` | TVA calculée |
| montant_ttc | `montant_ht × (1 + taux_tva/100)` | TTC |
| prix_au_litre | `prix_unitaire / volume` | Prix normalisé |
| volume_alcool_pur | `qté × vol × degré / 100` | VAP total |
| est_alcool | `regie IN ('S','B','M','T')` | Flag alcool |

```sql
-- Transformation
SELECT * FROM staging.transformer_vers_ods('batch-id-uuid');
-- Retourne: (nb_entetes, nb_lignes, montant_total_ht)
```

---

### 3.4 Étape 4 : HISTORISATION DWH

**Script SQL**: `sql/04_chargement_dwh.sql`

**Tables cibles**:
- `dwh.fait_achats` : Faits (granularité ligne facture)
- `dwh.dim_produit` : Dimension produit (SCD Type 2)
- `dwh.dim_fournisseur` : Dimension fournisseur (SCD Type 2)
- `dwh.dim_categorie_produit` : Dimension catégorie

```sql
-- Chargement DWH
CALL dwh.charger_faits_achats('2024-01-01', '2024-12-31');

-- Création produits depuis ODS
SELECT dwh.creer_produit_depuis_ods('batch-id-uuid');
```

---

## 4. Exécution du Pipeline

### 4.1 Commande complète

```bash
# Pipeline complet
python etl/metro/run_pipeline.py \
    --input /docs/METRO \
    --db postgresql://user:pass@localhost/massacorp

# Mode dry-run (sans chargement DWH)
python etl/metro/run_pipeline.py \
    --input /docs/METRO \
    --db postgresql://... \
    --dry-run

# Reprise depuis staging existant
python etl/metro/run_pipeline.py \
    --batch-id abc12345 \
    --skip-extraction \
    --db postgresql://...
```

### 4.2 Options

| Option | Description |
|--------|-------------|
| `--input, -i` | Répertoire des PDFs (requis) |
| `--db` | Connection string PostgreSQL |
| `--batch-id` | ID de batch (généré si absent) |
| `--dry-run` | Pas de chargement DWH |
| `--skip-extraction` | Réutiliser staging existant |
| `--skip-dwh` | Pas de chargement DWH |
| `--verbose, -v` | Mode verbeux |

### 4.3 Sortie

```
============================================================
PIPELINE ETL METRO - Batch a1b2c3d4-e5f6-...
Input: /docs/METRO
Dry run: False
============================================================
[1] EXTRACTION - DÉBUT
[1] EXTRACTION - SUCCESS ({'fichiers': 150, 'factures': 150, 'lignes': 2340})
[2] NETTOYAGE - DÉBUT
[2] NETTOYAGE - SUCCESS (...)
[3] VALIDATION - DÉBUT
[3] VALIDATION - SUCCESS ({'valides': 2280, 'erreurs': 60, 'taux': '97.4%'})
...
============================================================
RÉSUMÉ PIPELINE
============================================================
Statut: SUCCESS
Durée: 45.2s
Fichiers traités: 150
Factures: 150
Lignes extraites: 2340
Lignes validées: 2280
Lignes en erreur: 60
Lignes ODS: 2280
Lignes DWH: 2280
Montant HT: 125430.50€
============================================================
```

---

## 5. Monitoring & Audit

### 5.1 Vues de monitoring

```sql
-- Exécutions récentes
SELECT * FROM etl.v_executions_recentes;

-- Stats journalières
SELECT * FROM etl.v_stats_journalieres;

-- Erreurs fréquentes
SELECT * FROM etl.v_erreurs_frequentes;

-- Qualité données
SELECT * FROM etl.v_qualite_donnees;
```

### 5.2 Rapports

```sql
-- Rapport batch
SELECT * FROM staging.rapport_validation('batch-id');

-- Colonnes manquantes
SELECT * FROM staging.v_colonnes_manquantes WHERE batch_id = 'batch-id';

-- Résumé batch
SELECT * FROM staging.v_batch_summary;
```

---

## 6. Data Marts

### 6.1 ODS (Oper Marts - Tactique)

| Vue | Description |
|-----|-------------|
| `ods.v_factures_a_valider` | Factures en attente |
| `ods.v_achats_par_categorie` | Agrégation par catégorie/mois |
| `ods.v_top_produits` | Top produits par volume |

### 6.2 DWH (Data Marts - Stratégique)

| Vue | Description |
|-----|-------------|
| `dwh.v_analyse_achats_fournisseur` | Analyse fournisseur/catégorie |
| `dwh.v_evolution_prix_produit` | Historique prix (SCD2) |

---

## 7. Maintenance

### 7.1 Nettoyage staging

```sql
-- Purge données > 30 jours
SELECT * FROM etl.nettoyer_staging(30);
```

### 7.2 Dépendances Python

```bash
pip install pdfplumber psycopg2-binary
```

### 7.3 Initialisation DB

```bash
# Exécuter les scripts SQL dans l'ordre
psql -d massacorp -f etl/metro/sql/01_schema_staging.sql
psql -d massacorp -f etl/metro/sql/02_validation.sql
psql -d massacorp -f etl/metro/sql/03_transformation_ods.sql
psql -d massacorp -f etl/metro/sql/04_chargement_dwh.sql
psql -d massacorp -f etl/metro/sql/05_audit_monitoring.sql
```

---

## 8. Mapping Catégories METRO → DWH

| Régie | Catégorie METRO | Code DWH | Famille |
|-------|-----------------|----------|---------|
| S | SPIRITUEUX | ALC_SPIRITUEUX | Boissons / Alcool fort |
| B | BRASSERIE | ALC_BIERE | Boissons / Bière |
| M | CHAMPAGNES | ALC_CHAMPAGNE | Boissons / Vin effervescent |
| T | CAVE | ALC_VIN | Boissons / Vin |
| E | EPICERIE SECHE | ALI_EPICERIE | Alimentation / Épicerie |
| F | SURGELES | ALI_FRAIS | Alimentation / Frais |
| D | DROGUERIE | NON_ALI_DROGUERIE | Non alimentaire |

---

## 9. Diagramme de flux

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           FLUX ETL METRO                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   [PDF METRO]                                                            │
│       │                                                                  │
│       ▼                                                                  │
│   ┌────────────────┐                                                     │
│   │  EXTRACTION    │  pdfplumber                                         │
│   │  PDF → JSON    │  extract_metro_pdf.py                               │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │   STAGING      │  staging.stg_facture_ligne                          │
│   │   Données      │  Rétention: 7-30 jours                              │
│   │   brutes       │                                                     │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │  NETTOYAGE     │  staging.nettoyer_facture_lignes()                  │
│   │  N1-N6         │  Trim, normalisation, enrichissement                │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │  VALIDATION    │  staging.valider_facture_lignes()                   │
│   │  V1-V10        │  Règles métier, cohérence                           │
│   └───────┬────────┘                                                     │
│           │                                                              │
│       ┌───┴───┐                                                          │
│       │       │                                                          │
│       ▼       ▼                                                          │
│   [VALIDE] [ERREUR]──────▶ Rapport erreurs                               │
│       │                                                                  │
│       ▼                                                                  │
│   ┌────────────────┐                                                     │
│   │ TRANSFORMATION │  staging.transformer_vers_ods()                     │
│   │ Calculs métier │  TVA, TTC, prix/L, VAP                              │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │     ODS        │  ods.ods_facture_ligne                              │
│   │   Données      │  ods.ods_facture_entete                             │
│   │   tactiques    │  Rétention: 1-3 mois                                │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │ HISTORISATION  │  dwh.charger_faits_achats()                         │
│   │  SCD Type 2    │  dwh.scd2_update_produit()                          │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │     DWH        │  dwh.fait_achats                                    │
│   │   Données      │  dwh.dim_produit (SCD2)                             │
│   │  stratégiques  │  dwh.dim_fournisseur (SCD2)                         │
│   │                │  Rétention: 10+ ans                                 │
│   └───────┬────────┘                                                     │
│           │                                                              │
│           ▼                                                              │
│   ┌────────────────┐                                                     │
│   │  DATA MARTS    │  dwh.v_analyse_achats_fournisseur                   │
│   │  Vues agrégées │  dwh.v_evolution_prix_produit                       │
│   │  pour BI       │  ods.v_achats_par_categorie                         │
│   └────────────────┘                                                     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

*Document généré le 2026-01-02*
*MassaCorp - NOUTAM SAS & L'Incontournable*
