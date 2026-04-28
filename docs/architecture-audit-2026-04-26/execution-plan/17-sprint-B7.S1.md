# Sprint B7.S1 — Tenant.vertical NOT NULL + auth_vertical_scopes

> **STATUT** : ⏳ À démarrer après B7 démarré (post-Bloc 6)
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev2
> **BLOQUE** : B7.S2 (drop brand_code), B7.S3 (AppSelector), B7.S4 (provisioning)
> **DÉPEND DE** : B2.S2 (table verticals), B2.S3 (RBAC unifié)
> **OBJECTIF** : Migrer `Tenant.vertical NOT NULL` (cohérent Q43=B). Drop CHECK enum strict `app_code` (élargir à regex `^[a-z][a-z0-9_]+$` + UNIQUE). Ajouter colonnes `brand_*` (white-label per-tenant). Renommer table `auth_app_scopes` → `auth_vertical_scopes`. Mapping RBAC scopes par `vertical:*` (pas par `app_code`).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B7.S1.T1** | `Tenant.vertical NOT NULL` migration + backfill (cohérent B2.S2.T2 préparé) | P0 | 1 j | T2, T3 |
| **B7.S1.T2** | Drop CHECK enum `app_code` strict + élargir à regex `^[a-z][a-z0-9_]+$` + UNIQUE | P0 | 0.5 j | aucun |
| **B7.S1.T3** | Colonnes `brand_*` Tenant (display_name, logo_url, primary_color, dkim_domain) | P0 | 0.5 j | aucun |
| **B7.S1.T4** | Rename `auth_app_scopes` → `auth_vertical_scopes` + migration FK | P0 | 1 j | aucun |
| **B7.S1.T5** | RBAC mapping JWT : scopes par vertical (`location:read`, `epicerie:read`, etc.) — drop `marveline:*` | P0 | 1.5 j | aucun |
| **B7.S1.T6** | CI invariant `tools/check_no_app_code_in_scopes.py` | P1 | 0.5 j | aucun |

**Total effort** : 5 jours-homme.

---

# Story B7.S1.T1 — `Tenant.vertical NOT NULL`

## Contexte

**Décision** : Q43=B verrouillée + cohérent B2.S2.T2 prep
**Sévérité** : P0 — sans `vertical`, multi-vertical DEVUP impossible
**Code source** : `app/models/tenant.py`

### Description

Cible :
- Ajouter `Tenant.vertical String(64)` NOT NULL
- Backfill : Marveline → 'location', CaroCorp_epi → 'epicerie', CaroCorp_resto → 'restaurant'
- FK vers table `verticals(code)` (B2.S2.T2)

## Solution

### Migration

```python
# alembic/versions/l1a2b3c4d610_tenant_vertical_not_null.py
def upgrade() -> None:
    # Étape 1 : add nullable
    op.add_column("tenants", sa.Column("vertical", sa.String(64), nullable=True))
    op.create_foreign_key(
        "fk_tenants_vertical", "tenants", "verticals",
        ["vertical"], ["code"], ondelete="RESTRICT",
    )
    # Étape 2 : backfill (mapping app_code → vertical)
    op.execute(text("""
        UPDATE tenants SET vertical = CASE
            WHEN app_code IN ('marveline', 'splendid', 'splendid_events') THEN 'location'
            WHEN app_code LIKE '%_epi' OR app_code LIKE '%_epicerie' THEN 'epicerie'
            WHEN app_code LIKE '%_resto' OR app_code LIKE '%_restaurant' THEN 'restaurant'
            WHEN app_code LIKE '%_table' OR app_code LIKE '%_autour_de_table' THEN 'autour_de_table'
            ELSE 'location'  -- fallback
        END
    """))
    # Étape 3 : NOT NULL
    op.alter_column("tenants", "vertical", nullable=False)
```

### Modèle

```python
# app/models/tenant.py
class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    id: Mapped[int]
    app_code: Mapped[str]
    vertical: Mapped[str] = mapped_column(ForeignKey("verticals.code", ondelete="RESTRICT"), nullable=False)
    # ... autres
```

### Test

```python
async def test_tenant_vertical_required(db):
    with pytest.raises(IntegrityError):
        tenant = Tenant(app_code="test", legal_name="Test")  # pas de vertical
        db.add(tenant); await db.commit()

async def test_tenant_vertical_fk_to_verticals_table(db, vertical_location):
    tenant = Tenant(app_code="x", legal_name="X", vertical="location")
    db.add(tenant); await db.commit()
    # FK valide

async def test_tenant_invalid_vertical_refused(db):
    with pytest.raises(IntegrityError, match="fk_tenants_vertical"):
        tenant = Tenant(app_code="x", legal_name="X", vertical="nonexistent")
        db.add(tenant); await db.commit()
```

## DoD

- [ ] Migration 3 étapes (add → backfill → NOT NULL)
- [ ] FK `verticals(code)`
- [ ] Backfill 4 valeurs (location/epicerie/restaurant/autour_de_table)
- [ ] Test : INSERT sans vertical → IntegrityError
- [ ] Test : vertical inconnu → IntegrityError

---

# Story B7.S1.T2 — Drop CHECK enum `app_code` + UNIQUE + regex

## Contexte

**Sévérité** : P0 — actuellement `Tenant.app_code CHECK (app_code IN ('marveline', 'splendid', ...))` hardcoded → ajouter un nouveau tenant = migration

### Description

Cible :
- Drop CHECK enum strict
- Add CHECK regex `^[a-z][a-z0-9_]{2,63}$`
- Garder UNIQUE

## Solution

```python
def upgrade() -> None:
    with contextlib.suppress(Exception):
        op.drop_constraint("check_tenants_app_code", "tenants")
    op.create_check_constraint(
        "ck_tenants_app_code_format",
        "tenants",
        "app_code ~ '^[a-z][a-z0-9_]{2,63}$'",
    )
    # UNIQUE déjà en place normalement
```

### Test

```python
async def test_tenant_app_code_regex(db):
    # Valide
    Tenant(app_code="marveline_v2", legal_name="X", vertical="location")
    Tenant(app_code="client_x_resto", legal_name="X", vertical="restaurant")
    # Invalide
    with pytest.raises(IntegrityError, match="ck_tenants_app_code_format"):
        db.add(Tenant(app_code="UPPERCASE", ...)); await db.commit()
    with pytest.raises(IntegrityError):
        db.add(Tenant(app_code="ab", ...)); await db.commit()  # < 3 chars
```

## DoD

- [ ] CHECK regex actif
- [ ] Test : `UPPERCASE`, `ab`, `123start` refusés
- [ ] Test : `marveline_v2`, `client_x_resto` acceptés

---

# Story B7.S1.T3 — Colonnes `brand_*` Tenant

## Contexte

**Décision** : Q44=A+C — white-label per-tenant
**Référence** : `architecture-cible.md §7.2 lignes 2120-2127`

## Solution

```python
def upgrade() -> None:
    op.add_column("tenants", sa.Column("brand_display_name", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("brand_logo_url", sa.String(512), nullable=True))
    op.add_column("tenants", sa.Column("brand_primary_color", sa.String(7), nullable=True))  # hex #RRGGBB
    op.add_column("tenants", sa.Column("brand_email_from", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("brand_dkim_domain", sa.String(255), nullable=True))
    op.create_check_constraint(
        "ck_tenants_brand_color_hex",
        "tenants",
        "brand_primary_color IS NULL OR brand_primary_color ~ '^#[0-9A-Fa-f]{6}$'",
    )
    # Backfill display_name = legal_name si NULL
    op.execute(text("UPDATE tenants SET brand_display_name = legal_name WHERE brand_display_name IS NULL"))
    op.alter_column("tenants", "brand_display_name", nullable=False)
```

## DoD

- [ ] 5 colonnes brand_* migration
- [ ] CHECK hex sur primary_color
- [ ] backfill `display_name = legal_name`
- [ ] Test : INSERT sans brand_display_name → IntegrityError

---

# Story B7.S1.T4 — Rename `auth_app_scopes` → `auth_vertical_scopes`

## Contexte

**Sévérité** : P0 — table existe mais nommée par app_code, doit être par vertical (Q43=B drop brand)

### Description

Cible : rename table + colonne `app_code` → `vertical_code`. Pré-requis B2.S3 (RBAC unifié) déjà migré vers vertical_scopes.

## Solution

```python
def upgrade() -> None:
    # Si déjà renommé en B2.S3 → no-op
    op.execute(text("""
        ALTER TABLE IF EXISTS auth_app_scopes RENAME TO auth_vertical_scopes;
    """))
    op.execute(text("""
        ALTER TABLE auth_vertical_scopes RENAME COLUMN app_code TO vertical_code;
    """))
    # FK update
    op.drop_constraint("fk_auth_app_scopes_app_code", "auth_vertical_scopes", type_="foreignkey")
    op.create_foreign_key(
        "fk_auth_vertical_scopes_vertical_code",
        "auth_vertical_scopes", "verticals",
        ["vertical_code"], ["code"], ondelete="CASCADE",
    )
```

## DoD

- [ ] Table renommée
- [ ] Colonne renommée
- [ ] FK pointe vers `verticals.code`
- [ ] Test : SELECT auth_vertical_scopes fonctionne

---

# Story B7.S1.T5 — RBAC scopes par vertical

## Contexte

**Sévérité** : P0 — JWT actuel `{scopes: ['marveline:read']}` → doit être `{scopes: ['location:read']}`

### Description

Cible : drop tout scope `app_code:*`, utiliser `vertical:*`.

## Solution

```python
# app/constants/security.py
class Scope(str, Enum):
    # Vertical-based (pas app_code-based)
    LOCATION_READ = "location:read"
    LOCATION_WRITE = "location:write"
    EPICERIE_READ = "epicerie:read"
    EPICERIE_WRITE = "epicerie:write"
    RESTAURANT_READ = "restaurant:read"
    RESTAURANT_WRITE = "restaurant:write"
    AUTOUR_DE_TABLE_READ = "autour_de_table:read"
    AUTOUR_DE_TABLE_WRITE = "autour_de_table:write"
```

### JWT issuance

```python
# app/services/auth/token.py
async def issue_access_token(account: Account, tenant: Tenant) -> str:
    scopes = await self._resolve_scopes(account.id, tenant.id)  # depuis auth_vertical_scopes
    payload = {
        "sub": str(account.id),
        "tenant_id": tenant.id,
        "vertical": tenant.vertical,  # ajout
        "scopes": scopes,  # ['location:read', 'location:write']
        "exp": ...,
    }
    return jwt.encode(payload, ...)
```

### Migration data

```python
# Convertir scopes existants : app_code → vertical
# Mapping :
#   marveline:* → location:*
#   splendid:* → location:*  (Q43=B : Splendid = aussi location vertical)
#   carocorp_epi:* → epicerie:*
#   carocorp_resto:* → restaurant:*
```

## DoD

- [ ] Scope enum vertical-based
- [ ] JWT issuance utilise vertical
- [ ] Migration scopes auth_vertical_scopes
- [ ] Test : user Marveline reçoit `location:read` (pas `marveline:read`)

---

# Story B7.S1.T6 — CI invariant `check_no_app_code_in_scopes`

## Solution

```python
# tools/check_no_app_code_in_scopes.py
"""Refuse `app_code:*` ou `marveline:*`/`splendid:*` dans le code."""
PATTERNS = [
    re.compile(r"['\"](marveline|splendid|carocorp[a-z_]*):"),
    re.compile(r"app_code\s*\+\s*['\"]:"),  # construction dynamique
]
```

## DoD

- [ ] Script CI
- [ ] EXEMPT_FILES : migrations historiques, ce script
- [ ] Test : code avec `'marveline:read'` → CI fail

---

## Critères de succès Sprint B7.S1

- [ ] **Tenant.vertical NOT NULL** + FK verticals
- [ ] **app_code** : drop CHECK enum, regex format, UNIQUE
- [ ] **brand_*** colonnes white-label
- [ ] **auth_vertical_scopes** renommée
- [ ] **Scopes vertical-based** : `location:*`, `epicerie:*`, `restaurant:*`, `autour_de_table:*`
- [ ] CI invariant
- [ ] Test E2E : user Marveline → JWT contient `location:read`

---

**Fin du document — 17-sprint-B7.S1.md**
