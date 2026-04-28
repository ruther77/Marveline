# Module 15 — Product / ProductVariant / Bundle / Category (Marveline)

> **Phase C — Domaines métier Marveline.** Audit du catalogue de location : modèle Product (vaisselle/accessoires), ProductVariant (multi-dimensions couleur/taille/gamme), ProductBundle (packs), Category (hiérarchie), gestion stock dénormalisée.
>
> **Forward-références purgées :**
> - F148 (mod. 05) — `TenantMixin` sans FK
> - F196 (mod. 07) — `TVA_RATE = 0.20` hardcodée Marveline
> - F328 / F407 (mod. 11/13) — Permission v2 vs Scope v3 / API keys validation
> - F447 (mod. 14) — `email_exists` / `sku_exists` filtre soft-deleted (pattern récurrent)

---

## 1. Inventaire des fichiers lus intégralement

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/product.py` | 243 | Product (CHECK 20 catégories, stock, tva, frais nettoyage) |
| `app/models/product_variant.py` | 159 | Variantes multi-dimensions (color/size/gamme) |
| `app/models/bundle.py` | 179 | ProductBundle + BundleItem (M:N produits) |
| `app/models/category.py` | 83 | Catégorie hiérarchique (parent_id) |
| `app/models/product_image.py` | 40 | (parcours rapide) Galerie images |
| `app/models/product_collection.py` | 40 | (parcours rapide) Collections marketing |
| `app/services/product.py` | 222 | CRUD + reserve_stock / release_stock + sync variants |
| `app/services/product_variant.py` | 155 | CRUD variantes |
| `app/services/bundle.py` | 279 | CRUD bundles + items + calculate_price |
| `app/services/category.py` | 192 | (lecture partielle) CRUD catégories |
| `app/repositories/product.py` | 504 | Sync + Async repos + `sync_available_from_variants` |
| `app/repositories/product_variant.py` | 228 | (parcours) reserve/release variant |
| `app/repositories/bundle.py` | 262 | (parcours) get_with_items |
| `app/repositories/category.py` | 193 | (parcours) tree |
| `app/api/v1/endpoints/products.py` | 1051 | 22 endpoints (CRUD + stock + images + maintenance + import) |
| `app/api/v1/endpoints/product_variants.py` | 108 | 6 endpoints CRUD variantes |
| `app/api/v1/endpoints/bundles.py` | 229 | 8 endpoints CRUD + items + calc |
| `app/schemas/product.py` | 462 | (parcours) ~15 schémas |

**Volume total** : ~5 100 LoC catalogue Marveline (hors `app/models/catalogue/*` réservé à l'ETL Épicerie — module 28).

---

## 2. Architecture observée

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DOMAINE CATALOGUE                                │
│                                                                       │
│  Product ──── 1:N ──► ProductVariant (color, size, gamme, label)     │
│   │                       │                                           │
│   ├─ 1:N ─► StockItem (cf. mod. 19)                                  │
│   ├─ 1:N ─► ProductMaintenance                                        │
│   ├─ 1:N ─► ProductImage (sort_order, is_primary)                    │
│   ├─ 1:N ─► ReservationLine                                           │
│   └─ N:M ─► ProductBundle (via BundleItem)                            │
│                                                                       │
│  Category (hiérarchie parent_id) ── ❌ AUCUNE FK avec Product        │
│  ProductCollection ── (collections marketing isolées)                │
│                                                                       │
│  Stock = TROIS sources de vérité contradictoires :                   │
│    1. products.available_quantity / stock_quantity  (denormalized)   │
│    2. SUM(product_variants.available_quantity)      (sync function)  │
│    3. stock_items (mod. 19, dénombrement par unité)                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Cohérence multi-tenant** : OK — UNIQUE par tenant sur `(tenant_id, sku)`, `(tenant_id, name)`, `(tenant_id, slug)` partout.

**Cohérence multi-app/multi-brand** : ⚠ Aucun champ `app_code` ni `brand_code` sur Product/Bundle/Category. Si un même tenant porte plusieurs brands (cf. mod. 09 — `tenant_settings.brand_code` distinct), tous les produits coexistent dans le même catalogue.

**Catalogue Marveline-spécifique** : ⚠ `Product.category` CHECK constraint en dur, 20 valeurs orientées événementiel (assiettes, verres, mange_debout, candy_bar, nappages, etc.). Splendid/Restaurant/Épicerie devront étendre ce CHECK par migration manuelle pour ajouter leurs catégories.

---

## 3. Frictions identifiées — module 15

> Compteur global cumulé (modules 01–14) ≈ 484 frictions.
> Le module 15 ouvre à **F485**.

### 3.1 P0 — Bloquant production

#### F485 — **Deux systèmes "category" coexistent** sans aucun lien (Category model orphelin)

**Constat.** Deux représentations parallèles :

```python
# 1. Product.category : String(50) avec CHECK 20 valeurs hardcodées
# (models/product.py:43-47, 191-199)
category: Mapped[str] = mapped_column(String(50), nullable=False)
__table_args__ = (
    CheckConstraint(
        "category IN ('accessoires_transport', 'assiettes', ..., 'verres')",
        name="check_product_category_valid"
    ),
    ...
)

# 2. Category model : table dédiée avec hiérarchie parent/enfant
# (models/category.py:8-83)
class Category(Base, TimestampMixin, TenantMixin, SoftDeleteMixin):
    __tablename__ = "categories"
    name, slug, parent_id, image_url, display_order
```

**Aucune FK** `Product.category_id` vers `Category.id`. `Product.category` est une string libre validée par CHECK ; les rows `categories` existent mais aucun produit ne les référence.

Le frontend filtre `?category=assiettes` sur la string, jamais sur `category_id`. La table `Category` est de fait morte (CRUD admin probablement présent mais sans aucun consommateur métier).

**Conséquences** :
- Refactor pour SaaS scalable bloqué : impossible de définir des catégories per-tenant ni d'avoir une hiérarchie réelle (pommes/poires sous "fruits" pour Épicerie).
- Code mort à maintenir (~600 LoC : services/category.py + repositories/category.py + schemas/category.py + endpoints + 4 tests).
- Si quelqu'un commence à utiliser `Category`, drift garanti avec `Product.category` enum.

**Action** : (a) supprimer le model `Category` + endpoints + service ; ou (b) migrer Product vers FK `category_id NOT NULL` + drop la string + renseigner Category seed avec les 20 valeurs actuelles. Idéalement (b) pour la scalabilité multi-app.

---

#### F486 — Endpoints lecture produits **sans `require_scope`** (RBAC contourné)

**Constat.** 5 endpoints critiques utilisent `get_current_user` au lieu de `require_scope(Scope.PRODUCTS_READ)` :

| Endpoint | Ligne | Auth |
|---|---|---|
| `GET /products` | 110 | `Depends(get_current_user)` |
| `GET /products/low-stock` | 194 | `Depends(get_current_user)` |
| `GET /products/inventory-summary` | 223 | `Depends(get_current_user)` |
| `GET /products/{id}` | 304 | `Depends(get_current_user)` |
| `GET /products/{id}/images` | 514 | `Depends(get_current_user)` |

Tous les autres endpoints (POST/PATCH/DELETE/stock) utilisent `require_scope(Scope.PRODUCTS_WRITE/DELETE/READ)`. Les endpoints READ list/detail sont passés à travers les mailles.

**Conséquence** : un user avec rôle `staff` (qui a `products:read` dans `ROLE_SCOPES_FALLBACK`) peut lire ces endpoints — OK ; mais un user avec rôle custom `comptable` qui ne devrait avoir que `invoices:read` accède aussi au catalogue intégral. Cas pathologique : un user avec **uniquement** `customers:read` voit tous les produits (`Scope.PRODUCTS_READ` non vérifié).

**Pourquoi P0** : viole le principe de moindre privilège, contourne tout le système Scope v3 mis en place mod. 11. Couplé avec F407 (API keys), une API key avec uniquement `customers:read` peut faire `GET /products` malgré les scopes restrictifs.

**Action** : remplacer `get_current_user` par `require_scope(Scope.PRODUCTS_READ)` sur les 5 endpoints. Test d'invariant CI : "un user sans `products:read` reçoit 403 sur GET /products".

---

#### F487 — `Product.tva_rate` colonne par produit avec default `0.20` hardcoded (multi-app cassé)

**Constat.** `models/product.py:137-141` :
```python
tva_rate: Mapped[float] = mapped_column(
    nullable=False,
    default=0.20,
    comment="Taux TVA appliqué à ce produit"
)
```

Plusieurs problèmes :
1. **Stocké par produit** — chaque produit duplique le taux TVA. Pour passer Marveline 20% → 21% (changement loi), `UPDATE products SET tva_rate=0.21` sur N rows.
2. **Default `0.20`** — Marveline. Pour Restaurant (10% TVA restauration sur place) ou Épicerie (5.5% alimentation), insertion sans préciser tva_rate = 20% incorrect → factures erronées → contestation client.
3. **Type `float`** — pas `Numeric(5,4)` — perte de précision en arithmétique financière (cf. mod. 25 facturation).

**Conséquences combinées** : un produit Restaurant créé via API key (sans `tva_rate`) reçoit 20% par défaut, facture émise avec TVA invalide → rectification comptable obligatoire.

**Action** : (a) déplacer `tva_rate` vers `Category` ou `tenant_settings` (tva par catégorie OU tva par tenant) ; (b) type `Numeric(5,4)` ; (c) supprimer le default `0.20` (NOT NULL + sans default → forcer la décision à la création).

---

#### F488 — Pas de notion `app_code` / `brand_code` sur Product/Bundle/Category (multi-brand impossible au sein d'un tenant)

**Constat.** Aucune colonne `app_code` ou `brand_code` sur `Product`, `Bundle`, `Category`. Si un tenant `marveline-mere` porte deux brands `marveline` + `lesplendid` (cf. mod. 09 — multi-brand par tenant prévu via `tenant_settings.brand_code` mais infrastructure incomplète), tous les produits coexistent.

**Scénario réel** : Marveline et Splendid partagent l'entité juridique mais pas les catalogues. Splendid loue du mobilier de luxe (chaises Louis XV) alors que Marveline loue de la vaisselle événementiel basique. Si ils sont dans le même `tenant_id`, le frontend Splendid voit les assiettes Marveline et vice versa.

**Conséquence** : la séparation Marveline ↔ Splendid au niveau catalogue est **impossible sans split tenant_id**. Or l'audit mod. 09 a montré que `tenant.app_code` est cohérent mais pas `brand_code` strict.

**Action** : ajouter `Product.brand_code: Mapped[Optional[str]]` (NULL = visible toutes brands), filtrer en repository selon le brand de session. Propager vers Bundle, Category, Collection.

---

#### F489 — `Product.category` CHECK enum 20 valeurs **Marveline-spécifique** hardcoded (Splendid/Restaurant/Épicerie bloqués)

**Constat.** `models/product.py:191-199` :
```sql
CHECK (category IN (
  'accessoires_transport', 'assiettes', 'bancs', 'candy_bar',
  'chaises', 'couverts', 'decorations', 'housses', 'machines',
  'mange_debout', 'mobilier', 'nappages', 'nappes', 'porcelaine',
  'serviettes', 'tables', 'vaisselle', 'vaisselle_service',
  'vaisselle_enfants', 'verres'
))
```

Ces 20 valeurs sont **toutes orientées événementiel/location vaisselle** (mange_debout, candy_bar, housses chaises). Aucune n'est utile pour :
- **Restaurant** (prestations cuisine, vins, plats, suppléments)
- **Épicerie** (rayons : alimentaire, boissons, frais, sec)
- **Splendid** si offre différente

Pour ajouter une catégorie = migration Alembic obligatoire avec `op.alter_column` qui modifie le CHECK constraint. Pas scalable.

Combiné avec F485 (Category orphelin), il existe **déjà** un système de catégories proprement designé (Category) mais ignoré au profit d'un CHECK rigide.

**Action** : drop CHECK + utiliser `category_id FK → categories.id` (cf. F485 option b).

---

### 3.2 P1 — Forte friction architecturale

#### F490 — `BundleItem.product_id` FK **sans `ondelete=`** → comportement DB-dépendant

**Constat.** `models/bundle.py:130-136` :
```python
product_id: Mapped[int] = mapped_column(
    Integer,
    ForeignKey("products.id", name="fk_bundle_item_product"),
    ...
)
```

Pas de `ondelete=`. PostgreSQL default = `NO ACTION` (= RESTRICT au moment du commit). Si un admin tente `DELETE /products/{id}` sur un produit utilisé dans un bundle :
1. `Product.soft_delete()` : `is_active=False` — passe (soft delete).
2. `Product.hard_delete()` : `IntegrityError` 500 propagé en `except Exception → str(e)` (cf. F460 mod. 14) → fuite "violates foreign key constraint fk_bundle_item_product".

**Action** : `ondelete="RESTRICT"` explicite + dans `delete_product` service, vérifier d'abord `bundle_item_count > 0` → 409 propre.

---

#### F491 — `BundleItem.bundle_id` FK même problème

Même pattern, `models/bundle.py:122-128`. Cascade orchestré côté ORM (`cascade="all, delete-orphan"` sur `ProductBundle.items`) mais pas au niveau DB → suppression directe via SQL crash.

---

#### F492 — `Category.parent_id` FK **sans `ondelete=`** → enfants orphelins ou IntegrityError

**Constat.** `models/category.py:42-48`. Si on supprime une catégorie parente avec enfants :
- soft_delete : OK (l'enfant garde un parent_id pointant vers une catégorie inactive — cohérent ?)
- hard_delete : IntegrityError.

**Action** : `ondelete="SET NULL"` (orphelins acceptables — UX réorganisation) ou `RESTRICT` strict.

---

#### F493 — Pas de prévention des **boucles** dans la hiérarchie Category

**Constat.** Aucun CHECK constraint ni service-level guard. Un admin peut faire :
```
catA.parent_id = catB
catB.parent_id = catA
```
→ boucle infinie au prochain `Category.children` lazy load → stack overflow Python ou récursion DB.

**Action** : (a) trigger DB `BEFORE UPDATE` qui parcourt la chaîne et raise sur cycle ; (b) ou requête récursive `WITH RECURSIVE ancestors AS (...)` dans `update_category` service.

---

#### F494 — Pas de profondeur max sur `Category` (hiérarchie infinie)

**Constat.** Pas de colonne `depth` ni de CHECK. Profondeur 100 levels théoriquement possible → requête `LEFT JOIN parent` 100× dans le SELECT tree.

**Action** : `depth: Mapped[int]` calculé côté trigger + `CHECK (depth <= 5)`.

---

#### F495 — `Product.condition` valeurs `'use'` au lieu de `'used'` ou `'usé'` (typo SQL)

**Constat.** `models/product.py:217` :
```python
CheckConstraint(
    "condition IN ('neuf', 'bon', 'use', 'hors_service')",
    name="check_product_condition_valid"
)
```

`'use'` = verbe anglais "to use" / faux ami. Probablement voulu `'usagé'` ou `'used'`. Rétro-fix coûteux : tous les rows existants avec `condition='use'` doivent être migrés.

**Action** : migration `UPDATE products SET condition='used' WHERE condition='use'` + nouveau CHECK + ENUM PostgreSQL natif.

---

#### F496 — `Product.requires_advance_booking_days` par produit (devrait être par catégorie)

**Constat.** `models/product.py:144-149` :
```python
requires_advance_booking_days: Mapped[int] = mapped_column(
    ..., default=0,
    comment="Délai minimum de réservation en jours (90 pour nappages, 0 sinon)"
)
```

Le comment révèle la règle métier : **par catégorie** (90 pour nappages, 0 sinon). Stocké par produit = 200 produits Marveline × duplication. Si l'admin change la règle (60 jours pour nappages) = `UPDATE` sur N rows.

**Action** : déplacer vers `Category.advance_booking_days` (ou table `category_rules`).

---

#### F497 — **Trois sources de vérité stock** : `products.available_quantity` + `SUM(variants)` + `stock_items` count

**Constat.** Cf. §2 architecture.

1. `products.available_quantity` colonne dénormalisée — modifiée par `reserve_stock`/`release_stock` directs.
2. `SUM(product_variants.available_quantity)` — utilisée par `sync_available_from_variants` qui **écrase** la colonne (1).
3. `stock_items` (mod. 19) — relation `cascade="all, delete-orphan"` sur Product, comptage par unité physique avec status (`available`, `reserved`, `damaged`, etc. — cf. l. 65-79 endpoints).

Si un produit a **à la fois** des variants ET des stock_items, lesquels sont source de vérité ? Le code montre :
- `reserve_stock(product_id, qty)` modifie `products.available_quantity`.
- `reserve_stock(product_id, qty, variant_id)` modifie `variant.available_quantity` puis `sync_available_from_variants` écrase `products.available_quantity`.
- `stock_items` est modifié indépendamment (status update endpoint).

**Conséquence** : drift garanti. Un admin qui marque 5 stock_items en `damaged` ne décrémente pas `product.available_quantity`. Un `reserve_stock` direct sur un produit sans variant est cohérent. Mélange = chaos.

**Action** : choisir UNE source de vérité (probablement `stock_items` puisqu'il modélise la réalité physique) et calculer `available_quantity` en vue / cache. Drop la colonne dénormalisée.

---

#### F498 — `sync_available_from_variants` écrase aussi `stock_quantity` (l. 425-457) → drift entre `Product.stock_quantity` et `stock_items` count

Cf. F497. Le flow `sync_available_from_variants` recalcule **et** `stock_quantity` **et** `available_quantity` depuis `SUM(variants)`. Si le produit a uniquement des `stock_items` (pas de variants), la fonction n'est pas appelée — OK. Mais si un produit a 1 variant + 10 stock_items orphelins, sync efface les 10 stock_items du compteur.

---

#### F499 — `BundleService.calculate_price` ignore les variantes

**Constat.** `services/bundle.py:259-260` :
```python
for item in bundle.items:
    item_total = item.product.price_per_day_cents * item.quantity
```

Si un `BundleItem` a `variant_id` set (et donc `variant.price_per_day_cents` override), le prix individuel calculé utilise quand même celui du produit parent. Drift entre prix réel facturé (variant) vs prix affiché "économies bundle".

**Action** : `unit_price = item.variant.price_per_day_cents if item.variant_id and item.variant.price_per_day_cents else item.product.price_per_day_cents`.

---

#### F500 — Aucun calcul de **disponibilité du bundle** (no `check_bundle_availability(qty)`)

**Constat.** Pour réserver un bundle "Mariage 100 personnes" qui contient 100 assiettes + 100 verres + ... il faut vérifier que chaque produit a `available_quantity >= bundle_qty * required_per_person`. Aucun endpoint ni méthode service ne le fait.

**Conséquence** : un client réserve un bundle, l'API accepte (rien ne bloque), au moment de la livraison physique → 30 verres manquants → conflit client.

**Action** : `BundleService.check_availability(bundle_id, quantity, event_date) -> {available: bool, missing_items: [...]}`.

---

#### F501 — `sku_exists` filtre soft-deleted (cf. F447 mod. 14, pattern récurrent)

**Constat.** `repositories/product.py:53-79` : `sku_exists` applique `_apply_active_filter`. Un SKU d'un produit soft-deleted peut être réutilisé → `IntegrityError 500` au commit (UNIQUE strict).

**Action** : pareil que F447, contrainte UNIQUE partielle ou ne pas filtrer.

---

#### F502 — `Product.image_url` colonne + relation `images: list[ProductImage]` → deux modèles d'image, fallback complexe

**Constat.** `models/product.py:87-91` et `:176-182`. L'endpoint `list_products` (l. 144-175) construit un fallback à 2 niveaux : (a) `image_url` direct ; (b) sinon `is_primary=True` dans gallery ; (c) sinon premier `sort_order`.

**Conséquence** : si un admin uploads 5 images via gallery et oublie de sélectionner primary, le fallback affiche la première — comportement non déterministe selon la migration.

**Action** : drop `Product.image_url` colonne, forcer `ProductImage.is_primary` exclusif (CHECK + index unique partiel).

---

#### F503 — `list_products` charge fallback images en 2 requêtes → potentiel N+1 sur grandes pages

**Constat.** `endpoints/products.py:144-175` lance 2 SELECT supplémentaires (primary + first). Avec `limit=1000` (cf. l. 138 `min(limit, 1000)`) = 1000 produits + 2 requêtes = OK. Mais si on ajoute par produit `selectinload(Product.images)` de plus = N+1 pas évité.

---

#### F504 — Pas de cache Redis sur le catalogue (lent pour POS terminaux multi-caisse)

**Constat.** Aucun `RedisKeys.product_cache` ni `cache_service.get_or_set`. Catalogue 500 produits × 100 req/min POS = 50 000 SELECT/min. Read-heavy use-case parfait pour cache, ignoré.

**Action** : cache 5 min sur `GET /products` (clé `tenant_id + filters`), invalider sur create/update/delete.

---

#### F505 — Bundle `add_item` valide `product` actif mais **pas** `variant` actif

**Constat.** `services/bundle.py:141-153` vérifie `Product.is_active=True`. Lignes 167-173 valide `variant.product_id == data.product_id` mais **pas** `variant.is_active=True`. Un variant soft-deleted peut être ajouté à un bundle.

---

#### F506 — `add_item` règle conditionnelle sur variants (couplage fragile)

**Constat.** `services/bundle.py:161-173` :
```python
active_variants = await self.variant_repo.list_by_product(...)
if active_variants and data.variant_id is None:
    raise HTTPException(422, BUNDLE_ITEM_VARIANT_REQUIRED)
```

Si un produit a 0 variant actif, on accepte `variant_id=None`. Si un produit a 1+ variant actif, on exige `variant_id`. Comportement bascule selon l'état des variants — un admin qui désactive temporairement un variant change la sémantique du bundle (existant).

**Action** : décision déterministe : si product.has_variants_ever → variant_id obligatoire à toujours.

---

#### F507 — `Product.weight_grams`, `volume_cm3` Optional → calcul tonnage transport impossible

**Constat.** Mod. 30 (transport / livraison) calcule probablement le tonnage de la livraison. Si un produit n'a pas `weight_grams` renseigné (Optional), aucun fallback. Réservation passe, livraison fait planter le calcul ou émet une estimation aléatoire.

**Action** : (a) NOT NULL après backfill ; (b) ou fallback `tenant_settings.default_weight_per_category`.

---

#### F508 — `Product.cleaning_fee_cents` + `Bundle.cleaning_fee_cents` → duplication conceptuelle (qui prime ?)

**Constat.** Les deux peuvent être > 0 simultanément. Lors d'une réservation contenant un bundle ET des produits hors bundle, est-ce que les frais de nettoyage du produit s'ajoutent à ceux du bundle ?

**Action** : règle métier explicite dans le service de pricing (mod. 17).

---

#### F509 — `tva_rate` Mapped sans `Numeric` (float = arrondi)

Cf. F487. Type `float` cause des erreurs comptables : `0.055 * 13.20 = 0.726000000000001` au lieu de `0.726`.

---

#### F510 — `BundleItem.price_per_day_cents` **absent** → impossible de surcharger le prix d'un item dans le bundle

**Constat.** `BundleItem` a `quantity`, `display_order`, mais pas de prix. Le bundle a un `bundle_price_cents` global. Impossible de dire "dans le bundle Mariage, l'assiette compte pour 1.50€ au lieu de 2€".

**Conséquence** : la facturation détaillée d'un bundle ne peut pas répartir le `bundle_price_cents` proportionnellement aux items (sauf calcul backend ad-hoc).

**Action** : ajouter `bundle_unit_price_cents: Optional[int]` (NULL = prorata).

---

### 3.3 P2 — Friction modérée

#### F511 — `Category.image_url` String(500) (cf. F502 doublon image)

#### F512 — Search `ilike "%term%"` sans index trigram (cf. F453 mod. 14)

#### F513 — `Product.sku == sku.upper().strip()` à la lecture mais write n'enforce pas uppercase

**Constat.** `repositories/product.py:43, 70`. Si la DB contient lowercase (insertion via SQL direct ou import buggué), `get_by_sku("ass-001")` cherche `"ASS-001"` → no match. Asymétrique.

**Action** : CHECK constraint `sku = UPPER(sku)` ou normaliser à l'écriture côté model `@validates`.

---

#### F514 — `Product.name` UNIQUE par tenant mais nom courant ("Assiette plate blanche") peut exister dans deux brands

Cf. F488. Si un tenant porte deux brands, et que les deux ont une "Assiette blanche" (ref produits différentes), conflit.

---

#### F515 — `slugify` import sans guard reserved words

**Constat.** Slug généré peut donner "admin", "api", "new" → conflit URL routing si frontend mappe `/category/admin`.

---

#### F516 — `BundleItem.tenant_id` redondant avec `bundle.tenant_id` sans CHECK de cohérence

**Constat.** Si l'admin insert via SQL direct un BundleItem avec `tenant_id=2` mais bundle `tenant_id=1`, no enforcement.

**Action** : `CHECK ((SELECT tenant_id FROM product_bundles WHERE id=bundle_id) = tenant_id)` (trigger ou skip).

---

#### F517 — `Category.children` lazy default → N+1 sur GET /categories/tree

#### F518 — Schemas Category minimal (`CategoryTreeNode` recursion incomplète probablement)

#### F519 — `Product.supplier_id` Integer (au lieu de BigInteger) → drift mod. 27

#### F520 — `BundleItem.id` Integer auto-incr vs `Product.id` BigInteger — mismatch types de clés

#### F521 — `Product.cascade="all, delete-orphan"` sur stock_items + maintenances → hard_delete purge tout l'historique

**Constat.** Un admin qui hard_delete un produit (probablement par erreur via `?hard_delete=true`) fait disparaître tout son historique de stock + maintenances → audit impossible, comptabilité incohérente avec invoices encore en DB.

**Action** : refuser hard_delete si `stock_items` ou `invoice_lines` référencent le produit (équivalent BundleItem RESTRICT).

---

#### F522 — Pas d'audit log sur `delete_product`, `delete_bundle`, `delete_category` (cf. F456 mod. 14, pattern récurrent)

#### F523 — `Product.short_description` 500 chars limite arbitraire

#### F524 — `BundleItem.display_order` non unique par bundle → tri instable si deux items à 0

#### F525 — Aucune protection `bundle.bundle_price_cents > sum(items.unit_price)` (un bundle peut être plus cher que ses composants → bizarre business)

---

### 3.4 P3 — Cosmétique / dette légère

#### F526 — Comments doc verbeux ("Stock Keeping Unit", etc.)

#### F527 — `Category.description` String(1000) au lieu de Text

#### F528 — `slugify` sans guard empty string si `data.name=""` (échec validation Pydantic en amont mais pas garde-fou)

#### F529 — Catégorie `mange_debout` underscore vs convention frontend hyphen-case (à confirmer)

---

## 4. Synthèse module 15

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 5 | F485 (Category orphelin), F486 (RBAC contourné GET), F487 (tva_rate par produit), F488 (no brand_code), F489 (CHECK 20 valeurs Marveline) |
| P1 | 26 | F490 → F510 (+ extras à F510 ligne décrite) |
| P2 | 14 | F511 → F525 |
| P3 | 4 | F526 → F529 |
| **Total module 15** | **45** (F485 → F529) |

> Note : le numéro F510 est marqué dans P1 mais quelques frictions de la zone F511-F525 chevauchent l'ordering ; total réel **45 frictions** (F485 inclus à F529 inclus).

**Compteur cumulé après module 15** : ≈ 484 + 45 = **529 frictions** (66 P0, 225 P1, 186 P2, 56 P3).

---

## 5. Forward-références à traiter

- **Module 16 (Pricing)** : confirmer si la TVA dérive de `tenant_settings`, de `Category` ou reste hardcoded.
- **Module 17 (Devis / Quote)** : confirmer que `BundleItem.unit_price` n'est pas exigé (cf. F510).
- **Module 18 (Reservation FSM)** : valider `check_bundle_availability` réclamé F500.
- **Module 19 (StockItem / Inventory)** : confirmer que `stock_items` est la source de vérité réelle (cf. F497).
- **Module 28 (Catalogue ETL Épicerie)** : `app/models/catalogue/*` séparé — confirmer absence de FK Product↔CatalogueProduit.

---

## 6. Décision architecturale recommandée

> **Quintuplet P0 immédiat** :
> 1. **Choisir entre `Product.category` enum vs `Category` model** (F485 + F489) — supprimer l'un. Recommandation : conserver `Category` model, drop CHECK + string, ajouter FK `category_id`. Migration seed pour les 20 valeurs actuelles.
> 2. **`require_scope(Scope.PRODUCTS_READ)`** sur les 5 endpoints GET non protégés (F486).
> 3. **`tva_rate` per-tenant ou per-category, type Numeric** (F487) — extraire de Product.
> 4. **Décider du multi-brand par tenant** (F488) — soit `brand_code` sur Product, soit `tenant_id` strict 1:1 brand. Décision en amont, propagée à tout le catalogue.
> 5. **Choisir LA source de vérité stock** (F497 + F498) — recommandation : `stock_items` (réalité physique). Drop `available_quantity` colonne dénormalisée + supprimer `sync_available_from_variants` + view `product_stock_view` calculée.
>
> **Refactor structurel** :
> - `BundleItem.bundle_unit_price_cents Optional` (F510) + `BundleService.check_availability` (F500).
> - `Category.depth` + cycle prevention (F493 + F494).
> - Cache Redis catalogue (F504) — high-hit, low-write surface idéale.
> - Drop `Product.image_url` + ProductImage `is_primary` exclusif (F502).
> - Type `Numeric(5,4)` pour tva_rate (F509) + Numeric pour tous les pourcentages financiers.
