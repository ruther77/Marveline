# Sprint B7.S2 — Drop brand_code Catalogue

> **STATUT** : ⏳ À démarrer après B7.S1
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev2
> **BLOQUE** : B7.S3 (AppSelector frontend), B7.S4 (provisioning workflow)
> **DÉPEND DE** : B7.S1 (`Tenant.vertical` FK + auth_vertical_scopes)
> **OBJECTIF** : Drop intégral du concept `brand_code` Catalogue (Q43=B verrouille 2 tenants distincts Marveline + Splendid). Suppression des colonnes `brand_code` sur Product/Category/Bundle/ProductCollection, suppression de `Tenant.is_multi_brand`, drop du header frontend `X-Brand-Code`, cleanup des filtres repository, invariant CI bloquant la réintroduction. **Migration data si actuellement multi-brand intra-tenant** : split du tenant unique en 2 tenants distincts (cf. T6).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B7.S2.T1** | TR-20 (réinterprété Q43=B) — Drop colonnes `brand_code` (Product, Category, Bundle, ProductCollection) | P0 | 1 j | T2 |
| **B7.S2.T2** | Drop colonne `Tenant.is_multi_brand` + drop header `X-Brand-Code` middleware | P0 | 0.5 j | T3 |
| **B7.S2.T3** | Cleanup filtres repository `WHERE brand_code IS NULL OR brand_code = :current_brand` | P0 | 1 j | T5 |
| **B7.S2.T4** | Migration data : si `brand_code` ≠ NULL en prod → split intra-tenant en 2 tenants distincts | P0 | 1 j | T1 |
| **B7.S2.T5** | Cleanup endpoints API : drop param `?brand_code=`, drop schemas `brand_code` field | P0 | 0.5 j | aucun |
| **B7.S2.T6** | Script CI invariant `tools/check_no_brand_code.py` | P0 | 0.5 j | aucun |
| **B7.S2.T7** | Frontend cleanup : drop store `currentBrandCode`, drop selector UI multi-brand | P1 | 0.5 j | aucun |

**Total effort** : 5 jours-homme.

---

# Story B7.S2.T1 — Drop colonnes `brand_code` Catalogue

## Contexte

**Décision** : Q43=B (verrouillée 2026-04-27) — Marveline et Splendid = 2 tenants distincts
**Sévérité** : P0 — colonnes mortes ou pire : code chemin différent selon `brand_code` → maintenance double
**Référence** : `architecture-cible.md §4.2.4` (annoté OBSOLÈTE) + §7.2

### Description

Aujourd'hui (post-Bloc 4 hypothétique avant Q43=B) : 4 colonnes `brand_code String(64) nullable` sur `products`, `categories`, `bundles`, `product_collections`. Après Q43=B, ces colonnes n'ont plus de sens (1 tenant = 1 brand par construction). Drop intégral.

## Solution

### Migration backward-compatible 4 étapes

```python
# alembic/versions/i1a2b3c4d5f2_drop_brand_code_step1_add_optional_lookup.py
"""Étape 1 : ajout helpers de transition (vue temporaire pour code legacy)."""
def upgrade() -> None:
    # Vue qui retourne brand_code = tenant.app_code pour compat code legacy pendant transition
    op.execute(text("""
        CREATE OR REPLACE VIEW products_with_legacy_brand AS
        SELECT p.*, t.app_code AS legacy_brand_code
        FROM products p JOIN tenants t ON t.id = p.tenant_id
    """))
    # Idem categories, bundles, product_collections

# alembic/versions/i1a2b3c4d5f3_drop_brand_code_step2_drop_columns.py
"""Étape 2 : drop colonnes (après refacto Python étape 1)."""
def upgrade() -> None:
    for table in ("products", "categories", "bundles", "product_collections"):
        with contextlib.suppress(Exception):
            op.drop_index(f"ix_{table}_brand_code", table_name=table)
        with contextlib.suppress(Exception):
            op.drop_constraint(f"uq_{table}_brand_code_X", table, type_="unique")
        with contextlib.suppress(Exception):
            op.drop_column(table, "brand_code")
    # Drop la vue legacy
    op.execute(text("DROP VIEW IF EXISTS products_with_legacy_brand CASCADE"))

def downgrade() -> None:
    for table in ("products", "categories", "bundles", "product_collections"):
        op.add_column(table, sa.Column("brand_code", sa.String(64), nullable=True))
```

### Cleanup modèles SQLAlchemy

```python
# app/models/product.py — avant
class Product(Base):
    brand_code: Mapped[str | None] = mapped_column(String(64), nullable=True)  # ❌ DROP

# après — colonne supprimée
class Product(Base):
    # ... (aucune mention brand_code)
```

### Tests

```python
async def test_product_brand_code_attribute_dropped(db, tenant):
    product = Product(tenant_id=tenant.id, name="Chaise")
    db.add(product); await db.commit()
    with pytest.raises(AttributeError):
        _ = product.brand_code  # colonne droppée

async def test_no_brand_code_in_select_star(db, tenant, product):
    """SELECT * ne contient plus brand_code."""
    cols = await db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'brand_code'
    """))
    assert cols.first() is None
```

## DoD

- [ ] Migration 2 étapes (vue legacy → drop colonnes)
- [ ] Modèles SQLAlchemy nettoyés (4 modèles)
- [ ] Indexes/UNIQUE référençant `brand_code` supprimés
- [ ] Test : AttributeError sur `product.brand_code`

---

# Story B7.S2.T2 — Drop `Tenant.is_multi_brand` + header `X-Brand-Code`

## Contexte

**Décision** : Q43=B — concept multi-brand intra-tenant disparait
**Sévérité** : P0 — code théâtre : `is_multi_brand` jamais lu après Q43=B

### Description

Drop :
- Colonne `Tenant.is_multi_brand` 
- Header `X-Brand-Code` du middleware `BrandCodeMiddleware` (drop intégral du middleware)
- Variable contextuelle `current_brand_code` du request context

## Solution

```python
# alembic/versions/i1a2b3c4d5f4_drop_tenant_is_multi_brand.py
def upgrade() -> None:
    with contextlib.suppress(Exception):
        op.drop_column("tenants", "is_multi_brand")

# app/middleware/__init__.py — drop import
# from app.middleware.brand_code import BrandCodeMiddleware  # ❌ DROP
# app.add_middleware(BrandCodeMiddleware)  # ❌ DROP

# app/middleware/brand_code.py → file deleted

# app/core/context.py — drop current_brand_code
# avant : current_brand_code: ContextVar[str | None] = ContextVar("brand_code", default=None)
# après : <ligne supprimée>
```

### Test

```python
async def test_tenant_no_is_multi_brand_attr(db):
    tenant = Tenant(app_code="test", vertical="location", legal_name="Test SARL")
    db.add(tenant); await db.commit()
    with pytest.raises(AttributeError):
        _ = tenant.is_multi_brand

async def test_x_brand_code_header_ignored(client):
    """Header X-Brand-Code n'est plus traité — pas d'erreur si présent (graceful)."""
    response = await client.get(
        "/api/v1/products",
        headers={"X-Brand-Code": "splendid"},
    )
    # Pas de filtre appliqué — résultat identique sans header
    assert response.status_code == 200
```

## DoD

- [ ] Colonne `Tenant.is_multi_brand` droppée
- [ ] Middleware `BrandCodeMiddleware` supprimé du fichier + de la chaîne
- [ ] `current_brand_code` ContextVar supprimé
- [ ] Test : AttributeError sur `tenant.is_multi_brand`
- [ ] Test : header `X-Brand-Code` ignoré (pas d'effet)

---

# Story B7.S2.T3 — Cleanup filtres repository

## Contexte

**Sévérité** : P0 — chemins SQL `WHERE brand_code IS NULL OR brand_code = :current_brand` ne fonctionnent plus (colonne droppée)

### Description

Tous les repositories doivent être nettoyés. Pattern à grep et remplacer :

```sql
-- AVANT
SELECT * FROM products
WHERE tenant_id = :tid
  AND (brand_code IS NULL OR brand_code = :current_brand)

-- APRÈS
SELECT * FROM products
WHERE tenant_id = :tid
```

## Solution

```bash
# Audit pré-cleanup
grep -rn "brand_code" app/repositories/ app/services/ --include="*.py"

# Cleanup mass replace via sed/script
```

```python
# Exemple app/repositories/product.py — avant
async def list_products(self, tenant_id: int, brand_code: str | None) -> list[Product]:
    query = select(Product).where(Product.tenant_id == tenant_id)
    if brand_code:
        query = query.where(or_(Product.brand_code.is_(None), Product.brand_code == brand_code))
    return (await self.db.scalars(query)).all()

# après
async def list_products(self, tenant_id: int) -> list[Product]:
    query = select(Product).where(Product.tenant_id == tenant_id)
    return (await self.db.scalars(query)).all()
```

### Tests

```python
async def test_list_products_no_brand_filter(db, tenant_marveline, tenant_splendid):
    """Tenant Marveline ne voit que ses produits — pas de filtre brand_code."""
    p_m = Product(tenant_id=tenant_marveline.id, name="Chaise Marveline")
    p_s = Product(tenant_id=tenant_splendid.id, name="Chaise Splendid")
    db.add_all([p_m, p_s]); await db.commit()

    # RLS context Marveline
    await db.execute(text("SET LOCAL app.current_tenant_id = :tid"), {"tid": tenant_marveline.id})
    products = await product_repo.list_products(tenant_marveline.id)
    assert len(products) == 1
    assert products[0].name == "Chaise Marveline"
```

## DoD

- [ ] `grep -rn "brand_code" app/` → 0 résultat
- [ ] Repositories simplifiés (drop param `brand_code`)
- [ ] Tests endpoints catalogue : isolation par tenant_id seul
- [ ] CI script (T6) bloque réintroduction

---

# Story B7.S2.T4 — Migration data : split intra-tenant si présent

## Contexte

**Sévérité** : P0 — si en prod un tenant a `brand_code` = 'marveline' et 'splendid' coexistant → drop colonne ferait perdre la distinction
**Précondition** : audit pré-deploy `SELECT DISTINCT brand_code, tenant_id FROM products WHERE brand_code IS NOT NULL` 

### Description

Si pré-deploy détecte un tenant `T` avec multiples `brand_code` :
1. Créer 2 tenants distincts `T_marveline`, `T_splendid` (provisioning B7.S4 simulé manuellement)
2. Move products/categories/bundles : `UPDATE ... SET tenant_id = T_marveline WHERE brand_code = 'marveline'`
3. Move ressources connexes (reservations, invoices, etc.) cross-table par `tenant_id`
4. Audit log + Outbox event `TenantSplit` pour traçabilité
5. Inactiver l'ancien tenant `T`

## Solution

### Script de migration data (one-shot manuel pré-deploy)

```python
# tools/migrate_split_multi_brand_tenant.py
"""USAGE : python tools/migrate_split_multi_brand_tenant.py --tenant-id=42 --dry-run
   Puis : python tools/migrate_split_multi_brand_tenant.py --tenant-id=42 --apply
"""
async def split_tenant(tenant_id: int, dry_run: bool):
    async with engine.begin() as conn:
        brands_present = await conn.scalars(text("""
            SELECT DISTINCT brand_code FROM products
            WHERE tenant_id = :tid AND brand_code IS NOT NULL
        """), {"tid": tenant_id})
        brands = [b for b in brands_present.all()]

        if len(brands) <= 1:
            print(f"Tenant {tenant_id} mono-brand : aucune migration nécessaire")
            return

        old_tenant = await conn.execute(text("SELECT * FROM tenants WHERE id = :tid"), {"tid": tenant_id})
        old = old_tenant.first()

        for brand in brands:
            new_app_code = f"{old.app_code}_{brand}"
            if dry_run:
                print(f"DRY-RUN: créer tenant {new_app_code}, déplacer products WHERE brand_code='{brand}'")
                continue

            # Créer nouveau tenant
            result = await conn.execute(text("""
                INSERT INTO tenants (app_code, vertical, legal_name, brand_display_name, ...)
                VALUES (:app_code, :vertical, :legal, :brand, ...)
                RETURNING id
            """), {
                "app_code": new_app_code,
                "vertical": old.vertical,
                "legal": f"{old.legal_name} ({brand})",
                "brand": brand.title(),
            })
            new_tenant_id = result.scalar()

            # Déplacer rows
            for table in ("products", "categories", "bundles", "product_collections"):
                await conn.execute(text(f"""
                    UPDATE {table} SET tenant_id = :new_tid
                    WHERE tenant_id = :old_tid AND brand_code = :brand
                """), {"new_tid": new_tenant_id, "old_tid": tenant_id, "brand": brand})

            # Déplacer ressources liées (reservations, invoices, etc.) — selon brand_code propagé
            # Si pas de propagation : analyse manuelle par customer_id

            # Audit
            await conn.execute(text("""
                INSERT INTO outbox_events (event_type, aggregate_id, tenant_id, payload, created_at)
                VALUES ('TenantSplit', :old_tid, :new_tid, :payload, NOW())
            """), {
                "old_tid": str(tenant_id), "new_tid": new_tenant_id,
                "payload": json.dumps({"split_brand": brand, "from_tenant": tenant_id}),
            })

        # Inactiver ancien tenant
        if not dry_run:
            await conn.execute(text("UPDATE tenants SET is_active = false WHERE id = :tid"), {"tid": tenant_id})
```

### Pré-deploy checklist

1. Run `--dry-run` sur prod copy
2. Backup DB complet
3. Run `--apply` en maintenance window
4. Verify : aucun tenant avec multiples `brand_code`
5. Run migration B7.S2.T1 (drop colonnes)

## DoD

- [ ] Script `tools/migrate_split_multi_brand_tenant.py` livré
- [ ] Mode `--dry-run` fonctionnel
- [ ] Audit Outbox `TenantSplit` event créé
- [ ] Test sur tenant fictif : split correct + ancien inactivé
- [ ] Runbook pré-deploy documenté

---

# Story B7.S2.T5 — Cleanup endpoints API + schemas

## Contexte

**Sévérité** : P0 — schemas Pydantic exposent `brand_code: str | None = None` qui ne sera plus jamais rempli

### Description

Cleanup :
- `ProductCreate`, `ProductRead`, `CategoryCreate`, etc. : drop field `brand_code`
- Endpoints `?brand_code=splendid` query param drop
- OpenAPI 52-api-contracts.openapi.yml : drop schema field

## Solution

```python
# app/schemas/product.py — avant
class ProductRead(BaseSchema):
    id: int
    name: str
    brand_code: str | None = None  # ❌ DROP

# après — field supprimé
```

```python
# app/api/v1/endpoints/products.py — avant
@router.get("/products")
async def list_products(brand_code: str | None = Query(None)):
    return await service.list(brand_code=brand_code)

# après
@router.get("/products")
async def list_products():
    return await service.list()
```

### OpenAPI cleanup

```yaml
# 52-api-contracts.openapi.yml
# Avant
components:
  schemas:
    Product:
      properties:
        brand_code:
          type: string
          nullable: true
# Après — propriété supprimée
```

### Tests E2E

```python
async def test_products_endpoint_no_brand_code_param(client):
    response = await client.get("/api/v1/products?brand_code=splendid")
    # Soit 422 (param invalide) soit 200 (param ignoré) — selon strict mode
    assert response.status_code in (200, 422)
    # Le résultat ne doit PAS contenir brand_code
    if response.status_code == 200:
        assert all("brand_code" not in p for p in response.json())
```

## DoD

- [ ] 4 schemas Product/Category/Bundle/Collection : drop `brand_code` field
- [ ] Endpoints : drop query param `brand_code`
- [ ] OpenAPI yml mis à jour
- [ ] Test E2E : réponse JSON sans `brand_code`

---

# Story B7.S2.T6 — Script CI invariant `check_no_brand_code.py`

## Contexte

**Sévérité** : P0 — sans garde-fou CI, un dev peut réintroduire `brand_code` par habitude

## Solution

```python
# tools/check_no_brand_code.py (NEW)
"""Refuse `brand_code` dans le code (post Q43=B drop).

Cohérent : 1 tenant = 1 brand par construction (`Tenant.app_code`).
"""
import re, sys
from pathlib import Path

PATTERNS = [
    re.compile(r"\bbrand_code\b"),
    re.compile(r"\bcurrent_brand_code\b"),
    re.compile(r"X-Brand-Code"),
    re.compile(r"is_multi_brand"),
]

EXEMPT_FILES = {
    "tools/check_no_brand_code.py",  # ce script
    "tools/migrate_split_multi_brand_tenant.py",  # migration data one-shot
    "alembic/versions/i1a2b3c4d5f3_drop_brand_code_step2_drop_columns.py",
    "docs/architecture-audit-2026-04-26/architecture-cible.md",  # mention historique
}

violations = []
for py in Path(".").rglob("*.py"):
    rel = str(py)
    if rel in EXEMPT_FILES or "site-packages" in rel or ".venv" in rel:
        continue
    text = py.read_text(errors="ignore")
    for pattern in PATTERNS:
        for m in pattern.finditer(text):
            line = text[:m.start()].count("\n") + 1
            violations.append(f"{rel}:{line} — '{m.group()}' interdit (Q43=B drop)")

if violations:
    print("❌ Q43=B violations :")
    print("\n".join(f"  - {v}" for v in violations))
    sys.exit(1)
print("✅ Q43=B — aucun brand_code")
```

### Intégration CI

```yaml
# .github/workflows/ci.yml
- name: Check no brand_code (Q43=B)
  run: python tools/check_no_brand_code.py
```

Ajouté à `54-ci-invariants.md` script #27.

## DoD

- [ ] Script `tools/check_no_brand_code.py` livré
- [ ] CI workflow exécute le script
- [ ] EXEMPT_FILES whitelist (script lui-même + migrations historiques)
- [ ] Test : `brand_code` réintroduit → exit 1

---

# Story B7.S2.T7 — Frontend cleanup

## Contexte

**Sévérité** : P1 — store `currentBrandCode` Zustand + selector UI multi-brand sont morts post-Q43=B

### Description

Cleanup frontend :
- `frontend/packages/shared/stores/brandStore.ts` → drop ou refacto
- Composant `<BrandSelector>` → drop
- Header axios `X-Brand-Code` → drop
- Tests E2E qui ouvrent multi-brand → drop

## Solution

```typescript
// frontend/packages/shared/stores/brandStore.ts — file deleted

// frontend/packages/shared/api/client.ts — avant
client.interceptors.request.use((config) => {
  config.headers["X-Brand-Code"] = useBrandStore.getState().currentBrandCode;
  return config;
});

// après — interceptor supprimé
// (tenant context propagé via cookie SSO + JWT, pas de header brand)
```

```tsx
// frontend/packages/shared/components/BrandSelector.tsx — file deleted

// frontend/apps/marveline/src/routes/__root.tsx — avant
<TopBar>
  <BrandSelector /> {/* DROP */}
  <UserMenu />
</TopBar>
```

### Tests

```typescript
// frontend/packages/shared/__tests__/api-client.test.ts
test("client n'envoie plus le header X-Brand-Code", async () => {
  await client.get("/products");
  expect(mockFetch.mock.calls[0][1].headers).not.toHaveProperty("X-Brand-Code");
});
```

## DoD

- [ ] `brandStore.ts` supprimé
- [ ] `<BrandSelector>` supprimé
- [ ] Header `X-Brand-Code` plus envoyé
- [ ] Test : pas de header brand sortant
- [ ] App Marveline démarre sans erreur post-cleanup

---

## Critères de succès Sprint B7.S2

- [ ] **Q43=B drop intégral** : 4 colonnes `brand_code` supprimées (Product, Category, Bundle, ProductCollection)
- [ ] `Tenant.is_multi_brand` supprimé
- [ ] `BrandCodeMiddleware` supprimé + ContextVar `current_brand_code` supprimé
- [ ] Filtres repository nettoyés (0 occurrence `brand_code` dans `app/`)
- [ ] Endpoints API + schemas Pydantic cleanés
- [ ] Frontend : store + selector + header X-Brand-Code supprimés
- [ ] **Migration data** : si tenant prod multi-brand → split en 2 tenants distincts via script + audit Outbox
- [ ] **CI invariant** : `tools/check_no_brand_code.py` actif sur PR
- [ ] Test E2E : Marveline tenant ne voit pas catalogue Splendid (isolation par `tenant_id` seul)

---

**Fin du document — 17-sprint-B7.S2.md**
