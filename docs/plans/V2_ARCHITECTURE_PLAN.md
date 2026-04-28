# V2 Architecture Plan — Domaines Alimentaires
# Version: 1.3
# Statut: Validé — Restaurant + Finance V2 + cross-domaine intégrés (session 2026-03-08)
# Portée: catalogue + épicerie + restaurant + approvisionnement

---

## §1 — Périmètre V2

### Ce qui est ajouté

Trois nouveaux domaines métier s'intègrent dans la plateforme existante
(tenant_id=1 = location vaisselle) sans rupture des invariants existants :

| Domaine             | Tenant | Nature |
|---------------------|--------|--------|
| Catalogue produits  | —      | Référentiel ETL partagé (aucun tenant_id) |
| Fournisseurs alim   | —      | Référentiel partagé (METRO, TAIYAT, EUROCIEL…) |
| Épicerie            | 2      | Entité légale indépendante |
| Restaurant          | 3      | Entité légale indépendante |
| Approvisionnement   | 2 ou 3 | Commandes fournisseurs par tenant |
| Transferts internes | —      | Document légal inter-entreprises (facture réelle) |

### Ce qui NE change PAS

- Les modèles existants (location, auth, MFA, RBAC) restent intacts.
- Les tenants existants (tenant_id=1) ne sont pas touchés par les migrations V2.
- Le `BaseRepository` et `AsyncBaseRepository` existants sont réutilisés tels quels.

---

## §2 — ADR (Architectural Decision Records)

### ADR-01 — Catalogue produits sans tenant_id

**Décision** : `catalogue_produits` n'a pas de `tenant_id`.

**Justification** : C'est un référentiel technique ETL (METRO/TAIYAT/EUROCIEL),
pas un catalogue commercial. Il normalise les désignations produits par EAN.
Ni l'épicerie ni le restaurant ne le "possèdent" — ils y font référence.
Les produits sans EAN (maison) y ont également une entrée avec `ean=NULL`.

**Contrainte** : Aucun endpoint public ne l'expose directement.
L'accès se fait uniquement via `articles_epicerie` (tenant_id=2)
ou `ingredients` (tenant_id=3).

**Alternative rejetée** : tenant_id=2 (épicerie possède le catalogue) — rejetée
car le restaurant consomme les mêmes fournisseurs et les mêmes EAN.

---

### ADR-02 — Fournisseurs alimentaires sans tenant_id

**Décision** : `fournisseurs_alim` n'a pas de `tenant_id`.

**Justification** : METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM approvisionnent
les deux entités. Dupliquer la table par tenant crée une désynchronisation
des données fournisseurs et des EAN.

**Contrainte** : Les `commandes_fournisseurs` et `lignes_commande_fournisseur`
ont bien un `tenant_id` (qui commande ?).

---

### ADR-03 — Transferts internes sans tenant_id, sans FK cross-tenant

**Décision** : `transferts_internes` n'a pas de `tenant_id`.
Les mouvements de stock de chaque tenant référencent `transfert_interne_id`
comme entier brut (pas de FK DB).

**Justification** : Le transfert interne est un document légal unique représentant
une facture réelle entre deux sociétés. Il n'appartient à aucun des deux.
Chaque tenant enregistre son propre mouvement de stock avec le `transfert_interne_id`
pour la traçabilité comptable — sans violer l'isolation multi-tenant.

**Flow validé** :
1. L'épicerie (tenant_id=2) crée le `transfert_interne` (document légal).
2. L'épicerie crée immédiatement son `mouvement_stock_epicerie` (sortie).
3. L'épicerie crée immédiatement le `mouvement_stock_restaurant` (entrée côté restaurant).
4. Deux transactions DB séparées. Pas de statut "en attente" côté restaurant.
5. En cas d'échec de l'étape 3 : compensation applicative (annulation de l'étape 2
   et marquage du transfert en erreur).

**Qui peut créer** : `manager` ou `admin` des deux côtés (tenant_id=2 ou 3).

**Contrainte** : L'intégrité référentielle est applicative, pas DB.
Le service vérifie l'existence du `transfert_interne_id` avant insertion.

---

### ADR-04 — Sous-dossiers domaine dans app/models/

**Décision** : Organisation en sous-domaines :

```
app/
  models/
    catalogue/          # catalogue_produits.py, etl_import.py
    epicerie/           # article_epicerie.py, stock_epicerie.py, vente_epicerie.py
    restaurant/         # menu.py, plat.py, ingredient.py, stock_restaurant.py
    approvisionnement/  # fournisseur_alim.py, commande_fournisseur.py, ligne_commande.py
    finance/            # transfert_interne.py (document légal)
  repositories/
    catalogue/
    epicerie/
    restaurant/
    approvisionnement/
  services/
    catalogue/
    epicerie/
    restaurant/
    approvisionnement/
  api/
    v1/
      catalogue/
      epicerie/
      restaurant/
      approvisionnement/
  constants/
    epicerie.py
    restaurant.py
    approvisionnement.py
```

**Justification** : Cohérence avec la complexité ajoutée. Chaque domaine
est isolé et peut évoluer indépendamment. Évite la pollution de
`app/models/` plat qui existe déjà pour location.

---

### ADR-05 — Catégorisation produits = table de référence (50 entrées, 3 niveaux)

**Décision** : La catégorisation n'est PAS un Enum Python. C'est une table
de référence `categories_produit` sans tenant_id, seedée par migration Alembic,
avec la hiérarchie complète en 3 niveaux : Famille > Catégorie > Sous-catégorie.

**Source** : `MassaCorp/db/sql/categories_epicerie.sql` — 50 catégories existantes,
validées en production. Transposées telles quelles dans FUTUR PROJ.

**Pourquoi une table et non un Enum ?**
- 50 valeurs = trop pour un `CheckConstraint` lisible
- La hiérarchie (famille > catégorie > sous-catégorie) doit être requêtable
- Le `tva_defaut` par catégorie est une donnée métier (pas du code)
- Le flag `est_ingredient_resto` résout nativement le lien épicerie→restaurant
  sans FK cross-tenant (voir ADR-06)

**Structure `categories_produit`** :
```
categories_produit (sans tenant_id)
  id                  PK
  code                VARCHAR(20)   UNIQUE NOT NULL  -- 'EPIC_PATE', 'ALC_BIERE'...
  nom                 VARCHAR(100)  NOT NULL
  famille             VARCHAR(50)   NOT NULL          -- niveau 1
  categorie           VARCHAR(50)   NOT NULL          -- niveau 2
  sous_categorie      VARCHAR(50)                     -- niveau 3 (nullable)
  tva_defaut          FLOAT         NOT NULL          -- 0.055 ou 0.20
  ordre_famille       INT           DEFAULT 99
  ordre_categorie     INT           DEFAULT 99
  est_ingredient_resto BOOLEAN      NOT NULL DEFAULT false
  priorite_ingredient INT           DEFAULT 0        -- 1=haute, 2=moyenne, 3=basse
  is_active           BOOLEAN       NOT NULL DEFAULT true
  created_at / updated_at
```

**Familles (12 familles, 50 catégories)** :
```
Boissons           → 15 catégories (sans alcool, chaudes, alcools)
Produits Laitiers  →  6 catégories (laits, crèmes, beurres, fromages, yaourts, desserts)
Épicerie Salée     → 13 catégories (féculents, conserves, condiments)
Épicerie Sucrée    → 11 catégories (petit-déj, biscuits, pâtisserie, confiseries)
Produits Frais     → 13 catégories (viandes, charcuterie, poissons, œufs)
Surgelés           →  5 catégories (légumes, viandes, poissons, pâtisserie, glaces)
Boulangerie        →  3 catégories (pains, brioches, viennoiseries)
Fruits & Légumes   →  4 catégories (fruits, légumes, aromates, salades)
Produits du Monde  →  5 catégories (Afrique, Asie, Orient, Amérique, Halal)
Snacking           →  3 catégories (chips, fruits secs, biscuits apéro)
Hygiène/Entretien  →  5 catégories (TVA 20%)
Consommables Pro   →  5 catégories (TVA 20%)
Divers             →  1 catégorie  (fallback)
```

**Lien avec `catalogue_produits`** :
`catalogue_produits.categorie_code` → FK vers `categories_produit.code`

**Lien avec `ingredients` (restaurant)** :
Le service de transfert filtre `categories_produit.est_ingredient_resto = TRUE`
pour valider qu'un article épicerie peut devenir un ingrédient restaurant.

**Migration** : M00 (avant tout le reste, aucune dépendance).
Seedée via `data_migrations/seed_categories_produit.py` dans la même migration.

---

### ADR-06-BIS — TVA par catégorie, pas par article

**Décision** : Le `tva_rate` d'un `article_epicerie` est initialisé depuis
`categories_produit.tva_defaut` à la création. Il peut être surchargé
par ligne si nécessaire (ex: boisson alcoolisée à 20% dans un rayon épicerie).

**Justification** : Évite d'avoir à saisir le taux TVA manuellement pour chaque
article — la règle fiscale française est portée par la catégorie.

---

### ADR-08 — ETL parsers = scripts admin via Celery

**Décision** : Les parsers ETL (METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM)
sont dans `scripts/etl/`. Les imports sont déclenchés via Celery
(tâche asynchrone longue), pas via endpoint REST direct.

**Justification** : Import de factures = opération volumineuse, sans contrainte
de latence réponse. Celery permet le retry, le dead-letter, et l'idempotence.
Accès réservé : `super_admin` et `platform_ops` uniquement.

**Structure** :
```
scripts/
  etl/
    parsers/
      metro.py        # pdfplumber + coordonnées
      taiyat.py       # regex
      eurociel.py     # regex, 1 PDF = N factures
      ethan.py        # XLSX
      gnanam.py       # Excel + OCR
    import_pipeline.py  # orchestration + transaction atomique
app/
  tasks/
    etl_tasks.py      # Celery tasks wrappant import_pipeline
```

---

### ADR-06 — Lien épicerie → restaurant via catalogue partagé

**Décision** : La table `ingredients` (restaurant, tenant_id=3) a une FK vers
`catalogue_produits.id` et un `facteur_conversion`.

Le restaurant reçoit ses ingrédients de l'épicerie via `transferts_internes`.
Pas de FK directe `ingredients.article_epicerie_id` — le lien se fait via
`catalogue_produits.id` partagé.

**Justification** : Évite le couplage cross-tenant. Le restaurant ne connaît
pas les `articles_epicerie` directement.

---

### ADR-07 — Déduplication catalogue produits (algorithme profond)

**Décision** : La déduplication lors de l'import ETL suit cette hiérarchie :

```
1. Si EAN présent et valide (longueur 8 ou 13) :
   a. Chercher une entrée catalogue avec le même EAN.
   b. Si trouvé → mettre à jour la désignation/marque si vide.
   c. Si non trouvé → créer.

2. Si EAN absent ou invalide (produits TAIYAT, maison) :
   a. Normaliser la désignation :
      - lowercase, strip accents, strip ponctuation
      - supprimer mots vides (le, la, les, de, du, des, en, au)
      - tronquer à 80 chars de la désignation normalisée
   b. Chercher une entrée avec désignation_normalisée ≥ 0.85 similarité
      (algorithme Jaro-Winkler ou token_set_ratio via rapidfuzz).
   c. Si match > 0.85 → considérer comme même produit → logger le match douteux.
   d. Si < 0.85 → créer une nouvelle entrée.

3. Conflit EAN cross-fournisseur (ex: Coca EAN pays différent) :
   - Pas d'erreur bloquante.
   - Créer une entrée distincte avec (ean, source_fournisseur) comme
     clé composite dans etl_conflicts (table de log).
   - Le catalogue conserve les deux entrées — résolution manuelle possible.
```

**Contrainte** : `rapidfuzz` à ajouter en dépendance.

---

### ADR-09 — Restaurant : modèle deux niveaux de stock

**Décision** : Le domaine restaurant modélise deux niveaux de stock distincts :
1. **Ingrédients bruts** (`ingredients`, tenant_id=3) — ce qui est acheté/reçu.
2. **Préparations** (`instances_preparation`, tenant_id=3) — ce qui est cuisiné (marmite).

**Types de préparation** (`types_preparation`) = la recette template (portions_par_batch).
**Instance de préparation** (`instances_preparation`) = la marmite réelle du jour, quantifiée
en portions (ex: marmite sauce tomate = 20 portions).

**Flux de consommation** :
- *Cuisine* : saisie manuelle au démarrage → crée une instance + décrémente les ingrédients
  via `mouvements_stock_restaurant` (type=consommation).
- *Vente* : confirmation ligne commande → décrémente `instances_preparation.portions_restantes`
  + décrémente l'ingrédient protéine (`variantes_plat.ingredient_proteine_id`)
  + décrémente le side si `sides.ingredient_id IS NOT NULL`.
- *Calcul à rebours* : tâche Celery nocturne OU déclenchement manuel — réconcilie les
  portions consommées vs ventes réelles.

**Une instance peut servir plusieurs variantes** :
La marmite "sauce tomate" sert "X poulet", "X bœuf", "X crevette" sans distinction.
Le lien est via `variantes_plat.type_preparation_id` (pas vers l'instance directement).
Le service de vente sélectionne l'instance disponible du bon type au moment de la commande.

---

### ADR-10 — Sides : liste fixe avec tracking stock optionnel

**Décision** : Les sides (accompagnements) sont une liste fixe par tenant dans la table
`sides`. Chaque side peut être optionnellement lié à un `ingredient_id` avec une
`quantite_par_portion` pour déclencher un mouvement de stock à la vente.

- Side sans lien ingredient (ex: "riz blanc" géré en vrac) : affiché sur la commande, non
  décrémenté.
- Side avec lien ingredient (ex: "frites" → ingredient=pommes de terre, 200g/portion) :
  la confirmation de commande décrémente automatiquement l'ingrédient.

---

### ADR-11 — Finance V2 : 3 tables distinctes (documents sources uniquement)

**Décision** : Le module Finance V2 contient des documents sources, sans écritures
comptables débit/crédit. 3 tables distinctes :
1. `transferts_internes` — document inter-entreprises (§6.9, déjà modélisé).
2. `factures_achats` — factures fournisseurs (METRO, TAIYAT, importées par ETL ou saisies).
3. `ventes_epicerie` + `lignes_vente_epicerie` — ventes au comptoir de l'épicerie.

**Séparation stricte** : Aucune table partagée avec le module Finance location (tenant_id=1).
L'intégration comptable complète (plan comptable, rapprochement bancaire) est hors scope V2.

---

### ADR-12 — alertes_stock : table persistante avec historique

**Décision** : Les alertes stock sont stockées dans `alertes_stock` (append-only,
avec `resolu_at` pour marquer la résolution).

**Déclenchement** :
- `stock_actuel <= stock_alerte` → `seuil_type='bas'` (notification + dashboard).
- `stock_actuel = 0` → `seuil_type='zero'` (alerte critique "élément manquant").

**Fournisseur non nominatif** : L'alerte ne crée PAS de commande fournisseur automatique.
Les fournisseurs (METRO, TAIYAT, EUROCIEL…) proposent souvent les mêmes articles.
La liste "éléments manquants" est présentée à l'opérateur pour décision manuelle.

---

### ADR-13 — prix_fournisseur_historique : coût exact à date J

**Décision** : Table `prix_fournisseur_historique` sans tenant_id, alimentée par l'ETL
à chaque import de facture. Clé unique `(catalogue_id, fournisseur_id, date_prix)`.

**Usage** : Calcul du prix de revient d'une préparation au moment exact de sa confection
(date_cuisine de l'instance). Requête : `WHERE catalogue_id = X AND date_prix <= :date
ORDER BY date_prix DESC LIMIT 1` → prix en vigueur à J.

---

### ADR-14 — Cache V2 : stock jamais en cache

**Décision** :
- `stock_actuel`, `portions_restantes` : **lecture directe DB**, jamais en cache Redis.
- `categories_produit` : cache Redis TTL 24h, invalidé uniquement par migration Alembic.

**Justification** : La fraîcheur du stock est critique pour éviter les surventes et les
erreurs de consommation de portions. Un cache stock périmé = débit sur une valeur fausse.

---

## §3 — Stratégie Async (Règle Définitive V2)

| Opération | Pattern | Justification |
|-----------|---------|---------------|
| Création (POST) | `AsyncBaseRepository` | I/O non-blocking, idempotent réseau |
| Suppression (DELETE, soft) | `AsyncBaseRepository` | Idem |
| Lecture (GET, liste) | `AsyncBaseRepository` | Tous les repos V2 = async |
| Modification (PUT, PATCH) | `BaseRepository` (sync) | Souvent lié à validations chaînées |
| Import ETL | Celery task | Long-running, retry, dead-letter |

**Règle** : Tous les nouveaux repositories V2 héritent de `AsyncBaseRepository`.
Les méthodes `update()` restent synchrones par défaut (pattern BaseRepository).

---

## §4 — RBAC V2 (Règle Définitive)

### Multi-rôles par user

Un user peut avoir des rôles différents par tenant :
- `user_roles(user_id=X, tenant_id=2, role=manager)` — épicerie
- `user_roles(user_id=X, tenant_id=3, role=staff)` — restaurant

Ceci est déjà supporté par l'index partiel existant
`uq_user_roles_active_per_tenant` sur `(user_id, tenant_id) WHERE revoked_at IS NULL`.

### Mapping rôle → droits V2

| Action | Rôle minimum requis | Tenant |
|--------|---------------------|--------|
| Lecture catalogue | staff | 2 ou 3 |
| Lecture articles épicerie | staff | 2 |
| Écriture articles épicerie | manager | 2 |
| Gestion commandes fournisseurs | manager | 2 ou 3 |
| Création transfert interne | manager ou admin | 2 ou 3 |
| Lecture ingrédients restaurant | staff | 3 |
| Écriture ingrédients restaurant | manager | 3 |
| Import ETL | super_admin ou platform_ops | — |

**Principe** : Réutilisation du mapping `manager → write` existant par tenant.
Pas de nouveaux scopes applicatifs — le rôle + tenant_id suffit.

---

## §5 — MFA / TOTP V2 (Règle Définitive)

### Memberships multi-tenant

Chaque user a un `tenant_membership` **distinct par tenant** auquel il appartient.
Un user membre de l'épicerie ET du restaurant a deux `tenant_memberships`
et potentiellement deux `MFADevice` distincts.

### Obligation MFA V2

MFA **optionnel mais conseillé** pour les tenants 2 et 3.
Pas de `mfa_required=True` forcé pour les nouveaux rôles V2.

### Onboarding

À la création d'un membership sur tenant_id=2 ou 3, le service crée
automatiquement un `MFADevice` avec `is_enabled=False` (état "en attente").
Le user active ensuite via le flow TOTP setup existant.

---

## §6 — Modèles de données V2

### §6.0 — categories_produit (référentiel, sans tenant_id) — M00

```sql
CREATE TABLE categories_produit (
  id                   SERIAL PRIMARY KEY,
  code                 VARCHAR(20)  NOT NULL UNIQUE,
  nom                  VARCHAR(100) NOT NULL,
  famille              VARCHAR(50)  NOT NULL,
  categorie            VARCHAR(50)  NOT NULL,
  sous_categorie       VARCHAR(50),
  tva_defaut           FLOAT        NOT NULL DEFAULT 0.20,
  ordre_famille        INT          NOT NULL DEFAULT 99,
  ordre_categorie      INT          NOT NULL DEFAULT 99,
  est_ingredient_resto BOOLEAN      NOT NULL DEFAULT false,
  priorite_ingredient  INT          NOT NULL DEFAULT 0,
  is_active            BOOLEAN      NOT NULL DEFAULT true,
  created_at           TIMESTAMP    NOT NULL DEFAULT now(),
  updated_at           TIMESTAMP    NOT NULL DEFAULT now()
);
-- Seedée via data_migrations/seed_categories_produit.py dans la migration M00
CREATE INDEX idx_categories_famille ON categories_produit(famille);
CREATE INDEX idx_categories_ingredient ON categories_produit(est_ingredient_resto)
  WHERE est_ingredient_resto = TRUE;
```

### §6.1 — catalogue_produits (partagé, sans tenant_id) — M01

```sql
CREATE TABLE catalogue_produits (
  id                  BIGSERIAL PRIMARY KEY,
  ean                 VARCHAR(20),
  designation         VARCHAR(300) NOT NULL,
  designation_norm    VARCHAR(300),           -- version normalisée pour déduplication
  marque              VARCHAR(100),
  unite_base          VARCHAR(20)  NOT NULL,  -- 'kg', 'L', 'piece', 'carton'
  conditionnement     VARCHAR(100),           -- '1 carton de 6'
  source_fournisseur  VARCHAR(50),            -- 'METRO', 'TAIYAT', etc.
  categorie_code      VARCHAR(20)  REFERENCES categories_produit(code),
  created_at          TIMESTAMP    NOT NULL DEFAULT now(),
  updated_at          TIMESTAMP    NOT NULL DEFAULT now(),
  CONSTRAINT uq_catalogue_ean UNIQUE (ean)   -- partiel WHERE ean IS NOT NULL
);
CREATE INDEX idx_catalogue_categorie ON catalogue_produits(categorie_code);
```

### §6.2 — fournisseurs_alim (partagé, sans tenant_id)

```sql
CREATE TABLE fournisseurs_alim (
  id                  BIGSERIAL PRIMARY KEY,
  nom                 VARCHAR(200) NOT NULL UNIQUE,
  code_fournisseur    VARCHAR(50) UNIQUE,      -- 'METRO', 'TAIYAT'
  type_facturation    VARCHAR(50),             -- 'pdf', 'xlsx', 'email'
  created_at          TIMESTAMP NOT NULL DEFAULT now(),
  updated_at          TIMESTAMP NOT NULL DEFAULT now()
);
```

### §6.3 — etl_imports (log technique, sans tenant_id)

```sql
CREATE TABLE etl_imports (
  id                  BIGSERIAL PRIMARY KEY,
  fournisseur_id      BIGINT REFERENCES fournisseurs_alim(id),
  fichier_nom         VARCHAR(500) NOT NULL,
  date_import         TIMESTAMP NOT NULL,
  nb_lignes           INTEGER DEFAULT 0,
  nb_nouveaux         INTEGER DEFAULT 0,
  nb_erreurs          INTEGER DEFAULT 0,
  statut              VARCHAR(20) NOT NULL,
  detail_erreurs      TEXT,
  created_at          TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_etl_statut CHECK (statut IN ('succes', 'partiel', 'echec'))
);
```

### §6.4 — etl_conflicts (log déduplication, sans tenant_id)

```sql
CREATE TABLE etl_conflicts (
  id                  BIGSERIAL PRIMARY KEY,
  ean                 VARCHAR(20),
  designation         VARCHAR(300),
  source_fournisseur  VARCHAR(50),
  catalogue_id_match  BIGINT REFERENCES catalogue_produits(id),
  score_similarite    FLOAT,
  resolution          VARCHAR(20) DEFAULT 'pending',  -- 'pending','merged','kept_separate'
  created_at          TIMESTAMP NOT NULL DEFAULT now()
);
```

### §6.5 — articles_epicerie (tenant_id=2)

```sql
CREATE TABLE articles_epicerie (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  catalogue_id          BIGINT REFERENCES catalogue_produits(id),
  reference_interne     VARCHAR(100) NOT NULL,
  libelle               VARCHAR(300) NOT NULL,
  categorie_code        VARCHAR(20) REFERENCES categories_produit(code),
  unite_vente           VARCHAR(20) NOT NULL,
  prix_achat_ht_cts     BIGINT NOT NULL DEFAULT 0,
  prix_vente_ht_cts     BIGINT NOT NULL DEFAULT 0,
  tva_rate              FLOAT NOT NULL DEFAULT 0.055,
  stock_actuel          BIGINT NOT NULL DEFAULT 0,
  stock_alerte          BIGINT NOT NULL DEFAULT 0,
  fournisseur_id        BIGINT REFERENCES fournisseurs_alim(id),
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_article_epicerie_tenant_ref UNIQUE (tenant_id, reference_interne),
  CONSTRAINT check_article_prix_achat CHECK (prix_achat_ht_cts >= 0),
  CONSTRAINT check_article_prix_vente CHECK (prix_vente_ht_cts >= 0),
  CONSTRAINT check_article_stock CHECK (stock_actuel >= 0)
);
CREATE INDEX idx_articles_epicerie_tenant ON articles_epicerie(tenant_id);
CREATE INDEX idx_articles_epicerie_catalogue ON articles_epicerie(catalogue_id);
CREATE INDEX idx_articles_epicerie_fournisseur ON articles_epicerie(fournisseur_id);
CREATE INDEX idx_articles_epicerie_categorie ON articles_epicerie(categorie_code);
```

### §6.6 — ingredients (tenant_id=3)

```sql
CREATE TABLE ingredients (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  catalogue_id          BIGINT REFERENCES catalogue_produits(id),
  nom                   VARCHAR(300) NOT NULL,
  unite_stock           VARCHAR(20) NOT NULL,
  facteur_conversion    FLOAT NOT NULL DEFAULT 1.0,
  stock_actuel          FLOAT NOT NULL DEFAULT 0.0,
  stock_alerte          FLOAT NOT NULL DEFAULT 0.0,
  cout_unitaire_cts     BIGINT NOT NULL DEFAULT 0,
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_ingredient_tenant_nom UNIQUE (tenant_id, nom),
  CONSTRAINT check_ingredient_stock CHECK (stock_actuel >= 0),
  CONSTRAINT check_ingredient_facteur CHECK (facteur_conversion > 0)
);
CREATE INDEX idx_ingredients_tenant ON ingredients(tenant_id);
CREATE INDEX idx_ingredients_catalogue ON ingredients(catalogue_id);
```

### §6.7 — commandes_fournisseurs (tenant_id=2 ou 3)

```sql
CREATE TABLE commandes_fournisseurs (
  id                  BIGSERIAL PRIMARY KEY,
  tenant_id           BIGINT NOT NULL REFERENCES tenants(id),
  fournisseur_id      BIGINT NOT NULL REFERENCES fournisseurs_alim(id),
  reference           VARCHAR(100) NOT NULL,
  date_commande       DATE NOT NULL,
  date_livraison      DATE,
  statut              VARCHAR(30) NOT NULL DEFAULT 'brouillon',
  total_ht_cts        BIGINT NOT NULL DEFAULT 0,
  total_ttc_cts       BIGINT NOT NULL DEFAULT 0,
  notes               TEXT,
  etl_import_id       BIGINT REFERENCES etl_imports(id),
  is_active           BOOLEAN NOT NULL DEFAULT true,
  created_at          TIMESTAMP NOT NULL DEFAULT now(),
  updated_at          TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_commande_tenant_ref UNIQUE (tenant_id, reference),
  CONSTRAINT check_commande_statut CHECK (
    statut IN ('brouillon','confirmee','livree','annulee')
  ),
  CONSTRAINT check_commande_total CHECK (total_ht_cts >= 0)
);
CREATE INDEX idx_commandes_tenant ON commandes_fournisseurs(tenant_id);
CREATE INDEX idx_commandes_fournisseur ON commandes_fournisseurs(fournisseur_id);
```

### §6.8 — lignes_commande_fournisseur

```sql
CREATE TABLE lignes_commande_fournisseur (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  commande_id           BIGINT NOT NULL REFERENCES commandes_fournisseurs(id) ON DELETE CASCADE,
  catalogue_id          BIGINT REFERENCES catalogue_produits(id),
  designation           VARCHAR(300) NOT NULL,
  quantite              FLOAT NOT NULL,
  unite                 VARCHAR(20) NOT NULL,
  prix_unitaire_ht_cts  BIGINT NOT NULL,
  tva_rate              FLOAT NOT NULL DEFAULT 0.055,
  montant_ht_cts        BIGINT NOT NULL,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_ligne_quantite CHECK (quantite > 0),
  CONSTRAINT check_ligne_prix CHECK (prix_unitaire_ht_cts >= 0)
);
CREATE INDEX idx_lignes_commande_tenant ON lignes_commande_fournisseur(tenant_id, commande_id);
CREATE INDEX idx_lignes_commande_catalogue ON lignes_commande_fournisseur(catalogue_id);
```

### §6.9 — transferts_internes (document légal, sans tenant_id)

```sql
CREATE TABLE transferts_internes (
  id                  BIGSERIAL PRIMARY KEY,
  reference           VARCHAR(100) NOT NULL UNIQUE,
  date_transfert      DATE NOT NULL,
  tenant_source_id    INTEGER NOT NULL,  -- épicerie=2, entier brut (pas FK)
  tenant_dest_id      INTEGER NOT NULL,  -- restaurant=3, entier brut (pas FK)
  montant_ht_cts      BIGINT NOT NULL,
  montant_ttc_cts     BIGINT NOT NULL,
  statut              VARCHAR(30) NOT NULL DEFAULT 'brouillon',
  notes               TEXT,
  created_at          TIMESTAMP NOT NULL DEFAULT now(),
  updated_at          TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_transfert_statut CHECK (statut IN ('brouillon','valide','annule')),
  CONSTRAINT check_transfert_montant CHECK (montant_ht_cts >= 0),
  CONSTRAINT check_transfert_tenants CHECK (tenant_source_id != tenant_dest_id)
);
```

### §6.10 — mouvements_stock_epicerie (tenant_id=2)

```sql
CREATE TABLE mouvements_stock_epicerie (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  article_id            BIGINT NOT NULL REFERENCES articles_epicerie(id),
  type_mouvement        VARCHAR(30) NOT NULL,
  quantite              FLOAT NOT NULL,
  date_mouvement        TIMESTAMP NOT NULL,
  transfert_interne_id  BIGINT,           -- référence brute (pas FK DB)
  commande_id           BIGINT REFERENCES commandes_fournisseurs(id),
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_mvt_epicerie_type CHECK (
    type_mouvement IN ('entree','sortie','transfert_sortant','inventaire')
  ),
  CONSTRAINT check_mvt_epicerie_quantite CHECK (quantite != 0)
);
CREATE INDEX idx_mvt_epicerie_tenant_article ON mouvements_stock_epicerie(tenant_id, article_id);
CREATE INDEX idx_mvt_epicerie_date ON mouvements_stock_epicerie(tenant_id, date_mouvement);
```

### §6.11 — mouvements_stock_restaurant (tenant_id=3)

```sql
CREATE TABLE mouvements_stock_restaurant (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  ingredient_id         BIGINT NOT NULL REFERENCES ingredients(id),
  type_mouvement        VARCHAR(30) NOT NULL,
  quantite              FLOAT NOT NULL,
  date_mouvement        TIMESTAMP NOT NULL,
  transfert_interne_id  BIGINT,           -- référence brute (pas FK DB)
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_mvt_restaurant_type CHECK (
    type_mouvement IN ('entree','consommation','transfert_entrant','inventaire')
  ),
  CONSTRAINT check_mvt_restaurant_quantite CHECK (quantite != 0)
);
CREATE INDEX idx_mvt_restaurant_tenant_ingredient ON mouvements_stock_restaurant(tenant_id, ingredient_id);
CREATE INDEX idx_mvt_restaurant_date ON mouvements_stock_restaurant(tenant_id, date_mouvement);
```

---

## §6.R — Domaine Restaurant (tenant_id=3)

### §6.R1 — sides (liste fixe accompagnements) — M12

```sql
CREATE TABLE sides (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  nom                   VARCHAR(100) NOT NULL,
  ingredient_id         BIGINT REFERENCES ingredients(id),
  quantite_par_portion  FLOAT,
  unite                 VARCHAR(20),
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_side_tenant_nom UNIQUE (tenant_id, nom),
  CONSTRAINT check_side_quantite CHECK (quantite_par_portion IS NULL OR quantite_par_portion > 0)
);
CREATE INDEX idx_sides_tenant ON sides(tenant_id);
CREATE INDEX idx_sides_ingredient ON sides(ingredient_id) WHERE ingredient_id IS NOT NULL;
```

**Note** : `ingredient_id` nullable. Si renseigné, la confirmation de commande décrémente
l'ingrédient de `quantite_par_portion` via un `mouvement_stock_restaurant`.

---

### §6.R2 — types_preparation (recette template) — M13

```sql
CREATE TABLE types_preparation (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  nom                   VARCHAR(200) NOT NULL,
  portions_par_batch    INTEGER NOT NULL,
  notes                 TEXT,
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_type_prep_tenant_nom UNIQUE (tenant_id, nom),
  CONSTRAINT check_type_prep_portions CHECK (portions_par_batch > 0)
);
CREATE INDEX idx_types_prep_tenant ON types_preparation(tenant_id);
```

---

### §6.R3 — recettes_type_preparation (ingrédients par batch) — M14

```sql
CREATE TABLE recettes_type_preparation (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  type_preparation_id   BIGINT NOT NULL REFERENCES types_preparation(id) ON DELETE CASCADE,
  ingredient_id         BIGINT NOT NULL REFERENCES ingredients(id),
  quantite_par_batch    FLOAT NOT NULL,
  unite                 VARCHAR(20) NOT NULL,
  CONSTRAINT uq_recette_type_ingredient UNIQUE (type_preparation_id, ingredient_id),
  CONSTRAINT check_recette_quantite CHECK (quantite_par_batch > 0)
);
CREATE INDEX idx_recettes_type_prep ON recettes_type_preparation(tenant_id, type_preparation_id);
CREATE INDEX idx_recettes_ingredient ON recettes_type_preparation(ingredient_id);
```

---

### §6.R4 — instances_preparation (marmite réelle du jour) — M15

```sql
CREATE TABLE instances_preparation (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  type_preparation_id   BIGINT NOT NULL REFERENCES types_preparation(id),
  date_cuisine          DATE NOT NULL,
  portions_initiales    INTEGER NOT NULL,
  portions_restantes    INTEGER NOT NULL,
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_instance_portions CHECK (
    portions_restantes >= 0 AND portions_restantes <= portions_initiales
  ),
  CONSTRAINT check_instance_portions_init CHECK (portions_initiales > 0)
);
CREATE INDEX idx_instances_prep_tenant ON instances_preparation(tenant_id);
CREATE INDEX idx_instances_prep_type ON instances_preparation(tenant_id, type_preparation_id);
CREATE INDEX idx_instances_prep_date ON instances_preparation(tenant_id, date_cuisine);
```

**Note** : La création d'une instance déclenche automatiquement un `mouvement_stock_restaurant`
(type=consommation) pour chaque ligne de `recettes_type_preparation` × `quantite_par_batch`.

---

### §6.R5 — variantes_plat (configurations préconfigurées) — M16

```sql
CREATE TABLE variantes_plat (
  id                      BIGSERIAL PRIMARY KEY,
  tenant_id               BIGINT NOT NULL REFERENCES tenants(id),
  nom                     VARCHAR(200) NOT NULL,
  type_preparation_id     BIGINT NOT NULL REFERENCES types_preparation(id),
  ingredient_proteine_id  BIGINT REFERENCES ingredients(id),
  quantite_proteine       FLOAT,
  prix_vente_cts          BIGINT NOT NULL DEFAULT 0,
  is_active               BOOLEAN NOT NULL DEFAULT true,
  created_at              TIMESTAMP NOT NULL DEFAULT now(),
  updated_at              TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_variante_tenant_nom UNIQUE (tenant_id, nom),
  CONSTRAINT check_variante_prix CHECK (prix_vente_cts >= 0),
  CONSTRAINT check_variante_proteine CHECK (
    (ingredient_proteine_id IS NULL AND quantite_proteine IS NULL) OR
    (ingredient_proteine_id IS NOT NULL AND quantite_proteine > 0)
  )
);
CREATE INDEX idx_variantes_tenant ON variantes_plat(tenant_id);
CREATE INDEX idx_variantes_type_prep ON variantes_plat(type_preparation_id);
```

**Exemples** :
- "Riz sauce tomate + poulet" → type_prep=sauce_tomate, proteine=poulet, qte=200g, prix=1200cts
- "Riz sauce tomate + crevette" → type_prep=sauce_tomate, proteine=crevettes, qte=150g, prix=1500cts

---

### §6.R6 — tables_restaurant — M17

```sql
CREATE TABLE tables_restaurant (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  numero                VARCHAR(20) NOT NULL,
  capacite              INTEGER,
  is_active             BOOLEAN NOT NULL DEFAULT true,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_table_tenant_numero UNIQUE (tenant_id, numero),
  CONSTRAINT check_table_capacite CHECK (capacite IS NULL OR capacite > 0)
);
CREATE INDEX idx_tables_restaurant_tenant ON tables_restaurant(tenant_id);
```

---

### §6.R7 — commandes_restaurant (tickets clients) — M18

```sql
CREATE TABLE commandes_restaurant (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  table_id              BIGINT REFERENCES tables_restaurant(id),
  statut                VARCHAR(30) NOT NULL DEFAULT 'ouverte',
  date_ouverture        TIMESTAMP NOT NULL DEFAULT now(),
  date_fermeture        TIMESTAMP,
  total_cts             BIGINT NOT NULL DEFAULT 0,
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_commande_resto_statut CHECK (
    statut IN ('ouverte','servie','payee','annulee')
  ),
  CONSTRAINT check_commande_resto_total CHECK (total_cts >= 0)
);
CREATE INDEX idx_commandes_resto_tenant ON commandes_restaurant(tenant_id);
CREATE INDEX idx_commandes_resto_table ON commandes_restaurant(tenant_id, table_id);
CREATE INDEX idx_commandes_resto_statut ON commandes_restaurant(tenant_id, statut);
```

---

### §6.R8 — lignes_commande_restaurant — M19

```sql
CREATE TABLE lignes_commande_restaurant (
  id                        BIGSERIAL PRIMARY KEY,
  tenant_id                 BIGINT NOT NULL REFERENCES tenants(id),
  commande_id               BIGINT NOT NULL REFERENCES commandes_restaurant(id) ON DELETE CASCADE,
  variante_plat_id          BIGINT NOT NULL REFERENCES variantes_plat(id),
  side_id                   BIGINT REFERENCES sides(id),
  instance_preparation_id   BIGINT REFERENCES instances_preparation(id),
  quantite                  INTEGER NOT NULL DEFAULT 1,
  prix_unitaire_cts         BIGINT NOT NULL,
  notes                     TEXT,
  created_at                TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_ligne_resto_qte CHECK (quantite > 0),
  CONSTRAINT check_ligne_resto_prix CHECK (prix_unitaire_cts >= 0)
);
CREATE INDEX idx_lignes_resto_tenant_commande ON lignes_commande_restaurant(tenant_id, commande_id);
CREATE INDEX idx_lignes_resto_variante ON lignes_commande_restaurant(variante_plat_id);
```

**Déclenchements à la confirmation (statut → 'servie')** :
1. Décrémentation `instances_preparation.portions_restantes` (instance du bon type).
2. Création `mouvement_stock_restaurant` pour la protéine (type=consommation).
3. Création `mouvement_stock_restaurant` pour le side si `sides.ingredient_id IS NOT NULL`.

---

## §6.F — Finance V2 (documents sources, séparé de Finance location)

### §6.F1 — factures_achats (tenant_id=2 ou 3) — M20

```sql
CREATE TABLE factures_achats (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  fournisseur_id        BIGINT REFERENCES fournisseurs_alim(id),
  commande_id           BIGINT REFERENCES commandes_fournisseurs(id),
  reference             VARCHAR(100) NOT NULL,
  date_facture          DATE NOT NULL,
  montant_ht_cts        BIGINT NOT NULL,
  montant_ttc_cts       BIGINT NOT NULL,
  statut_paiement       VARCHAR(30) NOT NULL DEFAULT 'en_attente',
  etl_import_id         BIGINT REFERENCES etl_imports(id),
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_facture_tenant_ref UNIQUE (tenant_id, reference),
  CONSTRAINT check_facture_statut CHECK (statut_paiement IN ('en_attente','paye','annule')),
  CONSTRAINT check_facture_montant CHECK (
    montant_ht_cts >= 0 AND montant_ttc_cts >= montant_ht_cts
  )
);
CREATE INDEX idx_factures_achats_tenant ON factures_achats(tenant_id);
CREATE INDEX idx_factures_achats_fournisseur ON factures_achats(fournisseur_id);
CREATE INDEX idx_factures_achats_commande ON factures_achats(commande_id);
CREATE INDEX idx_factures_achats_etl ON factures_achats(etl_import_id);
```

**Note** : `commande_id` nullable — facture possible sans commande préalable.
`etl_import_id` nullable — saisie manuelle ou import ETL.

---

### §6.F2 — ventes_epicerie (tenant_id=2) — M21

```sql
CREATE TABLE ventes_epicerie (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  reference             VARCHAR(100) NOT NULL,
  date_vente            TIMESTAMP NOT NULL,
  total_cts             BIGINT NOT NULL DEFAULT 0,
  statut                VARCHAR(30) NOT NULL DEFAULT 'brouillon',
  notes                 TEXT,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  updated_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_vente_epicerie_tenant_ref UNIQUE (tenant_id, reference),
  CONSTRAINT check_vente_epicerie_statut CHECK (statut IN ('brouillon','confirmee','annulee')),
  CONSTRAINT check_vente_epicerie_total CHECK (total_cts >= 0)
);
CREATE INDEX idx_ventes_epicerie_tenant ON ventes_epicerie(tenant_id);
CREATE INDEX idx_ventes_epicerie_date ON ventes_epicerie(tenant_id, date_vente);
```

---

### §6.F3 — lignes_vente_epicerie — M22

```sql
CREATE TABLE lignes_vente_epicerie (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  vente_id              BIGINT NOT NULL REFERENCES ventes_epicerie(id) ON DELETE CASCADE,
  article_id            BIGINT NOT NULL REFERENCES articles_epicerie(id),
  quantite              FLOAT NOT NULL,
  prix_unitaire_cts     BIGINT NOT NULL,
  tva_rate              FLOAT NOT NULL DEFAULT 0.055,
  montant_ht_cts        BIGINT NOT NULL,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_ligne_vente_qte CHECK (quantite > 0),
  CONSTRAINT check_ligne_vente_prix CHECK (prix_unitaire_cts >= 0)
);
CREATE INDEX idx_lignes_vente_tenant_vente ON lignes_vente_epicerie(tenant_id, vente_id);
CREATE INDEX idx_lignes_vente_article ON lignes_vente_epicerie(article_id);
```

**Note** : La confirmation de vente (statut → 'confirmee') décrémente automatiquement
`articles_epicerie.stock_actuel` via un `mouvement_stock_epicerie` (type=sortie) par ligne.

---

## §6.X — Tables Cross-domaine

### §6.X1 — prix_fournisseur_historique (partagé, sans tenant_id) — M23

```sql
CREATE TABLE prix_fournisseur_historique (
  id                    BIGSERIAL PRIMARY KEY,
  catalogue_id          BIGINT NOT NULL REFERENCES catalogue_produits(id),
  fournisseur_id        BIGINT NOT NULL REFERENCES fournisseurs_alim(id),
  date_prix             DATE NOT NULL,
  prix_ht_cts           BIGINT NOT NULL,
  etl_import_id         BIGINT REFERENCES etl_imports(id),
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT uq_prix_catalogue_fournisseur_date UNIQUE (catalogue_id, fournisseur_id, date_prix),
  CONSTRAINT check_prix_positif CHECK (prix_ht_cts >= 0)
);
CREATE INDEX idx_prix_historique_catalogue ON prix_fournisseur_historique(catalogue_id);
CREATE INDEX idx_prix_historique_date ON prix_fournisseur_historique(catalogue_id, date_prix DESC);
```

**Requête prix à date J** :
```sql
SELECT prix_ht_cts FROM prix_fournisseur_historique
WHERE catalogue_id = :id AND date_prix <= :date_cuisine
ORDER BY date_prix DESC LIMIT 1;
```

---

### §6.X2 — alertes_stock (tenant_id) — M24

```sql
CREATE TABLE alertes_stock (
  id                    BIGSERIAL PRIMARY KEY,
  tenant_id             BIGINT NOT NULL REFERENCES tenants(id),
  entite_type           VARCHAR(30) NOT NULL,
  entite_id             BIGINT NOT NULL,
  stock_au_moment       FLOAT NOT NULL,
  seuil_type            VARCHAR(20) NOT NULL DEFAULT 'bas',
  resolu_at             TIMESTAMP,
  created_at            TIMESTAMP NOT NULL DEFAULT now(),
  CONSTRAINT check_alerte_entite_type CHECK (
    entite_type IN ('article_epicerie','ingredient','instance_preparation')
  ),
  CONSTRAINT check_alerte_seuil_type CHECK (seuil_type IN ('bas','zero'))
);
CREATE INDEX idx_alertes_stock_tenant ON alertes_stock(tenant_id);
CREATE INDEX idx_alertes_non_resolues ON alertes_stock(tenant_id, seuil_type)
  WHERE resolu_at IS NULL;
```

**Note** : `entite_id` est une référence brute (pas de FK DB) — permet de pointer vers
`articles_epicerie`, `ingredients` ou `instances_preparation` sans FK polymorphe.

---

## §7 — Ordre de migration (expand/contract)

```
--- SOCLE PARTAGÉ ---
M00 — categories_produit              (aucune dépendance — seedée dans la même migration)
M01 — catalogue_produits              (dépend: categories_produit)
M02 — fournisseurs_alim               (aucune dépendance)
M03 — etl_imports                     (dépend: fournisseurs_alim)
M04 — etl_conflicts                   (dépend: catalogue_produits)

--- ÉPICERIE ---
M05 — articles_epicerie               (dépend: catalogue_produits, fournisseurs_alim, categories_produit)
M07 — commandes_fournisseurs          (dépend: fournisseurs_alim, etl_imports)
M08 — lignes_commande_fournisseur     (dépend: commandes_fournisseurs, catalogue_produits)
M09 — transferts_internes             (aucune dépendance)
M10 — mouvements_stock_epicerie       (dépend: articles_epicerie, commandes_fournisseurs)

--- RESTAURANT ---
M06 — ingredients                     (dépend: catalogue_produits)
M11 — mouvements_stock_restaurant     (dépend: ingredients)
M12 — sides                           (dépend: ingredients)
M13 — types_preparation               (aucune dépendance restaurant)
M14 — recettes_type_preparation       (dépend: types_preparation, ingredients)
M15 — instances_preparation           (dépend: types_preparation)
M16 — variantes_plat                  (dépend: types_preparation, ingredients)
M17 — tables_restaurant               (aucune dépendance)
M18 — commandes_restaurant            (dépend: tables_restaurant)
M19 — lignes_commande_restaurant      (dépend: commandes_restaurant, variantes_plat, sides,
                                        instances_preparation)

--- FINANCE V2 ---
M20 — factures_achats                 (dépend: fournisseurs_alim, commandes_fournisseurs,
                                        etl_imports)
M21 — ventes_epicerie                 (aucune dépendance nouvelle)
M22 — lignes_vente_epicerie           (dépend: ventes_epicerie, articles_epicerie)

--- CROSS-DOMAINE ---
M23 — prix_fournisseur_historique     (dépend: catalogue_produits, fournisseurs_alim, etl_imports)
M24 — alertes_stock                   (aucune dépendance — entite_id = référence brute)
```

---

## §8 — Constantes V2

```python
# app/constants/epicerie.py
#
# NOTE: La catégorisation produits (50 catégories, 3 niveaux) est stockée
# dans la table `categories_produit` (M00), pas dans un Enum.
# Les codes valides sont les `code` de cette table : 'EPIC_PATE', 'ALC_BIERE', etc.
# Accès via CategoriesProduitRepository.get_all() — jamais hardcodé ici.

# Familles valides (niveau 1) — pour validation rapide sans requête DB
FAMILLES_VALIDES = frozenset({
    "Boissons", "Produits Laitiers", "Épicerie Salée", "Épicerie Sucrée",
    "Produits Frais", "Surgelés", "Boulangerie", "Fruits & Légumes",
    "Produits du Monde", "Snacking", "Hygiène", "Entretien",
    "Consommables Pro", "Divers",
})

class MouvementEpicerieType(str, Enum):
    ENTREE = "entree"
    SORTIE = "sortie"
    TRANSFERT_SORTANT = "transfert_sortant"
    INVENTAIRE = "inventaire"

TVA_ALIMENTAIRE_TAUX = 0.055   # 5.5% — taux réduit alimentaire
TVA_BOISSON_ALCOOL_TAUX = 0.20  # 20% — boissons alcoolisées

# app/constants/restaurant.py
class MouvementRestaurantType(str, Enum):
    ENTREE = "entree"
    CONSOMMATION = "consommation"
    TRANSFERT_ENTRANT = "transfert_entrant"
    INVENTAIRE = "inventaire"

class StatutCommandeRestaurant(str, Enum):
    OUVERTE = "ouverte"
    SERVIE = "servie"
    PAYEE = "payee"
    ANNULEE = "annulee"

# app/constants/finance_v2.py (nouveau — Finance V2, séparé de Finance location)
class StatutPaiementFacture(str, Enum):
    EN_ATTENTE = "en_attente"
    PAYE = "paye"
    ANNULE = "annule"

class StatutVenteEpicerie(str, Enum):
    BROUILLON = "brouillon"
    CONFIRMEE = "confirmee"
    ANNULEE = "annulee"

class TypeAlerteStock(str, Enum):
    BAS = "bas"     # stock_actuel <= stock_alerte
    ZERO = "zero"   # stock_actuel = 0

class EntiteTypeAlerte(str, Enum):
    ARTICLE_EPICERIE = "article_epicerie"
    INGREDIENT = "ingredient"
    INSTANCE_PREPARATION = "instance_preparation"

# app/constants/approvisionnement.py
class StatutCommande(str, Enum):
    BROUILLON = "brouillon"
    CONFIRMEE = "confirmee"
    LIVREE = "livree"
    ANNULEE = "annulee"

class StatutTransfert(str, Enum):
    BROUILLON = "brouillon"
    VALIDE = "valide"
    ANNULE = "annule"

class SourceFournisseur(str, Enum):
    METRO = "METRO"
    TAIYAT = "TAIYAT"
    EUROCIEL = "EUROCIEL"
    ETHAN = "ETHAN"
    GNANAM = "GNANAM"
    MANUEL = "MANUEL"
```

---

## §9 — Phases d'implémentation

```
Phase A — Socle partagé (M01→M04 + constants + ETL METRO)
  Migrations: M01 catalogue_produits, M02 fournisseurs_alim,
              M03 etl_imports, M04 etl_conflicts
  Code: parseur METRO, import_pipeline.py, tâche Celery etl_metro
  Tests: déduplication EAN, similarité texte, conflict log

Phase B — Épicerie (M05 + M07 + M08 + M10 + API CRUD)
  Migrations: M05 articles_epicerie, M07 commandes_fournisseurs,
              M08 lignes_commande, M10 mouvements_stock_epicerie
  Code: repos + services + API articles, commandes, mouvements
  Tests: anti-cross-tenant, stock cohérence, RBAC manager/staff

Phase C — Restaurant socle (M06 + M11-M16 + CRUD ingrédients)
  Migrations: M06 ingredients, M11 mouvements_stock_restaurant,
              M12 sides, M13 types_preparation, M14 recettes_type_preparation,
              M15 instances_preparation, M16 variantes_plat
  Code: repos + services ingrédients + préparations (cuisine = 2 niveaux)
  Tests: anti-cross-tenant, facteur_conversion, portions_restantes cohérence,
         déclenchement mouvement ingrédients à la création instance

Phase D — Transferts internes + commandes restaurant (M09 + M17-M19)
  Migrations: M09 transferts_internes, M17 tables_restaurant,
              M18 commandes_restaurant, M19 lignes_commande_restaurant
  Code: service transfert (2 transactions séquentielles + compensation),
        service commandes restaurant (consommation portions + protéine + side),
        tâche Celery calcul à rebours (nocturn + déclenchement manuel)
  Tests: rollback compensation transfert, décrémentation portions exacte,
         calcul à rebours cohérent vs ventes réelles

Phase E — ETL complet + prix historique (M23 + parseurs restants)
  Migrations: M23 prix_fournisseur_historique
  Code: TAIYAT, EUROCIEL, ETHAN, GNANAM + pipeline unifié,
        alimentation prix_fournisseur_historique à chaque import facture
  Tests: déduplication cross-fournisseur, gestion EAN conflit,
         historique prix correct sur imports consécutifs

Phase F — Finance V2 + alertes (M20-M22 + M24)
  Migrations: M20 factures_achats, M21 ventes_epicerie, M22 lignes_vente_epicerie,
              M24 alertes_stock
  Code: service Finance V2 (3 types documents, séparé location),
        service alertes_stock (Celery trigger bas/zero + résolution),
        calcul prix de revient (prix_fournisseur_historique × date_cuisine),
        vente épicerie → décrémentation stock automatique
  Tests: alertes déclenchement + résolution, calcul prix de revient à date J,
         vente confirmée → mouvement_stock_epicerie cohérent
```

---

## §10 — Règles de sécurité V2

- Aucun endpoint sans auth. `catalogue:read` = auth requise minimum.
- Tous les repos V2 héritent de `AsyncBaseRepository`.
- `update()` reste synchrone (BaseRepository.update pattern).
- Imports ETL = tâches Celery uniquement, accès `super_admin`/`platform_ops`.
- Test anti-cross-tenant obligatoire pour chaque endpoint métier.
- `rapidfuzz` en dépendance pour la déduplication catalogue.

---

### ADR-15 — etl_conflicts porte etl_import_id (FK vers etl_imports)

**Décision** : `etl_conflicts` ajoute une colonne `etl_import_id` nullable,
FK vers `etl_imports.id` (pas de `ON DELETE CASCADE` — les conflits survivent
à la suppression du log d'import pour préserver l'audit).

**Justification** : Sans ce lien, il est impossible de :
- Filtrer "tous les conflits générés par l'import METRO du 01/03/2026"
- Afficher l'onglet "Conflits générés" dans la page ETL Imports Log
- Identifier le batch responsable d'une vague de conflits en production

Ce besoin a été révélé lors de la rédaction des specs API (session 2026-03-09) —
la page `admin/etl-imports/{id}` expose un endpoint `GET /conflicts` qui
nécessite ce filtre. Sans `etl_import_id`, l'endpoint n'est pas implémentable
proprement (seul un filtre approximatif par date serait possible).

**Impact migrations** : Ajoute une colonne dans M04 `etl_conflicts`.
Convention expand/contract : colonne nullable d'abord, sans rupture.

```sql
-- M04 (complété) : etl_conflicts
ALTER TABLE etl_conflicts ADD COLUMN etl_import_id INTEGER REFERENCES etl_imports(id);
CREATE INDEX idx_etl_conflicts_import_id ON etl_conflicts(etl_import_id);
```

**Impact Celery** : La task `etl.tasks.import_*` reçoit `etl_import_id`
comme paramètre et le propage à chaque `INSERT INTO etl_conflicts`.

**Alternative rejetée** : Filtre par `created_at` — approximatif, cassant
si deux imports se chevauchent dans la même fenêtre de temps.

---

### ADR-16 — Specs API générées à partir de V2_ARCHITECTURE_PLAN, cross-validation mockups requise

**Contexte** : Les fichiers `V2_API_EPICERIE.md`, `V2_API_RESTAURANT.md`,
`V2_API_ADMIN.md` ont été générés (session 2026-03-09) à partir des ADR
et du schéma V2 — **pas** à partir des maquettes HTML `/tmp/massa-mockups/`.

**Risque identifié** : certains flows UI (stepper réception, suggestion formule
boissons, statut plat par plat, paiement fractionné) peuvent ne pas avoir
d'endpoint correspondant dans les specs générées.

**Décision** : Avant implémentation, une passe de cross-validation
mockups ↔ specs est obligatoire. Les écarts sont documentés dans
`V2_API_GAPS.md` (à créer) et résolus avant Phase B minimum.

**Impact** : Les specs V2_API_*.md sont en statut **"draft à valider"**,
pas encore "référence" pour l'implémentation.

---

*Document v1.4 — session 2026-03-09 · ADR-15 (etl_import_id) + ADR-16 (specs draft).*
*Périmètre complet : M00→M24, 6 phases d'implémentation.*
*Prochaine étape : Phase A — implémentation sur accord utilisateur.*
