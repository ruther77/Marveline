# Sprint B2.S5 — auth_factors unifié

> **STATUT** : ⏳ À démarrer après B2.S4
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev2
> **BLOQUE** : aucun (dernier sprint Bloc 2)
> **DÉPEND DE** : B1.S3 (KMS — chiffrement TOTP secret), B2.S4 (MFA flows finalisés)
> **OBJECTIF** : Migration des 3 modèles MFA legacy (`MFADevice`, `WebAuthnCredential`, `TrustedDevice` PIN) vers une seule table unifiée `auth_factors` (Q6=B). Drop legacy + recovery codes 96 bits NIST compliant.

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B2.S5.T1** | DDL `auth_factors` (déjà spec 50 §2.1) + indexes + XOR CHECK | 0.5 j | T2 |
| **B2.S5.T2** | Migration data : `MFADevice` + `WebAuthnCredential` + `TrustedDevice` → `auth_factors` | 2 j | T3 |
| **B2.S5.T3** | Service `AuthFactorService` + drop legacy | 1.5 j | T4 |
| **B2.S5.T4** | F296 consolidation `verify_credentials` `hashed_password=None` (Sprint 1 follow-up) | 0.5 j | aucun |
| **B2.S5.T5** | Recovery codes 96 bits + chiffrement KMS (V4-P2-02) | 1 j | aucun |
| **B2.S5.T6** | **Q7=A** Migration `Account.address`/`postal_code`/`city`/`country` → `Customer` (RGPD purge cascade tenant-naturelle) | P0 | 1 j | aucun |

**Total effort** : 6.5 jours-homme.

---

# Story B2.S5.T1 — DDL `auth_factors`

## Contexte

**Décision** : Q6=B unification — Phase 1 §2.7 ligne 471-507
**DDL** : `50-sql-schema.md §2.1` (déjà rédigé Phase 3 — table créée par cette story)

### Description

Cf. `50-sql-schema.md §2.1` pour le DDL complet. Points clés :
- `__tablename__ = "auth_factors"` (pluriel — corrigé vague 2 P1-01)
- `membership_id` FK `tenant_memberships.id` (lié à TenantMembership pas Account direct → multi-tenant a factors différents par tenant)
- 3 types : `'TOTP' | 'FIDO' | 'PIN'` avec XOR CHECK constraint
- TOTP : `encrypted_secret BYTEA + encrypted_secret_key_version` (KMS envelope)
- FIDO : `credential_id`, `public_key`, `aaguid`, `transports`
- PIN : `pin_hash` Argon2id + `pin_attempts` + `pin_locked_until` (lockout 5min après 3 échecs — F367)

## Solution

```python
# alembic/versions/c4d5e6f7a8bd_create_auth_factors.py
"""Bloc 2 Q6=B : table auth_factors unifiée.

Revision ID: c4d5e6f7a8bd
Revises: c4d5e6f7a8bc
"""
def upgrade() -> None:
    # Cf. 50-sql-schema.md §2.1 pour DDL complet
    op.create_table("auth_factors", ...)
    op.create_index("idx_auth_factors_membership_active", "auth_factors",
                    ["membership_id", "type"], postgresql_where="is_active = true")
    op.create_index("uq_auth_factors_credential_id", "auth_factors", ["credential_id"],
                    unique=True, postgresql_where="credential_id IS NOT NULL")
```

## DoD

- [ ] Migration appliquée
- [ ] CI invariant `check_xor_constraint.py` (NEW) vérifie XOR sur 3 types

---

# Story B2.S5.T2 — Migration data legacy → `auth_factors`

## Contexte

**Sévérité** : P0 — sans migration, les MFA enrôlées actuellement sont perdues à la suppression des tables legacy

### Description

3 sources legacy :
- `mfa_devices` (TOTP enroll) → `auth_factors(type='TOTP')`
- `webauthn_credentials` (FIDO2) → `auth_factors(type='FIDO')`
- `accounts.pin_hash` + `trusted_devices` → `auth_factors(type='PIN')`

## Solution

Migration data step-by-step (4-step backward-compat pattern) :

```python
# alembic/versions/c4d5e6f7a8be_migrate_mfa_data_to_auth_factors.py
"""Migration data : MFADevice/WebAuthnCredential/TrustedDevice → auth_factors.

Revision ID: c4d5e6f7a8be
"""
def upgrade() -> None:
    # 1. Migrate TOTP : mfa_devices → auth_factors(type='TOTP')
    # NOTE : encrypted_secret est déjà chiffré via legacy KMS — réencrypter
    # avec nouveau KMS context = {tenant_id, entity='auth_factor_totp', record_id}
    op.execute("""
        INSERT INTO auth_factors (
            membership_id, type, label,
            encrypted_secret, encrypted_secret_key_version,
            last_used_at, is_active, created_at, updated_at
        )
        SELECT
            tm.id AS membership_id,
            'TOTP' AS type,
            COALESCE(md.label, 'Migrated TOTP') AS label,
            md.encrypted_secret,
            md.key_version,
            md.last_used_at,
            md.is_active,
            md.created_at,
            md.updated_at
        FROM mfa_devices md
        INNER JOIN tenant_memberships tm
            ON tm.account_id = md.account_id
            AND tm.tenant_id = md.tenant_id
        WHERE md.deleted_at IS NULL;
    """)

    # 2. Migrate FIDO : webauthn_credentials → auth_factors(type='FIDO')
    op.execute("""
        INSERT INTO auth_factors (
            membership_id, type, label,
            credential_id, public_key, sign_count, aaguid, transports,
            last_used_at, is_active, created_at, updated_at
        )
        SELECT
            tm.id AS membership_id,
            'FIDO' AS type,
            COALESCE(wc.label, 'Migrated FIDO key') AS label,
            wc.credential_id,
            wc.public_key,
            wc.sign_count,
            wc.aaguid,
            wc.transports,
            wc.last_used_at,
            wc.is_active,
            wc.created_at,
            wc.updated_at
        FROM webauthn_credentials wc
        INNER JOIN tenant_memberships tm
            ON tm.account_id = wc.account_id;
    """)

    # 3. Migrate PIN : accounts.pin_hash + trusted_devices → auth_factors(type='PIN')
    op.execute("""
        INSERT INTO auth_factors (
            membership_id, type, label,
            pin_hash, pin_attempts, pin_locked_until,
            last_used_at, is_active, created_at, updated_at
        )
        SELECT DISTINCT
            tm.id AS membership_id,
            'PIN' AS type,
            'Migrated PIN' AS label,
            a.pin_hash,
            0 AS pin_attempts,
            NULL AS pin_locked_until,
            NULL AS last_used_at,
            true AS is_active,
            a.created_at,
            NOW() AS updated_at
        FROM accounts a
        INNER JOIN tenant_memberships tm ON tm.account_id = a.id
        WHERE a.pin_hash IS NOT NULL;
    """)

    # 4. Validation : count avant/après
    # (à vérifier manuellement en pré-prod : SELECT count par type)


def downgrade() -> None:
    # Restaurer depuis auth_factors → tables legacy (best-effort)
    # NOTE : downgrade lossy — TOTP secret réchiffré non récupérable côté legacy
    raise NotImplementedError(
        "Downgrade not supported — keep auth_factors unified. "
        "Use Point-In-Time Recovery DB if rollback needed."
    )
```

## DoD

- [ ] Migration data testée sur staging avec snapshot prod (count avant/après match)
- [ ] Test E2E : user avec TOTP enrôlé pré-migration peut toujours se connecter post-migration
- [ ] R14 (effort migration auth_factor sous-estimé) marqué résolu

## Risque

- Probabilité 4, impact 5 → score 20 CRITICAL (cf. R14 dans risk register)
- Mitigation : déploiement progressif staging 14j avant prod, smoke tests E2E sur tous types MFA

---

# Story B2.S5.T3 — Service `AuthFactorService` + drop legacy

## Contexte

**Sévérité** : P1 — refacto code post-migration data

### Description

Une fois T2 migré, on :
1. Crée `AuthFactorService` avec API unifiée
2. Migre les call-sites (MFAService, WebAuthnService, PINService → AuthFactorService)
3. Drop tables legacy (`mfa_devices`, `webauthn_credentials`, `trusted_devices`) et colonne `accounts.pin_hash`

## Solution

```python
# app/services/auth_factor.py (NEW)
class AuthFactorService:
    async def list_factors(self, db, membership_id: int) -> list[AuthFactor]:
        """Tous les factors actifs d'un membership."""
        result = await db.execute(
            select(AuthFactor).filter_by(membership_id=membership_id, is_active=True)
        )
        return list(result.scalars())

    async def enroll_totp(self, db, membership_id: int, label: str, secret: str) -> AuthFactor:
        """Enrôle un TOTP factor avec chiffrement KMS."""
        factor = AuthFactor(
            membership_id=membership_id,
            type="TOTP",
            label=label,
            encrypted_secret=...,  # via EncryptedField
            is_active=True,
        )
        db.add(factor)
        await db.flush()
        return factor

    async def enroll_fido(self, db, membership_id, label, credential_id, public_key, ...):
        ...

    async def verify_totp(self, db, membership_id: int, code: str) -> bool:
        """Vérifie code TOTP contre tous les factors TOTP actifs du membership."""
        factors = await db.execute(
            select(AuthFactor).filter_by(
                membership_id=membership_id, type="TOTP", is_active=True
            )
        )
        for factor in factors.scalars():
            secret = factor.encrypted_secret  # Déchiffré transparent via EncryptedField
            if pyotp.TOTP(secret).verify(code, valid_window=1):
                factor.last_used_at = datetime.now(UTC)
                return True
        return False
```

## DoD

- [ ] `AuthFactorService` opérationnel
- [ ] `MFAService`, `WebAuthnService` (existants) appellent `AuthFactorService` (façade)
- [ ] Tables legacy droppées (migration `c4d5e6f7a8bf_drop_legacy_mfa_tables.py`)
- [ ] `accounts.pin_hash` colonne droppée

## Risque

- Probabilité 2, impact 4 → score 8 MEDIUM

---

# Story B2.S5.T4 — F296 consolidation `verify_credentials`

## Contexte

**Friction** : F296 (vague 5 V5-P0-03)
**Sévérité** : P1 — Sprint 1 T9 a posé un patch tactique. Cette story consolide le pattern timing-safe partout.

### Description

Sprint 1 T9 a corrigé `account.py:70`. Cette story applique le même pattern à tous les call-sites :
- `auth_v2.py:278, 285` (`change_password` actuel + new password verify)
- `password_reset.py` (verify token reset)
- API key validation legacy

## Solution

Factoriser dans `app/services/security_helpers.py` :

```python
# app/services/security_helpers.py
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22 + "$" + "B" * 43


def verify_password_safe(password: str, hash_value: Optional[str]) -> bool:
    """F296 fix : timing-safe — toujours appeler verify_password.

    Si hash_value=None (OAuth-only), retourne False mais avec même durée
    qu'un verify normal (anti user-enum).
    """
    target_hash = hash_value if hash_value else _DUMMY_HASH
    is_valid = verify_password(password, target_hash)
    return is_valid and hash_value is not None  # OAuth-only = always False
```

## DoD

- [ ] `verify_password_safe()` utilisé partout (~6 call-sites)
- [ ] CI invariant `check_no_unsafe_verify_password.py` (NEW) — refuse `verify_password(pwd, account.hashed_password)` direct (force le helper)

---

# Story B2.S5.T5 — Recovery codes 96 bits + chiffrement KMS

## Contexte

**Friction** : V4-P2-02 (vague 4) + F388 (Sprint B2.S1.T6 préparation)
**Sévérité** : P2 — entropie 32 bits insuffisante (NIST SP 800-63B exige 64 bits min)

### Description

B2.S1.T6 a créé le modèle `BackupCode` avec `EncryptedField` (chiffrement KMS). Cette story livre la génération + verify finalisés.

## Solution

```python
# app/services/backup_codes.py
import secrets
import hashlib
from sqlalchemy import select


class BackupCodeService:
    CODE_BITS = 96  # NIST SP 800-63B compliant

    def generate_codes(self, count: int = 10) -> list[str]:
        """Génère N codes recovery 96 bits base32.

        Format : XXXX-XXXX-XXXX-XXXX-XXX (16 chars + 3 dashes pour lisibilité)
        """
        return [self._format(secrets.token_urlsafe(12)) for _ in range(count)]

    def _format(self, code: str) -> str:
        """Format human-readable : XXXX-XXXX-XXXX-XXXX."""
        clean = code.replace("-", "").replace("_", "").upper()[:16]
        return "-".join([clean[i:i+4] for i in range(0, 16, 4)])

    async def enroll(self, db, membership_id: int) -> list[str]:
        """Génère et stocke N codes pour un membership.

        Retourne les codes en plain text UNE SEULE FOIS (à sauvegarder par user).
        Stockage : hash SHA-256 chiffré KMS.
        """
        codes = self.generate_codes()
        for code in codes:
            code_hash = hashlib.sha256(code.encode()).hexdigest()
            db.add(BackupCode(
                membership_id=membership_id,
                code_hash_encrypted=code_hash,  # via EncryptedField
                used_at=None,
            ))
        await db.flush()
        return codes

    async def verify(self, db, membership_id: int, code: str) -> bool:
        """Vérifie + invalide single-use."""
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        result = await db.execute(
            select(BackupCode).filter_by(
                membership_id=membership_id, code_hash_encrypted=code_hash, used_at=None
            ).with_for_update()
        )
        backup = result.scalar_one_or_none()
        if not backup:
            return False
        backup.used_at = datetime.now(UTC)
        await db.flush()
        return True
```

## DoD

- [ ] `BackupCodeService.generate_codes()` utilise 96 bits (NIST compliant)
- [ ] `verify()` single-use + atomique avec `with_for_update`
- [ ] Test : 10 codes générés tous uniques, hash AAD KMS context tenant
- [ ] Endpoint `POST /auth/mfa/backup-codes/regenerate` (admin only)

---

# Story B2.S5.T6 — Migration `Account.address` → `Customer` (Q7=A)

## Contexte

**Décision** : **Q7=A** (verrouillée 2026-04-27) — Account ne porte plus que `email + names + auth`. `address`/`postal_code`/`city`/`country` migrent vers `Customer` (tenant-scopée). RGPD : purge cascade par tenant naturelle.
**Sévérité** : **P0** — sans cette migration, `Account.address` reste cross-tenant non scopé, RGPD purge complexe (tenant offboard ne supprime pas address de comptes multi-tenant)
**Code source** : `app/models/account.py`, `app/models/customer.py`

### Description

État actuel :
- `Account` porte `address: str | None`, `postal_code`, `city`, `country` — données tenant-scopées sur entité cross-tenant
- Pour un user `TenantMembership` sur 2 tenants (Marveline + Splendid post Q43=B) : 1 seule address chez Account → laquelle utiliser pour facturation ?

Cible Q7=A :
1. **Migration data** : pour chaque `Account` ayant address, créer/update `Customer(account_id=..., tenant_id=...)` avec address
2. **Drop colonnes** sur `Account.address`, `Account.postal_code`, `Account.city`, `Account.country`
3. **API** : pour récupérer l'adresse user dans un tenant donné → `Customer.where(account_id=..., tenant_id=...).address`

## Solution

### Migration backward-compatible 4 étapes

```python
# alembic/versions/c4d5e6f7a8c0_account_address_to_customer_step1_add_customer_columns.py
"""Étape 1 : s'assurer que Customer a les colonnes (déjà cas ; check)."""
def upgrade() -> None:
    # Customer.address_line1, postal_code, city, country existent déjà (B4.S5)
    pass


# alembic/versions/c4d5e6f7a8c1_account_address_to_customer_step2_backfill.py
"""Étape 2 : backfill — pour chaque Account.address non null, copier dans Customer du tenant approprié."""
def upgrade() -> None:
    op.execute(text("""
        -- Pour chaque Account avec address ET TenantMembership unique → créer/update Customer
        WITH account_with_address AS (
            SELECT a.id AS account_id, a.address, a.postal_code, a.city, a.country, tm.tenant_id
            FROM accounts a
            JOIN tenant_memberships tm ON tm.account_id = a.id
            WHERE a.address IS NOT NULL OR a.postal_code IS NOT NULL
        )
        INSERT INTO customers (
            tenant_id, account_id, first_name, last_name, email,
            address_line1, postal_code, city, country, requires_deposit, created_at
        )
        SELECT
            awa.tenant_id, awa.account_id,
            a.first_name, a.last_name, a.email,
            awa.address, awa.postal_code, awa.city, awa.country,
            true, NOW()
        FROM account_with_address awa
        JOIN accounts a ON a.id = awa.account_id
        ON CONFLICT (tenant_id, account_id) DO UPDATE
        SET address_line1 = EXCLUDED.address_line1,
            postal_code = EXCLUDED.postal_code,
            city = EXCLUDED.city,
            country = EXCLUDED.country
        WHERE customers.address_line1 IS NULL  -- ne pas overwrite address customer existante
    """))


# alembic/versions/c4d5e6f7a8c2_account_address_to_customer_step3_drop_columns.py
"""Étape 3 : drop colonnes Account après vérification 0 perte data."""
def upgrade() -> None:
    # Audit pre-drop : 0 Account avec address sans Customer correspondant
    orphans = op.get_bind().scalar(text("""
        SELECT COUNT(*) FROM accounts a
        WHERE (a.address IS NOT NULL OR a.postal_code IS NOT NULL)
          AND NOT EXISTS (
              SELECT 1 FROM customers c
              JOIN tenant_memberships tm ON tm.account_id = a.id
              WHERE c.account_id = a.id AND c.tenant_id = tm.tenant_id
                AND c.address_line1 IS NOT NULL
          )
    """))
    if orphans > 0:
        raise Exception(f"{orphans} accounts with address but no Customer.address — fix backfill first")

    op.drop_column("accounts", "address")
    op.drop_column("accounts", "postal_code")
    op.drop_column("accounts", "city")
    op.drop_column("accounts", "country")
```

### Modèle Account refacto

```python
# app/models/account.py — avant
class Account(Base):
    email: Mapped[str]
    first_name: Mapped[str]
    last_name: Mapped[str]
    address: Mapped[str | None]  # ❌ DROP (Q7=A)
    postal_code: Mapped[str | None]  # ❌ DROP
    city: Mapped[str | None]  # ❌ DROP
    country: Mapped[str | None]  # ❌ DROP

# après — Account ne porte que auth + identité minimale
class Account(Base):
    email: Mapped[str]
    first_name: Mapped[str]
    last_name: Mapped[str]
    hashed_password: Mapped[str | None]
    # address tenant-scopée → Customer.address_line1
```

### API endpoints adapt

```python
# Avant (legacy) : endpoint /me retournait address depuis Account
@router.get("/me")
async def get_me(user: Account = Depends(...)):
    return MeRead(email=user.email, address=user.address, ...)

# Après Q7=A : address depuis Customer du tenant courant
@router.get("/me")
async def get_me(
    user: Account = Depends(...),
    tenant_id: int = Depends(get_tenant_id),
):
    customer = await db.scalar(
        select(Customer).where(
            Customer.account_id == user.id,
            Customer.tenant_id == tenant_id,
        )
    )
    return MeRead(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        address=customer.address_line1 if customer else None,
        postal_code=customer.postal_code if customer else None,
        city=customer.city if customer else None,
        country=customer.country if customer else None,
    )
```

### Tests

```python
async def test_account_no_more_address_attribute(db, account_post_migration):
    with pytest.raises(AttributeError):
        _ = account_post_migration.address  # colonne droppée

async def test_user_two_tenants_two_addresses(db, account, tenant_marveline, tenant_splendid):
    """Q7=A — user multi-tenant peut avoir address différente per tenant."""
    db.add(Customer(account_id=account.id, tenant_id=tenant_marveline.id, address_line1="Paris", ...))
    db.add(Customer(account_id=account.id, tenant_id=tenant_splendid.id, address_line1="Lyon", ...))
    await db.commit()

    addr_m = await get_user_address(account.id, tenant_marveline.id)
    addr_s = await get_user_address(account.id, tenant_splendid.id)
    assert addr_m == "Paris"
    assert addr_s == "Lyon"

async def test_rgpd_tenant_purge_naturel(db, account, tenant_marveline):
    """RGPD : purge tenant Marveline → Customer purgé → address purgée. Account intact (multi-tenant)."""
    customer = Customer(account_id=account.id, tenant_id=tenant_marveline.id, address_line1="Paris", ...)
    db.add(customer); await db.commit()

    # Tenant offboarding : DELETE WHERE tenant_id=marveline cascade
    await db.execute(delete(Customer).where(Customer.tenant_id == tenant_marveline.id))
    await db.commit()

    # Account toujours présent, mais sans address Marveline
    await db.refresh(account)
    assert account is not None
    customer_check = await db.scalar(
        select(Customer).where(Customer.account_id == account.id, Customer.tenant_id == tenant_marveline.id)
    )
    assert customer_check is None
```

## DoD

- [ ] **Q7=A livré** : 4 colonnes droppées de `Account` (address, postal_code, city, country)
- [ ] Migration backfill : 0 perte data (audit count Customer = count Account-with-address per tenant)
- [ ] Endpoint `/me` retourne address depuis Customer du tenant courant
- [ ] Test : `account.address` → AttributeError
- [ ] Test : user multi-tenant → 2 addresses distinctes per tenant
- [ ] Test RGPD : purge tenant → Customer.address purgée mais Account intact

---

## Critères de succès Sprint B2.S5

- [ ] Table `auth_factors` opérationnelle, 3 types XOR
- [ ] Migration data 100% : count MFADevice = count auth_factors(TOTP), idem FIDO/PIN
- [ ] Tables legacy droppées
- [ ] `AuthFactorService` API unifiée
- [ ] F296 timing-safe partout (`verify_password_safe()`)
- [ ] Recovery codes 96 bits chiffrés KMS
- [ ] **Q7=A** Account.address → Customer migré (RGPD purge tenant-naturelle)

## Bloc 2 — bilan

À l'issue de B2.S5, **Bloc 2 Identity livré** :
- Provisioning atomique avec verticals
- RBAC v3 effectif (DB lue, fallback uniquement en mode dégradé)
- MFA enforcement réel (politique per-role)
- OAuth flows unifiés avec MFA gate
- Sessions cascade revoke + Redis batch flush
- WebAuthn multi-tenant (RP_ID per-tenant)
- auth_factors unifié + recovery codes NIST compliant

**~30 frictions sécurité auth résolues** (Bloc 2 = densité max audit Phase 1).

**Suite** : Bloc 3 Money (B3.S1 → B3.S7 incl. nouveau B3.S7).

---

**Fin du document — 12-sprint-B2.S5.md**
