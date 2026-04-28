# Sprint B2.S3 — RBAC unifié + auth_vertical_scopes

> **STATUT** : ⏳ À démarrer après B2.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2 — collaboration Dev1 (B1.S1.T2 ApiKey context déjà fixé)
> **BLOQUE** : tout B3-B7 (scopes utilisés partout)
> **DÉPEND DE** : **B1.S1.T2 (F02 ApiKey set_tenant_context fixé)** + B1.S1 invariant CI `check_token_creator_passes_db.py`
> **OBJECTIF** : Migration RBAC v2 (`Permission` enum) → v3 (`Scope` enum `domain:action` 62 valeurs) + table `auth_vertical_scopes` + suppression `UserCompat`/`auth_role_scopes_fallback` permanent. **Sprint critique car effet placebo R25 si F329 non préalablement corrigé**.

⚠️ **R25 — placebo critical** : Cf. `05-risk-register.md` R25. Si **F329 (`token.py:49` `get_role_scopes(role, None)`)** n'est pas corrigé en B1.S1 préalablement, ce sprint livre une infrastructure inerte (table `auth_vertical_scopes` créée mais jamais lue à l'émission JWT). **Vérifier que `check_token_creator_passes_db.py` (54 §19) est vert AVANT d'engager B2.S3**.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B2.S3.T1** | DDL `auth_vertical_scopes` + `auth_role_scopes` + seed scopes par vertical | 1 j | T2 |
| **B2.S3.T2** | F329 `token.py` lit DB (passe `db` au lieu de `None`) — désactive placebo R25 | 1 j | T3 |
| **B2.S3.T3** | F407 ApiKey scopes Permission v2 → Scope v3 | 0.5 j | aucun |
| **B2.S3.T4** | F408 `cleanup_expired` AttributeError tenant_id fix | 0.5 j | aucun |
| **B2.S3.T5** | Migration ~40 endpoints `require_permission` → `require_scope` | 3 j | merge B2 |
| **B2.S3.T6** | Drop `UserCompat`, `Permission` enum v2, `ROLE_SCOPES_FALLBACK` runtime | 1 j | aucun |

**Total effort** : 7 jours-homme. **Sprint le plus dense Bloc 2**.

---

# Story B2.S3.T1 — DDL `auth_vertical_scopes` + `auth_role_scopes` + seed

## Contexte

**Décision** : Phase 1 §2.5 — Scope enum unique 62 valeurs format `domain:action`
**DDL** : `50-sql-schema.md §2.2`

### Description

2 tables :
- `auth_vertical_scopes(vertical_code, scope_name)` — quels scopes sont attribuables sur quel vertical (ex: `restaurant:write` uniquement sur tenants `vertical='restaurant'`)
- `auth_role_scopes(role_name, scope_name)` — quels scopes appartiennent à quel rôle (admin, manager, staff, …)

## Solution

DDL déjà spécifié dans `50-sql-schema.md §2.2`. Seed à compléter :

```sql
-- Seed auth_vertical_scopes — 4 verticals × ~20 scopes chacun
INSERT INTO auth_vertical_scopes (vertical_code, scope_name) VALUES
  -- Vertical 'location' (Marveline, Splendid)
  ('location', 'reservations:read'), ('location', 'reservations:write'),
  ('location', 'reservations:cancel'), ('location', 'devis:read'),
  ('location', 'devis:write'), ('location', 'devis:convert'),
  ('location', 'invoices:read'), ('location', 'invoices:write'),
  ('location', 'invoices:emit_credit_note'),
  ('location', 'customers:read'), ('location', 'customers:write'),
  ('location', 'customers:read_pii'), ('location', 'customers:import'),
  ('location', 'products:read'), ('location', 'products:write'),
  ('location', 'stock:read'), ('location', 'stock:write'),
  ('location', 'pricing:read'), ('location', 'pricing:write'),
  ('location', 'loyalty:read'), ('location', 'loyalty:write'),
  ('location', 'tenants:admin'),

  -- Vertical 'epicerie' (MassaCorp Épicerie)
  ('epicerie', 'ventes:read'), ('epicerie', 'ventes:write'),
  ('epicerie', 'ventes:refund'),
  ('epicerie', 'stock:read'), ('epicerie', 'stock:write'),
  ('epicerie', 'stock:transfer'),
  ('epicerie', 'etl:read'), ('epicerie', 'etl:write'),
  ('epicerie', 'customers:read'), ('epicerie', 'customers:write'),
  ('epicerie', 'loyalty:read'), ('epicerie', 'loyalty:write'),
  ('epicerie', 'tenants:admin'),

  -- Vertical 'restaurant' (MassaCorp Resto)
  ('restaurant', 'commandes:read'), ('restaurant', 'commandes:write'),
  ('restaurant', 'commandes:pay'),
  ('restaurant', 'instances:read'), ('restaurant', 'instances:launch'),
  ('restaurant', 'recettes:read'), ('restaurant', 'recettes:write'),
  ('restaurant', 'tenants:admin'),

  -- Vertical 'autour_de_table' (futur)
  ('autour_de_table', 'commandes:read'),
  ('autour_de_table', 'commandes:write'),
  ('autour_de_table', 'tenants:admin'),

  -- Scopes globaux DEVUP (admin opérateur SaaS)
  ('location', 'tenants:provision'), ('epicerie', 'tenants:provision'),
  ('restaurant', 'tenants:provision'), ('autour_de_table', 'tenants:provision'),
  ('location', 'admin:read'), ('epicerie', 'admin:read'),
  ('restaurant', 'admin:read'), ('autour_de_table', 'admin:read');

-- Seed auth_role_scopes — 6 rôles client + 2 rôles DEVUP plateforme (Q9=A 6 rôles tenant + cross-tenant)
-- ROLES TENANT-SCOPED (héritent du vertical du tenant) :
--   admin    : tous scopes du vertical du tenant
--   manager  : read+write mais pas admin/provision
--   staff    : read+ventes:write+commandes:write
--   viewer   : read only
--   api      : scope subset pour ApiKey machine-to-machine (NON UI, F02 ApiKey context)
--   superadmin (renamed devup_admin) : admin DEVUP plateforme cross-tenant
-- ROLES CROSS-TENANT DEVUP (vertical='*') :
--   devup_admin   : tenants:provision sur tous verticals
--   devup_support : admin:read sur tous verticals
INSERT INTO auth_role_scopes (role_name, scope_name) VALUES
  ('admin', 'reservations:read'), ('admin', 'reservations:write'),
  ('admin', 'reservations:cancel'),
  ('admin', 'devis:read'), ('admin', 'devis:write'), ('admin', 'devis:convert'),
  -- ... etc — détail dans la migration B2.S3.T1
  ('viewer', 'reservations:read'), ('viewer', 'devis:read'),
  ('viewer', 'invoices:read'), ('viewer', 'customers:read'),
  -- Rôle 'api' (Q9=A) : scope minimal machine-to-machine
  ('api', 'reservations:read'), ('api', 'devis:read'),
  ('api', 'customers:read'), ('api', 'pricing:read'),
  ('api', 'products:read'),
  -- Rôles DEVUP plateforme cross-tenant (vertical='*')
  ('devup_admin', 'tenants:provision'), ('devup_admin', 'admin:read'),
  ('devup_support', 'admin:read');
```

**Note Q9 nomenclature** : Q9=A verrouille "6 rôles globaux fixes : admin / manager / staff / viewer / api / superadmin". Implémentation :
- 4 rôles client tenant-scoped : `admin`, `manager`, `staff`, `viewer`
- 1 rôle machine-to-machine : `api` (utilisé par ApiKey post-B1.S1.T2)
- 1 rôle plateforme : `superadmin` ≡ `devup_admin` (renommage explicite pour DEVUP plateforme cross-tenant)
- + 1 rôle annexe `devup_support` (sub-set superadmin pour ops support DEVUP)

## DoD

- [ ] Migration DDL `auth_vertical_scopes` + `auth_role_scopes` appliquée
- [ ] Seed 62 scopes × 4 verticals = ~150 entrées `auth_vertical_scopes`
- [ ] **Q9=A** : 6 rôles seed (admin/manager/staff/viewer/api/superadmin=devup_admin) + 1 annexe (devup_support)
- [ ] Rôle `api` documenté pour ApiKey M2M (cohérent B1.S1.T2 ApiKey context)
- [ ] CI invariant `check_scope_catalog.py` (54 §5) vert

---

# Story B2.S3.T2 — F329 `token.py` lit DB (désactive placebo R25)

## Contexte

**Friction** : F329 (vague 4 V4-P0-02)
**Sévérité** : **CRITICAL** — sans ce fix, B2.S3 = placebo total
**Code source** : `app/services/token.py:49` + `app/services/rbac.py:185-222`

### Description

```python
# app/services/token.py:49 (état actuel — placebo)
async def create_access_token(account_id, tenant_id, role, ...):
    scopes = await get_role_scopes(role, None)  # ← db=None → fallback ROLE_SCOPES_FALLBACK
    ...

# app/services/rbac.py:185-222
async def get_role_scopes(role_name: str, db: Optional[AsyncSession] = None) -> list[str]:
    if db is None:
        return ROLE_SCOPES_FALLBACK.get(role_name, [])  # ← branche systématique en prod
    # Branche DB jamais atteinte
    result = await db.execute(select(AuthRoleScope).filter_by(role_name=role_name))
    return [row.scope_name for row in result.scalars()]
```

**Conséquence** : table `auth_role_scopes` créée mais jamais lue → tout changement de scopes en DB silencieusement ignoré.

## Solution

```python
# app/services/token.py (refacto)
async def create_access_token(
    account_id: int,
    tenant_id: int,
    role: str,
    db: AsyncSession,  # ← MAINTENANT REQUIS
    audience: str,
) -> str:
    """F329 fix : db obligatoire pour lire auth_role_scopes ∩ auth_vertical_scopes.

    Resolution :
    1. scopes du rôle (auth_role_scopes WHERE role_name=role)
    2. ∩ scopes autorisés sur le vertical (auth_vertical_scopes WHERE vertical_code=tenant.vertical)
    3. Fallback ROLE_SCOPES_FALLBACK UNIQUEMENT si db down (R23 dégradé) — pas par défaut
    """
    try:
        scopes = await get_role_scopes_v3(db, role, tenant_id)
    except DatabaseUnavailable:
        # R23 — mode dégradé : fallback safety net
        logger.warning("RBAC fallback used (DB down) for role=%s tenant_id=%s", role, tenant_id)
        scopes = ROLE_SCOPES_FALLBACK.get(role, [])

    return jwt.encode({
        "sub": str(account_id),
        "tenant_id": str(tenant_id),
        "scopes": scopes,
        "type": TokenType.ACCESS.value,  # F47 fix Sprint 1
        "aud": audience,
        "exp": ...,
    }, ...)


# app/services/rbac.py
async def get_role_scopes_v3(
    db: AsyncSession,
    role_name: str,
    tenant_id: int,
) -> list[str]:
    """Lit DB : auth_role_scopes ∩ auth_vertical_scopes selon vertical du tenant.

    F329 fix : DB obligatoire (sinon `get_role_scopes_v3` lève TypeError).
    """
    # 1. Récupère le vertical du tenant
    tenant = await db.get(Tenant, tenant_id)
    if not tenant:
        raise NotFoundError(f"Tenant {tenant_id} not found")

    # 2. Intersection : scopes du rôle ∩ scopes autorisés sur ce vertical
    query = text("""
        SELECT ars.scope_name
        FROM auth_role_scopes ars
        INNER JOIN auth_vertical_scopes avs ON avs.scope_name = ars.scope_name
        WHERE ars.role_name = :role
        AND avs.vertical_code = :vertical
    """)
    result = await db.execute(query, {"role": role_name, "vertical": tenant.vertical})
    return [row.scope_name for row in result.fetchall()]
```

## CI invariant `check_token_creator_passes_db.py` (54 §19)

Déjà spécifié vague 6 — refuse merge si `get_role_scopes(role, None)` détecté en AST.

## Tests

```python
@pytest.mark.asyncio
async def test_create_access_token__reads_db_not_fallback(db, tenant, account):
    """F329 fix : tokens reflètent les scopes DB, pas le fallback."""
    # Modifier la DB : retirer un scope du rôle admin
    await db.execute(
        delete(AuthRoleScope).where(
            AuthRoleScope.role_name == "admin",
            AuthRoleScope.scope_name == "loyalty:write"
        )
    )
    await db.flush()

    token = await create_access_token(
        account_id=account.id, tenant_id=tenant.id, role="admin",
        db=db, audience=tenant.app_code,
    )
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, ...)

    # Le scope retiré ne doit PAS être dans le JWT
    assert "loyalty:write" not in payload["scopes"], (
        "F329 régression : token reflète fallback hardcodé au lieu de DB"
    )
```

## DoD

- [ ] `create_access_token(..., db: AsyncSession)` signature mise à jour
- [ ] `get_role_scopes_v3(db, role, tenant_id)` lit DB
- [ ] Fallback `ROLE_SCOPES_FALLBACK` uniquement en mode dégradé (R23)
- [ ] CI invariant `check_token_creator_passes_db.py` vert (0 call-site `db=None`)
- [ ] Test E2E : modifier scope DB → JWT régénéré reflète changement
- [ ] R25 marqué résolu

## Risque

- Probabilité 2, impact 5 → score 10 HIGH
- Mitigation : validation pré-merge invariant CI

---

# Story B2.S3.T3 — F407 ApiKey scopes Permission v2 → Scope v3

## Contexte

**Friction** : F407 (vague 5 V5-P0-08)
**Sévérité** : **P0 PROD** — modules v3 (Bloc 5+) inutilisables M2M car `Scope.EPICERIE_READ` rejeté avec "Scopes invalides"
**Code source** : `app/services/api_key.py:84` + `app/schemas/api_key.py:10,54,105`

### Description

```python
# app/services/api_key.py:84 (état actuel)
def _validate_scopes(self, scopes: list[str]) -> None:
    valid_scopes = {p.value for p in Permission}  # ← v2 enum
    invalid = [s for s in scopes if s not in valid_scopes]
    if invalid:
        raise ValueError(f"Scopes invalides : {invalid}")
```

L'utilisateur tente de créer une API key avec scopes `["epicerie:read", "ventes:write"]` → 400 car ces scopes existent en v3 mais pas dans `Permission` v2.

## Solution

```python
# app/services/api_key.py (corrigé)
from app.permissions.scope import Scope

class ApiKeyService:
    def _validate_scopes(self, scopes: list[str]) -> None:
        """F407 fix : validation contre Scope v3 (62 valeurs domain:action)."""
        valid_scopes = {s.value for s in Scope}
        invalid = [s for s in scopes if s not in valid_scopes]
        if invalid:
            raise ValueError(f"Scopes invalides : {invalid}. Valides : {sorted(valid_scopes)}")


# app/schemas/api_key.py (corrigé)
from app.permissions.scope import Scope

_VALID_SCOPES = {s.value for s in Scope}  # F407 fix


class ApiKeyCreate(BaseSchema):
    name: str
    scopes: list[str]
    expires_at: Optional[datetime] = None

    @field_validator("scopes")
    def validate_scopes(cls, v):
        invalid = [s for s in v if s not in _VALID_SCOPES]
        if invalid:
            raise ValueError(f"Scopes invalides : {invalid}")
        return v
```

## DoD

- [ ] `services/api_key.py:_validate_scopes` lit `Scope` enum v3
- [ ] `schemas/api_key.py:_VALID_SCOPES` idem
- [ ] Test : créer ApiKey avec `["epicerie:read"]` → 201 (au lieu de 400)
- [ ] CI invariant `check_scope_catalog.py` (54 §5) étendu : valide aussi `_VALID_SCOPES`

## Risque

- Probabilité 1, impact 4 → score 4 LOW

---

# Story B2.S3.T4 — F408 `cleanup_expired` AttributeError tenant_id fix

## Contexte

**Friction** : F408 (vague 5 V5-P1-04)
**Sévérité** : P1 — task Celery cleanup tokens expirés crashe au premier appel
**Code source** : `app/repositories/password_reset_token.py:124, 196`

### Description

```python
# password_reset_token.py:124, 196 (état actuel)
async def cleanup_expired(self, db, tenant_id: int):
    await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < now_utc(),
            PasswordResetToken.tenant_id == tenant_id,  # ← AttributeError
        )
    )
```

`PasswordResetToken` (modèle IAM v2) ne mappe pas `tenant_id` → AttributeError dès le premier appel de la task Celery.

## Solution

Tokens reset password sont liés à `account_id` (pas tenant) car un account peut avoir plusieurs memberships.

```python
# app/repositories/password_reset_token.py (corrigé)
async def cleanup_expired(self, db: AsyncSession) -> int:
    """F408 fix : cleanup global (tokens password reset = scope account, pas tenant).

    Si filtrage par tenant souhaité : passer par account_id JOIN tenant_memberships.
    """
    result = await db.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < now_utc()
        ).returning(PasswordResetToken.id)
    )
    deleted_count = len(result.fetchall())
    return deleted_count
```

## DoD

- [ ] `cleanup_expired()` sans paramètre `tenant_id`
- [ ] Task Celery `cleanup_password_reset_tokens` opérationnelle (pas de crash)
- [ ] Test : 5 tokens expirés en DB → cleanup → 0 restant

---

# Story B2.S3.T5 — Migration ~40 endpoints `require_permission` → `require_scope`

## Contexte

**Sévérité** : P0 — migration RBAC v2 → v3 sur tous les endpoints

### Description

Audit grep `require_permission` dans `app/api/v1/`. Estimation : ~40 endpoints à migrer.

```python
# AVANT (legacy v2)
@router.get("/customers")
async def list_customers(
    current_user: User = Depends(require_permission(Permission.CUSTOMER_READ)),
):
    ...

# APRÈS (v3)
@router.get("/customers")
async def list_customers(
    current_principal: Principal = Depends(require_scope(Scope.CUSTOMERS_READ)),
):
    ...
```

## Solution

Approche progressive : 5-10 endpoints par PR pour limiter blast radius.

```python
# app/core/deps.py
def require_scope(*scopes: Scope):
    """Décorateur FastAPI pour vérifier scopes dans le JWT principal."""
    async def dependency(
        principal: Principal = Depends(get_current_principal),
    ) -> Principal:
        token_scopes = set(principal.scopes)
        required = {s.value for s in scopes}
        missing = required - token_scopes
        if missing:
            raise HTTPException(403, f"Missing scopes: {sorted(missing)}")
        return principal
    return dependency
```

## DoD

- [ ] `require_scope` decorator opérationnel
- [ ] ~40 endpoints migrés (audit `grep require_permission` → 0 résultats)
- [ ] CI invariant `check_endpoint_scopes.py` (54 §1) vert sur 100% endpoints
- [ ] 0 régression test E2E

## Risque

- Probabilité 4, impact 4 → score 16 CRITICAL
- Mitigation : pair-programming + déploiement progressif (10 endpoints/PR), feature flag `rbac_v3_enabled` per-endpoint

---

# Story B2.S3.T6 — Drop `UserCompat`, `Permission` enum v2, `ROLE_SCOPES_FALLBACK` runtime

## Contexte

**Sévérité** : P1 — nettoyage final post-migration

### Description

Une fois T5 terminé (0 endpoint legacy), on peut supprimer définitivement :
- `app/core/deps.py:UserCompat` class (legacy)
- `app/permissions/permission.py:Permission` enum v2
- Décorateur `require_permission`
- `ROLE_SCOPES_FALLBACK` retiré du runtime (gardé uniquement comme safety-net mode dégradé R23 — appelé exceptionnellement)

## DoD

- [ ] `UserCompat` supprimée
- [ ] `Permission` enum supprimée (drop fichier `app/permissions/permission.py`)
- [ ] CI invariant `check_no_userpcompat.py` (vague 1) vert
- [ ] CI invariant `check_no_permission_v2.py` (NEW) vert
- [ ] `ROLE_SCOPES_FALLBACK` annoté `# Used only in degraded mode (R23 fallback)`

---

## Critères de succès Sprint B2.S3

- [ ] `auth_vertical_scopes` + `auth_role_scopes` peuplés (~150 + ~80 entrées)
- [ ] **F329 fix vérifié** : `token.py` lit DB — JWT reflète changements DB
- [ ] **R25 placebo résolu** : `check_token_creator_passes_db.py` vert
- [ ] **F407 fix** : ApiKey accepte scopes v3 (`epicerie:read`, etc.)
- [ ] **F408 fix** : cleanup tasks Celery opérationnelles
- [ ] ~40 endpoints migrés v2 → v3
- [ ] `UserCompat` + `Permission` enum supprimées
- [ ] CI 100% verte

---

**Fin du document — 12-sprint-B2.S3.md**
