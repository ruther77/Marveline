# 50 — SQL Schema cible (PostgreSQL 16)

> **Source unique de vérité DDL** pour le refactor. Toutes les nouvelles tables + modifications schema existant + triggers + views + indexes.
> **Convention** : DDL prêt à exécuter manuellement (debug staging) **ou** à transposer en migration Alembic (cf. `51-alembic-migrations.md`).

## Sommaire

| # | Section | Bloc | Sprint |
|---|---|---|---|
| 0 | Helpers DDL globaux (`fn_set_updated_at`) | 1 | B1.S1 |
| 1 | Tables transverses (verticals, outbox_events) | 1 | B1.S2, B7.S1 |
| 2 | Identity & Auth (auth_factors, auth_vertical_scopes, access_reviews) | 2 | B2.S2-S5, Sprint 1 T4 |
| 3 | Tenants augmentés (vertical, brand_*, peppol) | 1, 7 | B7.S1 |
| 4 | Customer augmenté (deposit_policy, country, preferred_language) | 3, 4 | B3.S4, B4.S4 |
| 5 | Catalogue restructuré (Category FK, drop brand_code, tva_rate) | 4, 7 | B4.S3, B7.S2 |
| 6 | Stock — view matérialisée + drop colonnes denormalized | 4 | B4.S2 |
| 7 | Ledger entries unifié (LedgerEntryMixin) | 3 | B3.S2 |
| 8 | Invoice immutability + e-invoicing prep | 3 | B3.S2, B3.S6 |
| 9 | Pricing rules (Numeric discount_pct, enum DB) | 3, 4 | B3.S3, B4.S4 |
| 10 | Audit refondu (HMAC chaîné, prev_hmac, PII encrypted) | 6 | B6.S2 |
| 11 | Notification log + Postmark tracking | 6 | B6.S1 |
| 12 | Feature flag history + M:N tenants | 6 | B6.S3 |
| 13 | Catalogue ETL per-tenant (split) + price history | 5 | B5.S2, B5.S6 |
| 14 | Triggers FSM + ledger immutability | 3, 5, 6 | B3.S2, B5.S3, B6.S2 |
| 15 | RLS policies (Q2=A) | 1 | B1.S2 |

---

## Conventions DDL

- **Naming** : cf. `02-conventions.md` §1.1 (snake_case pluriel, FK `<table>_id`).
- **Index nommage** : `idx_<table>_<columns>` ou `uq_<table>_<columns>` pour UNIQUE.
- **CHECK constraint nommage** : `ck_<table>_<rule>`.
- **FK nommage** : `fk_<table>_<column>` (généré auto SQLAlchemy en général).
- **Trigger nommage** : `trg_<table>_<event>_<action>`.
- **Tous les `created_at`/`updated_at`** : `TIMESTAMPTZ DEFAULT now() NOT NULL` (jamais `TIMESTAMP WITHOUT TIME ZONE`).
- **PII chiffré** : type `BYTEA` pour le ciphertext + commentaire `EncryptedField KMS context=<key>`.
- **Cents** : `BIGINT` (jamais `INTEGER` pour éviter overflow).
- **Soft delete** : convention `is_active BOOLEAN NOT NULL DEFAULT true` + `deleted_at TIMESTAMPTZ NULL` + `deleted_by_id BIGINT NULL`.

---

## §0 — Helpers DDL (functions PL/pgSQL globales)

> **Référencées** par triggers `BEFORE UPDATE` sur tables avec `updated_at`. À créer **avant** toute table qui en dépend (migration Sprint 1 `c1d2e3f4a5b5_create_pgsql_helpers.py`).

```sql
-- Trigger function : auto-update colonne updated_at à toute UPDATE
CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION fn_set_updated_at() IS 'Trigger BEFORE UPDATE — refresh updated_at = now(). Convention CaroCorp.';
```

> **Usage** : `CREATE TRIGGER trg_<table>_updated_at BEFORE UPDATE ON <table> FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();`

---

## §1 — Tables transverses

### 1.1 `verticals` (Bloc 7 §2.2 — renommée depuis `apps`)

```sql
CREATE TABLE verticals (
    code VARCHAR(50) PRIMARY KEY,
    -- Convention: lower_snake (ex: 'location', 'epicerie', 'restaurant', 'autour_de_table')
    
    label VARCHAR(100) NOT NULL,
    -- Affichable UI : "Location événementiel", "Épicerie alimentaire", etc.
    
    jwt_audience_pattern VARCHAR(100) NOT NULL,
    -- Format JWT audience : ex 'location-{tenant_id}', 'epicerie-{tenant_id}'
    
    degraded_redis_key_prefix VARCHAR(100) NOT NULL,
    -- Préfixe Redis key pour mode dégradé per-vertical
    
    react_module_name VARCHAR(100) NOT NULL,
    -- Frontend module à charger : 'location', 'epicerie', 'restaurant', etc.
    
    enabled BOOLEAN NOT NULL DEFAULT true,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT ck_verticals_code_format
        CHECK (code ~ '^[a-z][a-z0-9_]+$')
);

CREATE INDEX idx_verticals_enabled ON verticals(enabled) WHERE enabled = true;

COMMENT ON TABLE verticals IS 'Modèles métier extensibles. Bloc 7 §2.2.';
COMMENT ON COLUMN verticals.code IS 'Identifiant vertical (location, epicerie, restaurant, autour_de_table, …)';

-- Seed initial
INSERT INTO verticals (code, label, jwt_audience_pattern, degraded_redis_key_prefix, react_module_name) VALUES
    ('location',         'Location événementiel',   'location-{tenant_id}',   'degraded:location:',   'location'),
    ('epicerie',         'Épicerie alimentaire',    'epicerie-{tenant_id}',   'degraded:epicerie:',   'epicerie'),
    ('restaurant',       'Restaurant',              'restaurant-{tenant_id}', 'degraded:restaurant:', 'restaurant'),
    ('autour_de_table',  'Autour de Table',         'atdt-{tenant_id}',       'degraded:atdt:',       'autour_de_table');
```

### 1.2 `outbox_events` (Bloc 1 Q4=A — Outbox pattern transactionnel)

> **Note nommage (Vague 2 cohérence)** : table renommée `outbox` → `outbox_events` pour respecter convention CaroCorp pluriel sur les tables d'**enregistrements répétés indépendants** (`audit_logs`, `auth_factors`, `verticals`, `access_reviews`). Les tables de **registre temporel agrégé** restent au singulier suffixé (`points_ledger`, `revenue_ledger`, `payment_ledger`, `notification_log`, `feature_flag_history`). Modèle ORM : `class OutboxEvent(Base): __tablename__ = "outbox_events"`. Cohérent avec les 31 références sprints qui utilisent déjà `outbox_events` / `OutboxEvent`.

```sql
CREATE TABLE outbox_events (
    id BIGSERIAL PRIMARY KEY,
    
    aggregate_type VARCHAR(100) NOT NULL,
    -- Ex: 'Reservation', 'Customer', 'Invoice', 'AuditLog', 'EmailNotification'
    
    aggregate_id BIGINT,
    -- ID de l'entité métier qui déclenche l'event (NULL si event global)
    
    event_type VARCHAR(100) NOT NULL,
    -- Ex: 'ReservationCreated', 'CustomerUpdated', 'AuditMutation', 'EmailQueued'
    
    payload JSONB NOT NULL,
    -- Contenu sérialisé de l'event (idempotent, versionné via payload.version)
    
    tenant_id BIGINT,
    -- NULL pour events globaux (provisioning, migrations DEVUP-level)
    
    actor_account_id BIGINT,
    actor_api_key_id BIGINT,
    actor_type VARCHAR(20) NOT NULL DEFAULT 'system',
    -- 'account' | 'api_key' | 'system'
    
    request_id VARCHAR(100),
    -- Corrélation logs Loki + traces OTel (Bloc 6 §6.2.18)
    
    trace_id VARCHAR(64),
    -- OpenTelemetry trace_id (hex 32 chars)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Dispatch worker fields
    dispatched_at TIMESTAMPTZ,
    dispatch_attempts INTEGER NOT NULL DEFAULT 0,
    last_dispatch_error TEXT,
    
    CONSTRAINT ck_outbox_events_actor_type CHECK (actor_type IN ('account', 'api_key', 'system'))
);

-- Index pour worker dispatcher (lit les non-dispatched ordonnés)
CREATE INDEX idx_outbox_events_pending ON outbox_events (created_at)
    WHERE dispatched_at IS NULL;

-- Index pour debugging / replay par aggregate
CREATE INDEX idx_outbox_events_aggregate ON outbox_events (aggregate_type, aggregate_id, created_at DESC);

-- Index pour retry policy
CREATE INDEX idx_outbox_events_retry ON outbox_events (last_dispatch_error, dispatch_attempts)
    WHERE dispatched_at IS NULL AND dispatch_attempts > 0;

COMMENT ON TABLE outbox_events IS 'Outbox pattern transactionnel — Bloc 1 Q4=A. Worker async dispatche vers audit_log + RabbitMQ events.';
```

**Worker dispatcher** (référence — implémentation `app/tasks/outbox.py`) :
```python
@celery_app.task(name='app.tasks.outbox.dispatch_outbox', bind=True, queue='outbox')
async def dispatch_outbox_task(self):
    # SELECT FOR UPDATE SKIP LOCKED + dispatch chaque event vers audit_log/RabbitMQ
    # UPDATE outbox_events SET dispatched_at = now() WHERE id IN (...)
```

---

## §2 — Identity & Auth

### 2.1 `auth_factors` (Bloc 2 Q6=B)

Remplace `mfa_devices`, `webauthn_credentials`, `trusted_devices`, `accounts.pin_hash`.

```sql
CREATE TABLE auth_factors (
    id BIGSERIAL PRIMARY KEY,
    
    membership_id BIGINT NOT NULL REFERENCES tenant_memberships(id) ON DELETE CASCADE,
    -- Lié à TenantMembership (pas Account direct) — un user multi-tenant a des facteurs différents par tenant
    
    type VARCHAR(20) NOT NULL,
    -- 'TOTP' | 'FIDO' | 'PIN'
    
    label VARCHAR(100) NOT NULL,
    -- "iPhone Pro", "YubiKey 5", "PIN principal"
    
    -- TOTP fields
    encrypted_secret BYTEA,
    -- Envelope encryption KMS context='auth_factors_totp'
    -- Comment: EncryptedField KMS context=auth_factors_totp
    
    encrypted_secret_key_version INTEGER,
    -- Version de la KEK utilisée pour encrypted_secret (rotation)
    
    -- WebAuthn (FIDO) fields
    credential_id BYTEA,
    -- WebAuthn credential ID raw bytes
    
    public_key BYTEA,
    -- COSE_Key public key
    
    sign_count BIGINT NOT NULL DEFAULT 0,
    
    aaguid UUID,
    -- Authenticator Attestation GUID
    
    transports VARCHAR(100),
    -- CSV: 'usb,nfc,ble' | 'internal' | etc.
    
    -- PIN fields
    pin_hash VARCHAR(255),
    -- Argon2id hash (cf. Bloc 1 §1.2.1 password/hashing.py)
    
    pin_attempts INTEGER NOT NULL DEFAULT 0,
    pin_locked_until TIMESTAMPTZ,
    -- Lockout après 3 échecs (5 min) — F367 fix
    
    -- Common
    last_used_at TIMESTAMPTZ,
    last_ip VARCHAR(45),
    -- IPv4 ou IPv6
    
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- XOR : exactement 1 type populated
    CONSTRAINT ck_auth_factors_type CHECK (type IN ('TOTP', 'FIDO', 'PIN')),
    CONSTRAINT ck_auth_factors_xor CHECK (
        (type = 'TOTP' AND encrypted_secret IS NOT NULL AND credential_id IS NULL AND pin_hash IS NULL) OR
        (type = 'FIDO' AND credential_id IS NOT NULL AND encrypted_secret IS NULL AND pin_hash IS NULL) OR
        (type = 'PIN' AND pin_hash IS NOT NULL AND encrypted_secret IS NULL AND credential_id IS NULL)
    )
);

-- Index lookup par membership pour login flow
CREATE INDEX idx_auth_factors_membership_active ON auth_factors (membership_id, type)
    WHERE is_active = true;

-- WebAuthn lookup par credential_id
CREATE UNIQUE INDEX uq_auth_factors_credential_id ON auth_factors (credential_id)
    WHERE credential_id IS NOT NULL;

COMMENT ON TABLE auth_factors IS 'Facteur d''authentification unifié — Bloc 2 Q6=B. Remplace MFADevice, WebAuthnCredential, TrustedDevice (PIN).';
```

### 2.2 `auth_vertical_scopes` (Bloc 2 §2.3 — renommée depuis `auth_app_scopes`)

```sql
CREATE TABLE auth_vertical_scopes (
    vertical_code VARCHAR(50) NOT NULL REFERENCES verticals(code) ON DELETE CASCADE,
    scope_name VARCHAR(100) NOT NULL,
    -- Format: 'domain:action' (ex: 'reservations:write', 'commandes:pay')
    
    PRIMARY KEY (vertical_code, scope_name)
);

CREATE INDEX idx_auth_vertical_scopes_scope ON auth_vertical_scopes (scope_name);

COMMENT ON TABLE auth_vertical_scopes IS 'Restreint quels scopes RBAC sont attribuables à un vertical. Filtré à émission JWT (TokenService.issue_tokens). Bloc 2 §2.3.';

-- Seed exhaustif (cohérent avec catalogue Scopes v3 — cf. architecture-cible.md §2.3)
INSERT INTO auth_vertical_scopes (vertical_code, scope_name) VALUES
    -- Identity (cross-vertical)
    ('location', 'accounts:read'), ('epicerie', 'accounts:read'), ('restaurant', 'accounts:read'), ('autour_de_table', 'accounts:read'),
    ('location', 'sessions:read'), ('epicerie', 'sessions:read'), ('restaurant', 'sessions:read'), ('autour_de_table', 'sessions:read'),
    ('location', 'mfa:manage'), ('epicerie', 'mfa:manage'), ('restaurant', 'mfa:manage'), ('autour_de_table', 'mfa:manage'),
    
    -- Customer (cross-vertical)
    ('location', 'customers:read'), ('epicerie', 'customers:read'), ('restaurant', 'customers:read'), ('autour_de_table', 'customers:read'),
    ('location', 'customers:read_pii'), ('epicerie', 'customers:read_pii'), ('restaurant', 'customers:read_pii'), ('autour_de_table', 'customers:read_pii'),
    ('location', 'customers:write'), ('epicerie', 'customers:write'), ('restaurant', 'customers:write'), ('autour_de_table', 'customers:write'),
    
    -- Catalogue (cross-vertical sauf 'commandes' restaurant only)
    ('location', 'products:read'), ('epicerie', 'products:read'), ('restaurant', 'products:read'), ('autour_de_table', 'products:read'),
    ('location', 'products:write'), ('epicerie', 'products:write'), ('restaurant', 'products:write'), ('autour_de_table', 'products:write'),
    ('location', 'pricing:read'), ('epicerie', 'pricing:read'), ('restaurant', 'pricing:read'), ('autour_de_table', 'pricing:read'),
    ('location', 'pricing:write'), ('epicerie', 'pricing:write'), ('restaurant', 'pricing:write'), ('autour_de_table', 'pricing:write'),
    
    -- Stock (cross-vertical)
    ('location', 'stock:read'), ('epicerie', 'stock:read'), ('restaurant', 'stock:read'), ('autour_de_table', 'stock:read'),
    ('location', 'stock:write'), ('epicerie', 'stock:write'), ('restaurant', 'stock:write'), ('autour_de_table', 'stock:write'),
    ('epicerie', 'stock:transfer'), ('restaurant', 'stock:transfer'),
    
    -- Reservations / Devis (location ONLY)
    ('location', 'reservations:read'), ('location', 'reservations:write'), ('location', 'reservations:cancel'),
    ('location', 'devis:read'), ('location', 'devis:write'), ('location', 'devis:convert'),
    
    -- Invoice / Payment (cross-vertical)
    ('location', 'invoices:read'), ('epicerie', 'invoices:read'), ('restaurant', 'invoices:read'), ('autour_de_table', 'invoices:read'),
    ('location', 'invoices:write'), ('epicerie', 'invoices:write'), ('restaurant', 'invoices:write'), ('autour_de_table', 'invoices:write'),
    ('location', 'invoices:emit'), ('epicerie', 'invoices:emit'), ('restaurant', 'invoices:emit'), ('autour_de_table', 'invoices:emit'),
    ('location', 'payments:record'), ('epicerie', 'payments:record'), ('restaurant', 'payments:record'),
    ('location', 'relances:read'), ('location', 'relances:trigger'),
    
    -- Vente directe (epicerie ONLY)
    ('epicerie', 'ventes:read'), ('epicerie', 'ventes:write'), ('epicerie', 'ventes:refund'),
    
    -- Restaurant ONLY
    ('restaurant', 'commandes:read'), ('restaurant', 'commandes:write'), ('restaurant', 'commandes:pay'),
    ('restaurant', 'instances:launch'),
    
    -- Loyalty (cross-vertical applicable, choix tenant)
    ('location', 'loyalty:read'), ('epicerie', 'loyalty:read'), ('restaurant', 'loyalty:read'),
    ('location', 'loyalty:adjust'), ('epicerie', 'loyalty:adjust'), ('restaurant', 'loyalty:adjust'),
    
    -- Supplier (cross-vertical)
    ('location', 'suppliers:read'), ('epicerie', 'suppliers:read'), ('restaurant', 'suppliers:read'), ('autour_de_table', 'suppliers:read'),
    ('location', 'suppliers:write'), ('epicerie', 'suppliers:write'), ('restaurant', 'suppliers:write'), ('autour_de_table', 'suppliers:write'),
    ('epicerie', 'supplier_orders:receive'), ('restaurant', 'supplier_orders:receive'),
    
    -- Cross-cutting (cross-vertical)
    ('location', 'audit:read'), ('epicerie', 'audit:read'), ('restaurant', 'audit:read'), ('autour_de_table', 'audit:read'),
    ('location', 'audit:read_pii'), ('epicerie', 'audit:read_pii'), ('restaurant', 'audit:read_pii'), ('autour_de_table', 'audit:read_pii'),
    ('location', 'features:read'), ('epicerie', 'features:read'), ('restaurant', 'features:read'),
    ('epicerie', 'printer:print'), ('restaurant', 'printer:print'),
    
    -- VPN (cross-vertical, infra-level)
    ('location', 'vpn:read'), ('epicerie', 'vpn:read'), ('restaurant', 'vpn:read'),
    
    -- Évenements (location ONLY)
    ('location', 'evenements:read'), ('location', 'evenements:write'),
    
    -- Admin DEVUP (superadmin uniquement, mais scope par vertical pour restriction si besoin)
    ('location', 'admin:read'), ('epicerie', 'admin:read'), ('restaurant', 'admin:read'), ('autour_de_table', 'admin:read');
```

### 2.3 `access_reviews` (déjà détaillé Sprint 1 T4)

Cf. `10-sprint-1-PROD-FIRE-DRILL.md` §S1.T4. Schema rappel :

```sql
CREATE TABLE access_reviews (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    membership_id BIGINT REFERENCES tenant_memberships(id) ON DELETE SET NULL,
    review_type VARCHAR(30) NOT NULL,
    review_campaign_id VARCHAR(50) NOT NULL,
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewer_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    decision VARCHAR(20),
    notes TEXT,
    deadline TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_access_reviews_type CHECK (review_type IN ('privileged', 'tenant_admin', 'recertification')),
    CONSTRAINT ck_access_reviews_decision CHECK (decision IS NULL OR decision IN ('certified', 'rejected', 'pending'))
);

CREATE INDEX idx_access_reviews_account_campaign ON access_reviews(account_id, review_campaign_id);
CREATE INDEX idx_access_reviews_deadline_decision ON access_reviews(deadline, decision) WHERE decision = 'pending';
CREATE INDEX idx_access_reviews_tenant_type ON access_reviews(tenant_id, review_type);
```

---

## §3 — Tenants augmentés (Bloc 7 §7.2)

```sql
-- Migration B7.S1 : enrichir Tenant avec vertical + brand_* + e-invoicing prep
ALTER TABLE tenants
    ADD COLUMN vertical VARCHAR(50) REFERENCES verticals(code) ON DELETE RESTRICT,
    -- NOT NULL après backfill (cf. 51-alembic-migrations.md)
    
    -- White-label per-tenant (Q44=A+C)
    ADD COLUMN brand_display_name VARCHAR(100),
    ADD COLUMN brand_logo_url VARCHAR(500),
    ADD COLUMN brand_email_from VARCHAR(255),
    ADD COLUMN brand_dkim_domain VARCHAR(255),
    ADD COLUMN brand_primary_color VARCHAR(7),
    -- Format hex '#A52A2A' (CHECK regex)

    -- Vague 4 V4-P0-03 (F368) + Vague 5 V5-P0-02 (F295) — multi-tenant WebAuthn + frontend_url
    ADD COLUMN rp_id VARCHAR(253),
    -- WebAuthn Relying Party ID (domaine sans protocole, ex: 'marveline.com', 'splendid.events').
    -- NULL = fallback settings.JWT_ISSUER. Critique pour FIDO2 multi-tenant (F368).
    ADD COLUMN frontend_url VARCHAR(512),
    -- URL frontend per-tenant pour emails transactionnels (reset password, invitations)
    -- ET expected_origin WebAuthn. NULL = fallback settings.FRONTEND_URL. F295 + F368.
    
    -- Postmark (Q18=A) — chiffré KMS
    ADD COLUMN postmark_server_token_encrypted BYTEA,
    ADD COLUMN postmark_server_token_key_version INTEGER,
    
    -- E-invoicing UE prep (Bloc 3 Q19=A — colonnes nullable, activation différée)
    ADD COLUMN peppol_id VARCHAR(100),
    ADD COLUMN chorus_pro_id VARCHAR(100),
    ADD COLUMN e_invoice_status VARCHAR(20),
    
    -- Settings tenant déportés en table séparée `tenant_settings` (cf. §3bis ci-dessous).
    -- Why : éviter mutation row `tenants` à chaque change settings (cache invalidation + verrou row),
    --       permettre audit séparé via trigger, purger settings sans toucher tenants (RGPD).
    --       Cohérent avec B2.S2 provisioning (INSERT INTO tenant_settings) + B4.S4 Q27=B (rfm_thresholds).
    
    -- Status (renommé status existant si présent)
    ADD COLUMN suspended_at TIMESTAMPTZ,
    ADD COLUMN suspended_reason VARCHAR(500);

-- Drop ancien CHECK enum strict app_code (B7.S1)
ALTER TABLE tenants DROP CONSTRAINT IF EXISTS ck_tenants_app_code;

-- Nouveau CHECK regex sur app_code (UNIQUE déjà présent)
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_app_code_format
    CHECK (app_code ~ '^[a-z][a-z0-9_]+$');

-- CHECK e_invoice_status enum
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_e_invoice_status
    CHECK (e_invoice_status IS NULL OR e_invoice_status IN ('not_emitted', 'submitted', 'accepted', 'rejected'));

-- CHECK brand_primary_color hex format
ALTER TABLE tenants ADD CONSTRAINT ck_tenants_brand_primary_color
    CHECK (brand_primary_color IS NULL OR brand_primary_color ~ '^#[0-9A-Fa-f]{6}$');

-- Drop is_multi_brand (Bloc 7 obsolète Q43=B)
ALTER TABLE tenants DROP COLUMN IF EXISTS is_multi_brand;

-- Nouvel index sur vertical (queries fréquentes : filtrer tenants par vertical)
CREATE INDEX idx_tenants_vertical ON tenants(vertical);

COMMENT ON COLUMN tenants.vertical IS 'FK verticals.code — modèle métier du tenant. Bloc 7 §7.2.';
COMMENT ON COLUMN tenants.brand_email_from IS 'Sender email per-tenant white-label. Q44=A+C.';
COMMENT ON COLUMN tenants.peppol_id IS 'E-invoicing UE — PEPPOL participant ID. Activation 2026 Q19=A.';
COMMENT ON COLUMN tenants.rp_id IS 'WebAuthn Relying Party ID per-tenant (F368). Bloc 2 Q6=B + Bloc 7 Q43=B (Splendid).';
COMMENT ON COLUMN tenants.frontend_url IS 'Frontend URL per-tenant pour emails transactionnels + WebAuthn expected_origin (F295 + F368).';
```

---

## §3bis — `tenant_settings` (table EXISTANTE — Vague 8 alignement état réel)

> **Vague 8 — état réel** : la table `tenant_settings` **existe déjà** dans le code (`app/models/tenant_settings.py`, migration `v3w4x5y6z7a8`). Le plan Vague 3 prévoyait sa création (`d1e2f3a4b5c6a` en B2.S2) — c'était **faux**. Cette §3bis documente la structure EXISTANTE et liste les colonnes à AJOUTER pour les besoins du refactor (Q27=B, Q28=B, multi-tenant migration).

### Structure actuelle (à conserver)

```python
# app/models/tenant_settings.py — état actuel
class TenantSettings(Base, TimestampMixin):
    __tablename__ = "tenant_settings"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, nullable=False, unique=True, index=True)

    # Identité société (already there)
    company_name, company_email, company_phone, company_address

    # Paramètres fiscaux (TR-3/TR-18 friction — Float = perte précision, Marveline 0.20 default)
    vat_rate = Column(Float, nullable=False, default=0.20)

    # Tarifs main-d'œuvre EUR/heure (Marveline-spécifique, peut migrer en JSONB plus tard)
    hourly_rate_weekday, hourly_rate_weekend

    # CGV Marveline — financiers réservation
    advance_rate, deposit_multiplier, cancellation_threshold_days,
    cancellation_early_penalty_rate, cancellation_late_penalty_rate

    # Guards livraison
    block_delivery_without_advance, require_signature_before_delivery

    # Logistique + impression ticket B6.S5
    origin_postal_code, printer_host, printer_port,
    nom_commerce, adresse, siret, telephone

    # Identité tenant-scoped (TR-64 + V5-P0-02)
    frontend_url, mfa_issuer_name

    # Reporting
    reservation_uplift_pct
```

### Colonnes à AJOUTER (refactor)

```sql
-- Migration B4.S4 — Q27=B RFM per-tenant
ALTER TABLE tenant_settings
    ADD COLUMN rfm_thresholds JSONB;
COMMENT ON COLUMN tenant_settings.rfm_thresholds IS 'Q27=B — JSONB validé Pydantic RFMThresholds. NULL = fallback RFM_DEFAULTS runtime.';

-- Migration B4.S5 — Q28=B PII envelope encryption opt-in (par défaut activé)
ALTER TABLE tenant_settings
    ADD COLUMN pii_encryption_enabled BOOLEAN NOT NULL DEFAULT true;

-- Migration B5.S2 — multi-tenant resto/épicerie linkage
ALTER TABLE tenant_settings
    ADD COLUMN epicerie_tenant_id INTEGER REFERENCES tenants(id) ON DELETE SET NULL;
COMMENT ON COLUMN tenant_settings.epicerie_tenant_id IS 'Bloc 5 §5.2.4 — FK épicerie liée pour tenant restaurant (mapping ingrédients → produits).';

-- Migration B4.S3 — Numeric(5,4) pour vat_rate (TR-18 fix Float → Numeric)
ALTER TABLE tenant_settings
    ALTER COLUMN vat_rate TYPE NUMERIC(5,4) USING vat_rate::numeric(5,4);
```

### RLS (à ajouter en B1.S2)

```sql
-- Migration B1.S2 — RLS tenant-scoped (la table existe mais n'a probablement pas RLS yet)
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_tenant_settings ON tenant_settings
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::bigint);
ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY;
```

> **Note Vague 8** : le `tenant_settings` actuel a `id Integer PK` séparé du `tenant_id` (1-1 via UNIQUE). Le plan préfèrerait `tenant_id PK direct` mais le coût migration > bénéfice. On garde la structure actuelle.

---

## §4 — Customer augmenté

```sql
-- Migration B3.S4 : deposit_policy + B4.S4 : country ISO + B6.S1 : preferred_language
ALTER TABLE customers
    -- Bloc 3 Q14=C — deposit_policy per-customer
    ADD COLUMN requires_deposit BOOLEAN NOT NULL DEFAULT true,
    ADD COLUMN deposit_override_pct NUMERIC(5,4),
    -- NULL = utilise tenant.settings.default_deposit_pct ; sinon override per-customer
    
    -- Bloc 4 §4.2.15 — ISO 3166-2 alpha-2
    ADD COLUMN country_code VARCHAR(2) NOT NULL DEFAULT 'FR',
    -- Migration : backfill 'France'/'FRANCE' → 'FR'
    
    -- Bloc 6 §6.2.1 — i18n templates
    ADD COLUMN preferred_language VARCHAR(5) NOT NULL DEFAULT 'fr',
    -- Format: 'fr' | 'fr-FR' | 'en' | 'en-US'
    
    -- Bloc 4 §4.2.7 — PII chiffré (Q24 — périmètre complet, pas juste notes)
    -- Vague 5 V5-P0-01 : étendre au-delà de `notes` (RGPD Art.25 privacy by design)
    -- Migration step-by-step pour chaque colonne : add `*_encrypted` + `*_key_version`,
    -- backfill via worker Celery KMS, drop ancienne colonne plain text.
    ADD COLUMN notes_encrypted BYTEA,
    ADD COLUMN notes_key_version INTEGER,
    ADD COLUMN phone_encrypted BYTEA,
    ADD COLUMN phone_key_version INTEGER,
    ADD COLUMN address_encrypted BYTEA,
    ADD COLUMN address_key_version INTEGER,
    ADD COLUMN first_name_encrypted BYTEA,
    ADD COLUMN first_name_key_version INTEGER,
    ADD COLUMN last_name_encrypted BYTEA,
    ADD COLUMN last_name_key_version INTEGER,
    -- Comment: KMS context = 'customer_pii' + customer_id pour AAD

    -- Bloc 6 §6.2.2 — bounce tracking email
    ADD COLUMN email_invalid BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN email_bounce_at TIMESTAMPTZ;

ALTER TABLE customers ADD CONSTRAINT ck_customers_country_code_iso
    CHECK (country_code ~ '^[A-Z]{2}$');

ALTER TABLE customers ADD CONSTRAINT ck_customers_deposit_override_range
    CHECK (deposit_override_pct IS NULL OR (deposit_override_pct >= 0 AND deposit_override_pct <= 1));

-- Index trigram pour recherche perf (F453)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX idx_customers_search_trgm ON customers
    USING gin (
        (lower(coalesce(first_name, '') || ' ' || coalesce(last_name, '') || ' ' ||
               coalesce(company_name, '') || ' ' || coalesce(email, ''))) gin_trgm_ops
    );

COMMENT ON COLUMN customers.requires_deposit IS 'Q14=C — défaut true. Si false, pas d''acompte exigé.';
COMMENT ON COLUMN customers.deposit_override_pct IS 'NULL = tenant default. 0.30 = 30%. Q14=C.';
```

---

## §5 — Catalogue restructuré

### 5.1 `categories` augmenté (Bloc 4 §4.2.1)

```sql
-- Migration B4.S3 : Category devient FK obligatoire de Product
ALTER TABLE categories
    ADD COLUMN code VARCHAR(50),
    -- canonical lower_snake (ex: 'assiettes', 'fruits_legumes')
    
    ADD COLUMN tva_rate NUMERIC(5,4) NOT NULL DEFAULT 0.20,
    -- Q23=A. 0.20 default Marveline location. Migration backfill par vertical au seed.
    
    ADD COLUMN advance_booking_days INTEGER NOT NULL DEFAULT 0,
    -- F496 — devient per-Category (pas per-Product)
    
    ADD COLUMN cleaning_fee_cents_default BIGINT,
    -- Optional default cleaning fee per category
    
    ADD COLUMN depth INTEGER NOT NULL DEFAULT 0,
    -- Calculé par trigger BEFORE INSERT/UPDATE (cf. §14)
    
    -- Drop brand_code (Q43=B obsolète Bloc 7)
    DROP COLUMN IF EXISTS brand_code;

-- UNIQUE (tenant_id, code)
ALTER TABLE categories ADD CONSTRAINT uq_categories_tenant_code UNIQUE (tenant_id, code);

-- CHECK depth max 5 (F494)
ALTER TABLE categories ADD CONSTRAINT ck_categories_depth_max
    CHECK (depth >= 0 AND depth <= 5);

-- CHECK tva_rate range
ALTER TABLE categories ADD CONSTRAINT ck_categories_tva_rate_range
    CHECK (tva_rate >= 0 AND tva_rate <= 1);

-- FK parent_id — ondelete=SET NULL (orphelins acceptables — F492)
ALTER TABLE categories DROP CONSTRAINT IF EXISTS fk_categories_parent;
ALTER TABLE categories ADD CONSTRAINT fk_categories_parent
    FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL;

COMMENT ON COLUMN categories.tva_rate IS 'TVA per-category — Q23=A. Override per-product via Product.tva_rate_override (rare).';
COMMENT ON COLUMN categories.depth IS 'Profondeur hiérarchie (0=racine, max 5). Calculé par trigger BEFORE UPDATE.';
```

### 5.2 `products` restructuré (Bloc 4 §4.2.1, §4.2.2 + Bloc 7 §7.2)

```sql
-- Migration B4.S2 + B4.S3 + B7.S2
ALTER TABLE products
    -- Bloc 4 §4.2.1 — category devient FK
    ADD COLUMN category_id BIGINT,
    -- NOT NULL après backfill seed
    
    -- Bloc 4 §4.6 Q23 — override per-product (rare)
    ADD COLUMN tva_rate_override NUMERIC(5,4);

-- Backfill category_id (cf. 51-alembic-migrations.md B4.S3)

-- Après backfill : ALTER COLUMN NOT NULL + drop ancienne string
ALTER TABLE products ALTER COLUMN category_id SET NOT NULL;
ALTER TABLE products ADD CONSTRAINT fk_products_category
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT;

ALTER TABLE products
    DROP COLUMN IF EXISTS category,
    -- ancienne string CHECK 20 valeurs Marveline
    
    DROP CONSTRAINT IF EXISTS check_product_category_valid,
    
    -- Bloc 4 §4.2.2 — drop colonnes denormalized
    DROP COLUMN IF EXISTS available_quantity,
    DROP COLUMN IF EXISTS stock_quantity,
    
    -- Bloc 4 §4.2.1 — drop colonnes migrées vers Category
    DROP COLUMN IF EXISTS tva_rate,
    DROP COLUMN IF EXISTS requires_advance_booking_days,
    
    -- Bloc 7 §7.2 — drop brand_code (Q43=B obsolète)
    DROP COLUMN IF EXISTS brand_code,
    
    -- Bloc 4 §4.2.16 — drop image_url denormalized (cf. ProductImage exclusive primary)
    DROP COLUMN IF EXISTS image_url;

-- Bloc 4 §4.2.16 — vocabulaire condition unifié (ENUM PostgreSQL natif)
CREATE TYPE item_condition AS ENUM ('new', 'good', 'used', 'damaged', 'out_of_service', 'missing');

-- Migration data 'use' → 'used', 'neuf' → 'new', etc. (cf. 51-alembic-migrations.md)
ALTER TABLE products ALTER COLUMN condition TYPE item_condition USING (
    CASE condition
        WHEN 'neuf' THEN 'new'::item_condition
        WHEN 'bon' THEN 'good'::item_condition
        WHEN 'use' THEN 'used'::item_condition
        WHEN 'hors_service' THEN 'out_of_service'::item_condition
        ELSE 'good'::item_condition
    END
);

-- CHECK tva_rate_override range
ALTER TABLE products ADD CONSTRAINT ck_products_tva_rate_override_range
    CHECK (tva_rate_override IS NULL OR (tva_rate_override >= 0 AND tva_rate_override <= 1));

-- Index trigram nom + sku (F512)
CREATE INDEX idx_products_search_trgm ON products
    USING gin ((lower(coalesce(name, '') || ' ' || coalesce(sku, ''))) gin_trgm_ops);
```

### 5.3 `bundle_items` augmenté (Bloc 4 §4.2.11)

```sql
ALTER TABLE bundle_items
    ADD COLUMN bundle_unit_price_cents BIGINT;
    -- NULL = prorata depuis Bundle.price_cents ; sinon override

ALTER TABLE bundle_items ADD CONSTRAINT ck_bundle_items_unit_price_positive
    CHECK (bundle_unit_price_cents IS NULL OR bundle_unit_price_cents >= 0);

-- FK ondelete=RESTRICT (F490, F491)
ALTER TABLE bundle_items DROP CONSTRAINT IF EXISTS fk_bundle_item_product;
ALTER TABLE bundle_items ADD CONSTRAINT fk_bundle_item_product
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT;

ALTER TABLE bundle_items DROP CONSTRAINT IF EXISTS fk_bundle_item_bundle;
ALTER TABLE bundle_items ADD CONSTRAINT fk_bundle_item_bundle
    FOREIGN KEY (bundle_id) REFERENCES product_bundles(id) ON DELETE CASCADE;
```

---

## §6 — Stock unique source de vérité (Bloc 4 §4.2.2)

### 6.1 View matérialisée `product_stock_view`

```sql
-- Bloc 4 Q22=A : StockItem unique source de vérité
CREATE MATERIALIZED VIEW product_stock_view AS
SELECT
    si.tenant_id,
    si.product_id,
    si.variant_id,
    COUNT(*) FILTER (WHERE si.status = 'available'::stock_item_status)                  AS available,
    COUNT(*) FILTER (WHERE si.status = 'reserved'::stock_item_status)                   AS reserved,
    COUNT(*) FILTER (WHERE si.status = 'on_location'::stock_item_status)                AS on_location,
    COUNT(*) FILTER (WHERE si.status IN ('damaged'::stock_item_status, 'in_repair'::stock_item_status)) AS unavailable,
    COUNT(*) FILTER (WHERE si.status != 'retired'::stock_item_status)                   AS total_active
FROM stock_items si
WHERE si.retired = false
GROUP BY si.tenant_id, si.product_id, si.variant_id;

-- Index UNIQUE pour REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX uq_product_stock_view_pkv ON product_stock_view (tenant_id, product_id, variant_id);

CREATE INDEX idx_product_stock_view_tenant_product ON product_stock_view (tenant_id, product_id);

COMMENT ON MATERIALIZED VIEW product_stock_view IS 'Quantités stock dérivées de stock_items. Bloc 4 Q22=A. Refresh debounced 5s via Redis lock.';
```

### 6.2 `stock_item_status` ENUM PostgreSQL natif (FSM)

```sql
CREATE TYPE stock_item_status AS ENUM (
    'available', 'reserved', 'on_location', 'damaged', 'in_repair', 'retired'
);

ALTER TABLE stock_items ALTER COLUMN status TYPE stock_item_status USING status::stock_item_status;
```

(Trigger FSM `stock_item_status` cf. §14.)

### 6.3 PMP/WAC sur `stock_management` (Bloc 3 Q13=A)

> **Q13=A — PMP partout** (épicerie + Marveline). `inventory_movements.unit_cost_at_entry_cents`
> capturé à chaque entrée stock. `stock_management.weighted_avg_cost_cents` recalculé par trigger
> à chaque réception : `WAC_new = (qty_old × WAC_old + qty_in × cost_in) / (qty_old + qty_in)`.
> Cf. architecture-cible.md §3.6 Q13.

```sql
-- Capture du coût d'entrée par mouvement (PMP source)
ALTER TABLE inventory_movements
    ADD COLUMN unit_cost_at_entry_cents BIGINT;

ALTER TABLE inventory_movements ADD CONSTRAINT ck_inventory_movements_unit_cost_positive
    CHECK (unit_cost_at_entry_cents IS NULL OR unit_cost_at_entry_cents >= 0);

COMMENT ON COLUMN inventory_movements.unit_cost_at_entry_cents IS
    'Coût unitaire HT en centimes au moment de l''entrée stock (Bloc 3 Q13=A). NULL pour mouvements sortie/transfert (cost = WAC courant).';

-- WAC agrégé par stock_management (par tenant × product × variant)
ALTER TABLE stock_management
    ADD COLUMN weighted_avg_cost_cents BIGINT NOT NULL DEFAULT 0;

ALTER TABLE stock_management ADD CONSTRAINT ck_stock_management_wac_positive
    CHECK (weighted_avg_cost_cents >= 0);

COMMENT ON COLUMN stock_management.weighted_avg_cost_cents IS
    'PMP (Prix Moyen Pondéré) en centimes. Recalculé par trigger trg_stock_management_wac_recompute à chaque insert dans inventory_movements avec unit_cost_at_entry_cents NOT NULL. Bloc 3 Q13=A.';

-- Trigger de recalcul WAC sur entrée stock
CREATE OR REPLACE FUNCTION fn_stock_management_wac_recompute()
RETURNS TRIGGER AS $$
DECLARE
    v_qty_old BIGINT;
    v_wac_old BIGINT;
    v_qty_new BIGINT;
    v_wac_new BIGINT;
BEGIN
    -- Trigger uniquement pour entrées avec coût (réceptions fournisseur)
    IF NEW.unit_cost_at_entry_cents IS NULL OR NEW.quantity <= 0 THEN
        RETURN NEW;
    END IF;

    SELECT quantity_on_hand, weighted_avg_cost_cents
        INTO v_qty_old, v_wac_old
    FROM stock_management
    WHERE tenant_id = NEW.tenant_id
      AND product_id = NEW.product_id
    FOR UPDATE;

    v_qty_new := COALESCE(v_qty_old, 0) + NEW.quantity;
    v_wac_new := (
        COALESCE(v_qty_old, 0) * COALESCE(v_wac_old, 0)
        + NEW.quantity * NEW.unit_cost_at_entry_cents
    ) / GREATEST(v_qty_new, 1);

    UPDATE stock_management
        SET weighted_avg_cost_cents = v_wac_new
    WHERE tenant_id = NEW.tenant_id
      AND product_id = NEW.product_id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_management_wac_recompute
    AFTER INSERT ON inventory_movements
    FOR EACH ROW
    EXECUTE FUNCTION fn_stock_management_wac_recompute();
```

**Test invariant associé** (à ajouter dans `53-tests-strategy.md` §8 si Bloc 4 actif) :
```python
# WAC ne descend jamais en dessous de zéro, et reste cohérent après cycle entrée/sortie
async def test_invariant_wac_consistency(db, tenant):
    # ... test de propriété mathématique du PMP
```



### 7.1 `points_ledger` (refondu avec LedgerEntryMixin)

```sql
-- Si ledger n'existait pas : CREATE TABLE
-- Si existe : ALTER pour aligner sur LedgerEntryMixin

CREATE TABLE points_ledger (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    member_id BIGINT NOT NULL REFERENCES loyalty_members(id) ON DELETE RESTRICT,
    
    entry_type VARCHAR(30) NOT NULL,
    -- 'earn' | 'redeem' | 'expire' | 'adjust' | 'bonus'
    
    amount INTEGER NOT NULL,
    -- Points (positif = crédit, négatif = débit)
    
    balance_after INTEGER NOT NULL,
    -- Solde dénormalisé après cette entry
    
    related_entity_type VARCHAR(50),
    related_entity_id BIGINT,
    -- Ex: 'Reservation', 'Vente', 'Invoice'
    
    expires_at TIMESTAMPTZ,
    -- NULL si pas d'expiration (ex: redeem)
    
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    actor_account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT ck_points_ledger_entry_type
        CHECK (entry_type IN ('earn', 'redeem', 'expire', 'adjust', 'bonus'))
);

-- Index lookup par member (chronologique)
CREATE INDEX idx_points_ledger_member_created ON points_ledger (member_id, created_at DESC);

-- Index expiry (Celery expire_points_task)
CREATE INDEX idx_points_ledger_expires ON points_ledger (expires_at)
    WHERE expires_at IS NOT NULL AND amount > 0;

-- Index lookup par related entity (debug)
CREATE INDEX idx_points_ledger_related ON points_ledger (related_entity_type, related_entity_id);

COMMENT ON TABLE points_ledger IS 'Ledger fidélité — append-only, balance_after dénormalisé. Bloc 3 §3.2.15.';
COMMENT ON COLUMN points_ledger.amount IS 'Positif = crédit, négatif = débit. Trigger immutability empêche UPDATE/DELETE.';
```

### 7.2 `revenue_ledger` (idem pattern)

```sql
CREATE TABLE revenue_ledger (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    customer_id BIGINT NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
    
    entry_type VARCHAR(30) NOT NULL,
    -- 'invoice_emit' | 'invoice_pay' | 'credit_note' | 'adjust'
    
    amount_cents BIGINT NOT NULL,
    
    cumulative_after_cents BIGINT NOT NULL,
    -- Cumul revenu après cette entry (équivalent balance_after)
    
    related_entity_type VARCHAR(50),
    related_entity_id BIGINT,
    
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    actor_account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT ck_revenue_ledger_entry_type
        CHECK (entry_type IN ('invoice_emit', 'invoice_pay', 'credit_note', 'adjust'))
);

CREATE INDEX idx_revenue_ledger_customer_created ON revenue_ledger (customer_id, created_at DESC);
CREATE INDEX idx_revenue_ledger_tenant_created ON revenue_ledger (tenant_id, created_at DESC);
```

### 7.3 `payment_ledger` (idem)

```sql
CREATE TABLE payment_ledger (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    invoice_id BIGINT NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    
    entry_type VARCHAR(30) NOT NULL,
    -- 'payment' | 'refund' | 'adjust'
    
    amount_cents BIGINT NOT NULL,
    
    method VARCHAR(30) NOT NULL,
    -- 'card' | 'cash' | 'transfer' | 'check' | 'mix'
    
    transaction_reference VARCHAR(100),
    -- Référence externe (Stripe charge_id, etc.)
    
    related_entity_type VARCHAR(50),
    related_entity_id BIGINT,
    
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    actor_account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT ck_payment_ledger_entry_type
        CHECK (entry_type IN ('payment', 'refund', 'adjust')),
    CONSTRAINT ck_payment_ledger_method
        CHECK (method IN ('card', 'cash', 'transfer', 'check', 'mix'))
);

CREATE INDEX idx_payment_ledger_invoice ON payment_ledger (invoice_id, created_at DESC);
```

---

## §8 — Invoice immutability + e-invoicing prep

### 8.1 `invoices` augmenté

```sql
-- Bloc 3 §3.2.10 : reference UNIQUE per-tenant (drop UNIQUE global)
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS uq_invoices_reference;
ALTER TABLE invoices ADD CONSTRAINT uq_invoices_tenant_reference UNIQUE (tenant_id, invoice_number);

-- Bloc 3 §3.2.16 : e-invoicing UE prep
ALTER TABLE invoices
    ADD COLUMN electronic_invoice_id VARCHAR(100),
    ADD COLUMN peppol_message_id VARCHAR(100),
    ADD COLUMN chorus_pro_message_id VARCHAR(100),
    ADD COLUMN e_invoice_status VARCHAR(20),
    ADD COLUMN e_invoice_submitted_at TIMESTAMPTZ;

ALTER TABLE invoices ADD CONSTRAINT ck_invoices_e_invoice_status
    CHECK (e_invoice_status IS NULL OR e_invoice_status IN ('not_emitted', 'submitted', 'accepted', 'rejected'));

COMMENT ON COLUMN invoices.electronic_invoice_id IS 'E-invoicing UE — ID PDP. Q19=A activation 2026.';
```

### 8.2 `invoice_lines.tva_rate_snapshot` (Bloc 3 §3.2.3)

```sql
ALTER TABLE invoice_lines
    ADD COLUMN tva_rate_snapshot NUMERIC(5,4) NOT NULL DEFAULT 0.20;
    -- Default 0.20 temporaire pour ALTER. Backfill puis DROP DEFAULT.

-- Migration backfill : SELECT tva_rate from products via category lookup, set sur lines existantes
-- (cf. 51-alembic-migrations.md B3.S3)

-- Après backfill :
ALTER TABLE invoice_lines ALTER COLUMN tva_rate_snapshot DROP DEFAULT;

ALTER TABLE invoice_lines ADD CONSTRAINT ck_invoice_lines_tva_range
    CHECK (tva_rate_snapshot >= 0 AND tva_rate_snapshot <= 1);

COMMENT ON COLUMN invoice_lines.tva_rate_snapshot IS 'TVA capturée à émission. Bloc 3 TR-3 / §3.2.3.';
```

Pareil pour `devis_lines`, `reservation_lines`, `vente_lines`, `epicerie_vente_lignes`, `lignes_commande_restaurant`.

---

## §9 — Pricing rules (Bloc 4 §4.2.5)

```sql
-- Bloc 4 Q25=A : Numeric(5,4) cumul additif
CREATE TYPE pricing_rule_type AS ENUM (
    'flat', 'per_day', 'tiered', 'volume', 'seasonal', 'custom'
);

CREATE TYPE pricing_applies_to AS ENUM (
    'product', 'category', 'all'
);

-- Drop legacy discount_pct INTEGER (interprétation ÷100/÷10000 ambiguë)
-- Migration : convertir Integer → Numeric(5,4)
ALTER TABLE pricing_rules
    ADD COLUMN discount_pct_new NUMERIC(5,4);

-- Backfill: SELECT id, discount_pct FROM pricing_rules
-- UPDATE pricing_rules SET discount_pct_new = discount_pct / 100.0 WHERE rule_type IN ('custom', 'seasonal')
-- (cohérent avec ancienne logique engine ÷100, déjà sémantique correcte)

ALTER TABLE pricing_rules
    DROP COLUMN discount_pct;

ALTER TABLE pricing_rules
    RENAME COLUMN discount_pct_new TO discount_pct;

ALTER TABLE pricing_rules ADD CONSTRAINT ck_pricing_rules_discount_range
    CHECK (discount_pct IS NULL OR (discount_pct >= 0 AND discount_pct <= 1));

-- Migration rule_type/applies_to vers ENUM PostgreSQL natif
ALTER TABLE pricing_rules ALTER COLUMN rule_type TYPE pricing_rule_type USING rule_type::pricing_rule_type;
ALTER TABLE pricing_rules ALTER COLUMN applies_to TYPE pricing_applies_to USING applies_to::pricing_applies_to;

-- CHECK valid_from <= valid_to (F538)
ALTER TABLE pricing_rules ADD CONSTRAINT ck_pricing_rules_dates
    CHECK (valid_from IS NULL OR valid_to IS NULL OR valid_from <= valid_to);

-- target_id BigInteger (drift Integer vs BigInteger F542)
ALTER TABLE pricing_rules ALTER COLUMN target_id TYPE BIGINT;

-- Renommage active → is_active (convention SoftDeleteMixin — F540)
ALTER TABLE pricing_rules RENAME COLUMN active TO is_active;
```

---

## §10 — Audit refondu (Bloc 6 §6.2.4)

```sql
-- Bloc 6 §6.2.4 — HMAC chaîné blockchain
ALTER TABLE audit_logs
    ADD COLUMN prev_hmac VARCHAR(64),
    -- SHA-256 hex de l'audit log précédent du même tenant (NULL pour le 1er)
    
    ADD COLUMN hmac_key_version INTEGER NOT NULL DEFAULT 1;
    -- Versioning de la KEK HMAC pour rotation

-- Index lookup chronologique par tenant (pour vérification chaîne)
CREATE INDEX idx_audit_logs_tenant_chain ON audit_logs (tenant_id, created_at, id);

-- FK tenant_id propre (F999)
ALTER TABLE audit_logs DROP CONSTRAINT IF EXISTS fk_audit_logs_tenant;
ALTER TABLE audit_logs ADD CONSTRAINT fk_audit_logs_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE RESTRICT;

ALTER TABLE audit_logs ADD CONSTRAINT ck_audit_logs_tenant_positive
    CHECK (tenant_id > 0);

-- Bloc 6 §6.2.6 — PII chiffré sur changes + description
ALTER TABLE audit_logs
    ADD COLUMN changes_encrypted BYTEA,
    ADD COLUMN changes_key_version INTEGER,
    ADD COLUMN description_encrypted BYTEA,
    ADD COLUMN description_key_version INTEGER;

-- Migration data : encrypt existing rows via Celery task (cf. B6.S2)

-- Après migration backfill : drop colonnes clear-text
-- ALTER TABLE audit_logs DROP COLUMN changes;
-- ALTER TABLE audit_logs DROP COLUMN description;

-- entity_type ENUM (F1004, F1018)
CREATE TYPE audit_entity_type AS ENUM (
    'Account', 'Tenant', 'TenantMembership', 'Customer', 'Product', 'Category',
    'Reservation', 'Devis', 'Invoice', 'Payment', 'Vente',
    'Commande', 'InstancePreparation', 'EpicerieVente', 'EtlImport',
    'Supplier', 'SupplierOrder', 'LoyaltyMember', 'PointsLedger',
    'Bundle', 'StockItem', 'InventoryMovement', 'Relance',
    'AuthFactor', 'ApiKey', 'FeatureFlag', 'Ticket'
);

-- Migration entity_type VARCHAR → ENUM
-- (avec mapping pluriel → singulier strict)

ALTER TABLE audit_logs ALTER COLUMN entity_type TYPE audit_entity_type
    USING (CASE entity_type
        WHEN 'customers' THEN 'Customer'::audit_entity_type
        WHEN 'products' THEN 'Product'::audit_entity_type
        -- ... (mapping complet)
        ELSE entity_type::audit_entity_type
    END);

COMMENT ON COLUMN audit_logs.prev_hmac IS 'HMAC SHA-256 hex de l''audit précédent (chaîne blockchain). Bloc 6 §6.2.4.';
```

### 10.1 Verify chain helper view

```sql
CREATE OR REPLACE VIEW audit_chain_integrity_view AS
SELECT
    a.id,
    a.tenant_id,
    a.created_at,
    a.hmac_signature,
    a.prev_hmac,
    LAG(a.hmac_signature) OVER (PARTITION BY a.tenant_id ORDER BY a.id) AS expected_prev_hmac,
    (a.prev_hmac IS DISTINCT FROM LAG(a.hmac_signature) OVER (PARTITION BY a.tenant_id ORDER BY a.id)) AS chain_broken
FROM audit_logs a
ORDER BY a.tenant_id, a.id;
```

Job nightly `verify_audit_chain_task` lit cette view et alerte si `chain_broken=true` (sauf 1ère ligne).

---

## §11 — Notification log (Bloc 6 §6.2.2)

### 11.1 `notifications` refondu (in-app uniquement)

```sql
-- Migration B6.S1 : convention v2.0 + TenantMixin + FK
ALTER TABLE notifications
    ADD COLUMN account_id BIGINT REFERENCES accounts(id) ON DELETE CASCADE,
    -- (replace user_id Integer sans FK — F850)
    
    -- PII chiffré (Bloc 4 §4.2.7 cohérence)
    ADD COLUMN message_encrypted BYTEA,
    ADD COLUMN message_key_version INTEGER,
    
    ADD COLUMN read_at TIMESTAMPTZ;

-- Backfill account_id depuis user_id si possible
-- UPDATE notifications SET account_id = user_id;

-- Drop user_id legacy
ALTER TABLE notifications DROP COLUMN user_id;

-- TimestampMixin déjà présent (created_at) ; ajouter updated_at
ALTER TABLE notifications ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- TenantMixin : tenant_id FK propre
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS fk_notifications_tenant;
ALTER TABLE notifications ADD CONSTRAINT fk_notifications_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE notifications ALTER COLUMN tenant_id TYPE BIGINT;

-- Index unread scan (F865)
CREATE INDEX idx_notifications_account_unread
    ON notifications (tenant_id, account_id, is_read)
    WHERE is_read = false;
```

### 11.2 `notification_log` (NEW)

```sql
CREATE TABLE notification_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    customer_id BIGINT REFERENCES customers(id) ON DELETE SET NULL,
    
    channel VARCHAR(20) NOT NULL,
    -- 'email' | 'sms' | 'push' | 'in_app'
    
    template_key VARCHAR(100) NOT NULL,
    -- Ex: 'password_reset', 'relance_level1', 'reservation_confirmed'
    
    recipient VARCHAR(500) NOT NULL,
    -- Email, phone, device token...
    
    gateway_message_id VARCHAR(255),
    -- Postmark MessageID, Twilio SID, etc.
    
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 'pending' | 'sent' | 'delivered' | 'bounced' | 'failed'
    
    error TEXT,
    -- Si status='failed' ou 'bounced'
    
    bounce_type VARCHAR(50),
    -- 'hard_bounce' | 'soft_bounce' | 'spam_complaint' (Postmark webhook)
    
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    bounced_at TIMESTAMPTZ,
    
    related_entity_type VARCHAR(50),
    related_entity_id BIGINT,
    -- Ex: 'Relance', 'PasswordReset', 'Invoice'
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT ck_notification_log_channel
        CHECK (channel IN ('email', 'sms', 'push', 'in_app')),
    CONSTRAINT ck_notification_log_status
        CHECK (status IN ('pending', 'sent', 'delivered', 'bounced', 'failed'))
);

CREATE INDEX idx_notification_log_tenant_created ON notification_log (tenant_id, created_at DESC);
CREATE INDEX idx_notification_log_status_failed ON notification_log (status, created_at)
    WHERE status IN ('failed', 'bounced');
CREATE INDEX idx_notification_log_gateway_msg ON notification_log (gateway_message_id)
    WHERE gateway_message_id IS NOT NULL;
CREATE INDEX idx_notification_log_related ON notification_log (related_entity_type, related_entity_id);

COMMENT ON TABLE notification_log IS 'Log envois email/SMS/push avec bounce tracking. Bloc 6 §6.2.2.';
```

---

## §12 — Feature flag history + M:N tenants (Bloc 6 §6.2.10)

### 12.1 `feature_flag_tenants` (drop ARRAY orphan F1034)

```sql
CREATE TABLE feature_flag_tenants (
    feature_flag_id BIGINT NOT NULL REFERENCES feature_flags(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    PRIMARY KEY (feature_flag_id, tenant_id),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feature_flag_tenants_tenant ON feature_flag_tenants (tenant_id);

-- Migration : ARRAY[int] → table M:N
-- INSERT INTO feature_flag_tenants (feature_flag_id, tenant_id)
-- SELECT id, unnest(target_tenants) FROM feature_flags WHERE target_tenants IS NOT NULL;

-- Drop colonne ARRAY après backfill
ALTER TABLE feature_flags DROP COLUMN target_tenants;

-- Vague 5 V5-P0-04 (F1031) — fail_safe_value : sécurité sur incident Redis+DB down
-- Pour mfa_enabled : fail_safe_value = TRUE (dans le doute, on force MFA)
-- Pour disable_dangerous_feature : fail_safe_value = TRUE (dans le doute, on désactive)
ALTER TABLE feature_flags
    ADD COLUMN fail_safe_value BOOLEAN NOT NULL DEFAULT false;
COMMENT ON COLUMN feature_flags.fail_safe_value IS
    'Valeur retournée par is_feature_enabled() en cas d''incident infra (Redis+DB down). '
    'Bloc 6 Q37 + V5-P0-04 (F1031). Critique pour flags sécurité : mfa_enabled=true, disable_dangerous=true.';
```

### 12.2 `feature_flag_history` (NEW)

```sql
CREATE TABLE feature_flag_history (
    id BIGSERIAL PRIMARY KEY,
    feature_flag_id BIGINT NOT NULL REFERENCES feature_flags(id) ON DELETE CASCADE,
    
    actor_account_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    
    field_changed VARCHAR(50) NOT NULL,
    -- Ex: 'is_enabled', 'rollout_pct', 'tenants', 'metadata_json'
    
    value_before TEXT,
    value_after TEXT,
    -- Pour booleans/integers : str() de la valeur. Pour ARRAY/JSONB : sérialisation JSON.
    
    reason VARCHAR(500),
    -- Optionnel : raison du changement (input UI admin)
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feature_flag_history_flag_created ON feature_flag_history (feature_flag_id, created_at DESC);

COMMENT ON TABLE feature_flag_history IS 'Audit trail des changements de feature flags. Bloc 6 §6.2.10.';
```

### 12.3 Trigger `feature_flags AFTER UPDATE`

```sql
CREATE OR REPLACE FUNCTION trg_feature_flag_history_fn() RETURNS trigger AS $$
DECLARE
    actor_id BIGINT;
BEGIN
    -- Récupère l'actor depuis variable session app.actor_account_id (Bloc 1 RLS pattern)
    actor_id := nullif(current_setting('app.actor_account_id', true), '')::bigint;
    
    IF NEW.is_enabled IS DISTINCT FROM OLD.is_enabled THEN
        INSERT INTO feature_flag_history (feature_flag_id, actor_account_id, field_changed, value_before, value_after)
        VALUES (NEW.id, actor_id, 'is_enabled', OLD.is_enabled::text, NEW.is_enabled::text);
    END IF;
    
    IF NEW.rollout_pct IS DISTINCT FROM OLD.rollout_pct THEN
        INSERT INTO feature_flag_history (feature_flag_id, actor_account_id, field_changed, value_before, value_after)
        VALUES (NEW.id, actor_id, 'rollout_pct', OLD.rollout_pct::text, NEW.rollout_pct::text);
    END IF;
    
    IF NEW.metadata_json IS DISTINCT FROM OLD.metadata_json THEN
        INSERT INTO feature_flag_history (feature_flag_id, actor_account_id, field_changed, value_before, value_after)
        VALUES (NEW.id, actor_id, 'metadata_json', OLD.metadata_json::text, NEW.metadata_json::text);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_feature_flag_history
    AFTER UPDATE ON feature_flags
    FOR EACH ROW EXECUTE FUNCTION trg_feature_flag_history_fn();
```

---

## §13 — Catalogue ETL per-tenant + price history

### 13.1 `categorie_produit_seed` (M00 read-only — Bloc 5 Q29=A)

```sql
CREATE TABLE categorie_produit_seed (
    code VARCHAR(50) PRIMARY KEY,
    parent_code VARCHAR(50) REFERENCES categorie_produit_seed(code) ON DELETE SET NULL,
    label VARCHAR(255) NOT NULL,
    tva_defaut NUMERIC(5,4) NOT NULL DEFAULT 0.055,
    -- 5.5% défaut alimentaire FR
    
    is_food BOOLEAN NOT NULL DEFAULT true,
    keywords TEXT[],
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pas de tenant_id : table seed globale read-only
-- Modifications via migration Alembic uniquement (pas via UI/API)

COMMENT ON TABLE categorie_produit_seed IS 'Seed M00 read-only des catégories alimentaires (91 codes). Copié vers categorie_produits per-tenant au provisioning. Bloc 5 Q29=A.';

-- Seed initial (extrait — liste complète 91 codes dans 51-alembic-migrations.md)
INSERT INTO categorie_produit_seed (code, label, tva_defaut, is_food) VALUES
    ('FRAIS_VIANDE', 'Viande fraîche', 0.055, true),
    ('FRAIS_BOEUF', 'Bœuf frais', 0.055, true),
    ('FRAIS_POULET', 'Poulet frais', 0.055, true),
    ('ALC_VIN_RGE', 'Vin rouge', 0.20, true),
    ('ALC_BIERE', 'Bière', 0.20, true),
    ('SEC_PATES', 'Pâtes sèches', 0.055, true),
    -- ... 85 autres codes
    ('AUTRE', 'Autre', 0.20, false);
```

### 13.2 `categorie_produits` (per-tenant — Bloc 5 Q29=A)

```sql
-- Existante mais ajout tenant_id NOT NULL
ALTER TABLE categorie_produits
    ADD COLUMN tenant_id BIGINT;

-- Backfill : pour chaque tenant épicerie/restaurant, copier categorie_produit_seed
-- (cf. 51-alembic-migrations.md B5.S2)

-- Après backfill :
ALTER TABLE categorie_produits ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE categorie_produits ADD CONSTRAINT fk_categorie_produits_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- UNIQUE (tenant_id, code)
ALTER TABLE categorie_produits ADD CONSTRAINT uq_categorie_produits_tenant_code
    UNIQUE (tenant_id, code);
```

### 13.3 `catalogue_produits` per-tenant + colonne FK

```sql
-- Bloc 5 §5.2.1 + §5.2.12
ALTER TABLE catalogue_produits
    ADD COLUMN tenant_id BIGINT,
    ADD COLUMN categorie_id BIGINT;

-- Backfill : pour chaque tenant, dupliquer catalogue_produits + lier categorie_id
-- (cf. 51-alembic-migrations.md B5.S2 + B5.S5)

ALTER TABLE catalogue_produits ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE catalogue_produits ADD CONSTRAINT fk_catalogue_produits_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;

ALTER TABLE catalogue_produits ALTER COLUMN categorie_id SET NOT NULL;
ALTER TABLE catalogue_produits ADD CONSTRAINT fk_catalogue_produits_categorie
    FOREIGN KEY (categorie_id) REFERENCES categorie_produits(id) ON DELETE RESTRICT;

-- Drop ancienne string categorie_code
ALTER TABLE catalogue_produits DROP COLUMN categorie_code;

-- Index lookup per-tenant
CREATE INDEX idx_catalogue_produits_tenant_ean ON catalogue_produits (tenant_id, ean) WHERE ean IS NOT NULL;
```

### 13.4 `catalogue_produit_price_history` (Bloc 5 §5.2.16)

```sql
CREATE TABLE catalogue_produit_price_history (
    id BIGSERIAL PRIMARY KEY,
    catalogue_produit_id BIGINT NOT NULL REFERENCES catalogue_produits(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    etl_import_id BIGINT REFERENCES etl_imports(id) ON DELETE SET NULL,
    
    prix_unitaire_cts_old BIGINT,
    prix_unitaire_cts_new BIGINT NOT NULL,
    taux_tva_centieme_old INTEGER,
    taux_tva_centieme_new INTEGER NOT NULL,
    conditionnement_old VARCHAR(100),
    conditionnement_new VARCHAR(100),
    
    source_fournisseur VARCHAR(100),
    
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_catalogue_price_history_produit_changed
    ON catalogue_produit_price_history (catalogue_produit_id, changed_at DESC);

COMMENT ON TABLE catalogue_produit_price_history IS 'Audit trail prix catalogue ETL — Bloc 5 §5.2.16.';
```

### 13.5 `etl_correction_history` per-tenant (Bloc 5 Q29=A)

```sql
ALTER TABLE etl_correction_history
    ADD COLUMN tenant_id BIGINT;

-- Backfill from related etl_import.tenant_id
-- (cf. 51-alembic-migrations.md B5.S2)

ALTER TABLE etl_correction_history ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE etl_correction_history ADD CONSTRAINT fk_etl_correction_history_tenant
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE;
```

### 13.6 `etl_imports.lignes_data_schema_version` (Bloc 5 §5.2.7)

```sql
ALTER TABLE etl_imports
    ADD COLUMN lignes_data_schema_version INTEGER NOT NULL DEFAULT 1;

COMMENT ON COLUMN etl_imports.lignes_data_schema_version IS 'Version du schema LigneParsee. Bloc 5 §5.2.7. Migrator handle versions <CURRENT.';
```

### 13.7 `etl_imports.statut` ECHEC + AWAITING_VENDOR_MATCH (Bloc 5 Q33=B + Q35=A)

```sql
ALTER TABLE etl_imports DROP CONSTRAINT IF EXISTS ck_etl_imports_statut;
ALTER TABLE etl_imports ADD CONSTRAINT ck_etl_imports_statut
    CHECK (statut IN (
        'PENDING', 'RUNNING', 'PREVIEW', 'VALIDATED',
        'SUCCES', 'PARTIEL', 'ECHEC',                  -- ECHEC ajouté Q35=A
        'REJECTED', 'REVERTED',
        'AWAITING_VENDOR_MATCH'                         -- Q33=B vendor matching strict
    ));
```

---

## §14 — Triggers FSM + ledger immutability

### 14.1 Trigger ledger immutability (Bloc 1 Q1=A + Bloc 3 §3.2.5)

```sql
CREATE OR REPLACE FUNCTION raise_immutable_ledger() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Table % is append-only. UPDATE/DELETE forbidden. Use compensating entry.', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_points_ledger_immutable
    BEFORE UPDATE OR DELETE ON points_ledger
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

CREATE TRIGGER trg_revenue_ledger_immutable
    BEFORE UPDATE OR DELETE ON revenue_ledger
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

CREATE TRIGGER trg_payment_ledger_immutable
    BEFORE UPDATE OR DELETE ON payment_ledger
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

-- Idem : epicerie_stock_movements, mouvements_stock_restaurant, inventory_movements
CREATE TRIGGER trg_epicerie_stock_movements_immutable
    BEFORE UPDATE OR DELETE ON epicerie_stock_movements
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

CREATE TRIGGER trg_mouvements_stock_restaurant_immutable
    BEFORE UPDATE OR DELETE ON mouvements_stock_restaurant
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

CREATE TRIGGER trg_inventory_movements_immutable
    BEFORE UPDATE OR DELETE ON inventory_movements
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();

-- Invoice : immutable APRÈS émission seulement (status='emitted' ou 'paid')
CREATE OR REPLACE FUNCTION raise_immutable_emitted_invoice() RETURNS trigger AS $$
BEGIN
    IF OLD.status IN ('emitted', 'paid', 'cancelled') THEN
        -- Allow only specific field updates (e_invoice_status, last_reminder_sent_at, etc.)
        IF NEW.total_ttc_cents IS DISTINCT FROM OLD.total_ttc_cents
           OR NEW.tva_total_cents IS DISTINCT FROM OLD.tva_total_cents
           OR NEW.invoice_number IS DISTINCT FROM OLD.invoice_number THEN
            RAISE EXCEPTION 'Invoice % already emitted. Cannot mutate financial fields. Use credit_note + new invoice.', OLD.invoice_number;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_invoices_immutable_emitted
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_emitted_invoice();
```

### 14.2 Trigger FSM transition guard (Bloc 3 §3.2.1)

```sql
-- Pattern générique : trigger qui valide OLD.status → NEW.status selon une matrice JSONB
-- (la matrice est stockée en table dédiée pour évolution sans déploiement code)

CREATE TABLE fsm_transitions (
    table_name VARCHAR(100) NOT NULL,
    from_status VARCHAR(50) NOT NULL,
    to_status VARCHAR(50) NOT NULL,
    PRIMARY KEY (table_name, from_status, to_status)
);

INSERT INTO fsm_transitions (table_name, from_status, to_status) VALUES
    -- DevisFSM
    ('devis', 'draft',     'sent'),
    ('devis', 'sent',      'accepted'),
    ('devis', 'sent',      'rejected'),
    ('devis', 'sent',      'expired'),
    ('devis', 'accepted',  'converted'),
    ('devis', 'accepted',  'cancelled'),
    
    -- ReservationFSM
    ('reservations', 'draft',      'confirmed'),
    ('reservations', 'confirmed',  'in_preparation'),
    ('reservations', 'in_preparation', 'ready'),
    ('reservations', 'ready',      'departed'),
    ('reservations', 'departed',   'on_location'),
    ('reservations', 'on_location', 'returned'),
    ('reservations', 'returned',   'completed'),
    ('reservations', 'confirmed',  'cancelled'),
    -- ... toutes les transitions valides
    
    -- StockItemFSM (Bloc 4 §4.2.3)
    ('stock_items', 'available',   'reserved'),
    ('stock_items', 'available',   'damaged'),
    ('stock_items', 'available',   'in_repair'),
    ('stock_items', 'available',   'retired'),
    ('stock_items', 'reserved',    'available'),
    ('stock_items', 'reserved',    'on_location'),
    ('stock_items', 'reserved',    'damaged'),
    ('stock_items', 'on_location', 'available'),
    ('stock_items', 'on_location', 'damaged'),
    ('stock_items', 'damaged',     'in_repair'),
    ('stock_items', 'damaged',     'retired'),
    ('stock_items', 'in_repair',   'available'),
    ('stock_items', 'in_repair',   'retired'),
    -- 'retired' est terminal (pas de transition sortante)
    
    -- EpicerieVenteFSM
    ('epicerie_ventes', 'EN_COURS',   'VALIDEE'),
    ('epicerie_ventes', 'EN_COURS',   'ANNULEE'),
    ('epicerie_ventes', 'VALIDEE',    'ANNULEE'),
    ('epicerie_ventes', 'VALIDEE',    'REMBOURSEE'),
    
    -- CommandeRestaurantFSM
    ('restaurant_commandes', 'OUVERTE', 'SERVIE'),
    ('restaurant_commandes', 'OUVERTE', 'ANNULEE'),
    ('restaurant_commandes', 'SERVIE',  'PAYEE'),
    ('restaurant_commandes', 'SERVIE',  'ANNULEE');
    -- ... etc.

CREATE OR REPLACE FUNCTION raise_illegal_fsm_transition() RETURNS trigger AS $$
DECLARE
    transition_exists BOOLEAN;
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        SELECT EXISTS(
            SELECT 1 FROM fsm_transitions
            WHERE table_name = TG_TABLE_NAME
              AND from_status = OLD.status::text
              AND to_status = NEW.status::text
        ) INTO transition_exists;
        
        IF NOT transition_exists THEN
            RAISE EXCEPTION 'Illegal FSM transition for table %: % → %',
                TG_TABLE_NAME, OLD.status, NEW.status
                USING ERRCODE = 'restrict_violation';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Application aux tables FSM-aware
CREATE TRIGGER trg_devis_fsm BEFORE UPDATE ON devis
    FOR EACH ROW EXECUTE FUNCTION raise_illegal_fsm_transition();
CREATE TRIGGER trg_reservations_fsm BEFORE UPDATE ON reservations
    FOR EACH ROW EXECUTE FUNCTION raise_illegal_fsm_transition();
CREATE TRIGGER trg_stock_items_fsm BEFORE UPDATE ON stock_items
    FOR EACH ROW EXECUTE FUNCTION raise_illegal_fsm_transition();
-- ... etc pour toutes les FSM
```

### 14.3 Trigger cross-tenant validation (Bloc 5 §5.2.2)

```sql
CREATE OR REPLACE FUNCTION validate_internal_transfer_tenants() RETURNS trigger AS $$
DECLARE
    src_vertical VARCHAR(50);
    dst_vertical VARCHAR(50);
BEGIN
    SELECT vertical INTO src_vertical FROM tenants WHERE id = NEW.tenant_id;
    SELECT vertical INTO dst_vertical FROM tenants WHERE id = NEW.dest_tenant_id;
    
    IF src_vertical IS NULL OR dst_vertical IS NULL THEN
        RAISE EXCEPTION 'InternalTransfer: tenant_id % or dest_tenant_id % not found',
            NEW.tenant_id, NEW.dest_tenant_id;
    END IF;
    
    IF src_vertical != 'epicerie' OR dst_vertical != 'restaurant' THEN
        RAISE EXCEPTION 'Invalid InternalTransfer vertical pair: % → %. Expected epicerie → restaurant.',
            src_vertical, dst_vertical;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_internal_transfer_tenants_validate
    BEFORE INSERT OR UPDATE ON internal_transfers
    FOR EACH ROW EXECUTE FUNCTION validate_internal_transfer_tenants();

-- Idem pour transfer_requests (resto → épicerie) et ingredient_epicerie_mappings
CREATE OR REPLACE FUNCTION validate_transfer_request_tenants() RETURNS trigger AS $$
DECLARE
    src_vertical VARCHAR(50);
    dst_vertical VARCHAR(50);
BEGIN
    SELECT vertical INTO src_vertical FROM tenants WHERE id = NEW.tenant_id;
    SELECT vertical INTO dst_vertical FROM tenants WHERE id = NEW.target_tenant_id;
    
    IF src_vertical != 'restaurant' OR dst_vertical != 'epicerie' THEN
        RAISE EXCEPTION 'Invalid TransferRequest vertical pair: % → %. Expected restaurant → epicerie.',
            src_vertical, dst_vertical;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_transfer_request_tenants_validate
    BEFORE INSERT OR UPDATE ON transfer_requests
    FOR EACH ROW EXECUTE FUNCTION validate_transfer_request_tenants();

-- IngredientEpicerieMapping : produit_id doit appartenir au tenant épicerie jumelé
CREATE OR REPLACE FUNCTION validate_ingredient_mapping_tenant() RETURNS trigger AS $$
DECLARE
    produit_tenant_id BIGINT;
    expected_epicerie_tenant_id BIGINT;
BEGIN
    SELECT tenant_id INTO produit_tenant_id FROM epicerie_produits WHERE id = NEW.produit_id;
    
    SELECT (settings->>'epicerie_tenant_id')::bigint INTO expected_epicerie_tenant_id
    FROM tenants WHERE id = NEW.tenant_id;
    
    IF produit_tenant_id IS DISTINCT FROM expected_epicerie_tenant_id THEN
        RAISE EXCEPTION 'IngredientMapping: produit_id % belongs to tenant %, expected % (épicerie jumelée du resto %)',
            NEW.produit_id, produit_tenant_id, expected_epicerie_tenant_id, NEW.tenant_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ingredient_mapping_tenant_validate
    BEFORE INSERT OR UPDATE ON ingredient_epicerie_mappings
    FOR EACH ROW EXECUTE FUNCTION validate_ingredient_mapping_tenant();
```

### 14.4 Trigger cycle prevention `categories.parent_id` (F493)

```sql
CREATE OR REPLACE FUNCTION prevent_category_cycle() RETURNS trigger AS $$
DECLARE
    visited BIGINT[];
    current_id BIGINT;
    depth_count INTEGER;
BEGIN
    IF NEW.parent_id IS NULL THEN
        NEW.depth := 0;
        RETURN NEW;
    END IF;
    
    visited := ARRAY[NEW.id];
    current_id := NEW.parent_id;
    depth_count := 0;
    
    WHILE current_id IS NOT NULL AND depth_count < 10 LOOP
        IF current_id = ANY(visited) THEN
            RAISE EXCEPTION 'Category cycle detected: % is ancestor of itself via %', NEW.id, current_id;
        END IF;
        
        visited := array_append(visited, current_id);
        depth_count := depth_count + 1;
        
        SELECT parent_id INTO current_id FROM categories WHERE id = current_id;
    END LOOP;
    
    -- Set depth
    NEW.depth := depth_count;
    
    IF NEW.depth > 5 THEN
        RAISE EXCEPTION 'Category depth % exceeds max 5', NEW.depth;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_categories_cycle_prevent
    BEFORE INSERT OR UPDATE OF parent_id ON categories
    FOR EACH ROW EXECUTE FUNCTION prevent_category_cycle();
```

### 14.5 Trigger CHECK qty SupplierOrderReceiptLine (Bloc 4 §4.2.9)

```sql
ALTER TABLE supplier_order_receipt_lines
    ADD CONSTRAINT ck_qty_consistency
    CHECK (qty_received + qty_damaged + qty_missing <= qty_ordered_for_line);
```

### 14.6 Trigger sync stock après supplier receipt (Bloc 4 §4.2.9)

```sql
CREATE OR REPLACE FUNCTION sync_stock_from_supplier_receipt() RETURNS trigger AS $$
DECLARE
    movement_id BIGINT;
    i INTEGER;
BEGIN
    -- 1. Crée inventory_movement type='supplier_receipt'
    INSERT INTO inventory_movements (
        tenant_id, type, status, scheduled_date, actual_date,
        related_entity_type, related_entity_id, created_at
    ) VALUES (
        NEW.tenant_id, 'supplier_receipt', 'completed', now(), now(),
        'SupplierOrderReceipt', NEW.id, now()
    ) RETURNING id INTO movement_id;
    
    -- 2. Insert stock_items (qty_received en 'available')
    FOR i IN 1..NEW.qty_received LOOP
        INSERT INTO stock_items (tenant_id, product_id, status, source_movement_id, created_at)
        VALUES (NEW.tenant_id, NEW.product_id, 'available'::stock_item_status, movement_id, now());
    END LOOP;
    
    -- 3. Insert stock_items (qty_damaged en 'damaged')
    FOR i IN 1..NEW.qty_damaged LOOP
        INSERT INTO stock_items (tenant_id, product_id, status, source_movement_id, created_at)
        VALUES (NEW.tenant_id, NEW.product_id, 'damaged'::stock_item_status, movement_id, now());
    END LOOP;
    
    -- 4. Outbox event SupplierReceiptCompleted
    INSERT INTO outbox_events (aggregate_type, aggregate_id, event_type, payload, tenant_id, actor_type, created_at)
    VALUES ('SupplierOrderReceipt', NEW.id, 'SupplierReceiptCompleted',
            jsonb_build_object('movement_id', movement_id, 'qty_received', NEW.qty_received, 'qty_damaged', NEW.qty_damaged),
            NEW.tenant_id, 'system', now());
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_supplier_receipt_sync_stock
    AFTER INSERT ON supplier_order_receipt_lines
    FOR EACH ROW EXECUTE FUNCTION sync_stock_from_supplier_receipt();
```

### 14.7 Trigger refresh `product_stock_view` debounced

```sql
-- Stratégie : marquer "dirty" via Redis (via NOTIFY) + worker refresh debounced 5s
CREATE OR REPLACE FUNCTION notify_stock_view_refresh() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('stock_view_dirty', json_build_object(
        'tenant_id', COALESCE(NEW.tenant_id, OLD.tenant_id),
        'product_id', COALESCE(NEW.product_id, OLD.product_id)
    )::text);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_stock_items_notify_view
    AFTER INSERT OR UPDATE OR DELETE ON stock_items
    FOR EACH ROW EXECUTE FUNCTION notify_stock_view_refresh();

-- Worker (Python, app/tasks/stock.py) écoute NOTIFY + acquiert Redis lock 5s + REFRESH MATERIALIZED VIEW CONCURRENTLY
```

---

## §15 — Row-Level Security (Bloc 1 Q2=A)

### 15.1 RLS sur tables tenant-scoped

```sql
-- Pattern : enable RLS + policy USING (tenant_id = current_setting('app.current_tenant_id')::bigint)

ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_customers ON customers
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);

ALTER TABLE products ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_products ON products
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);

ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_categories ON categories
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);

ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_reservations ON reservations
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_invoices ON invoices
    USING (tenant_id = current_setting('app.current_tenant_id', true)::bigint);

-- ... répliqué sur ~50 tables tenant-scoped
-- Liste exhaustive : toute table avec colonne `tenant_id` doit avoir RLS enabled
```

### 15.2 Bypass RLS pour superadmin DEVUP

```sql
-- Le rôle DB applicatif normal respecte RLS
-- Le rôle superadmin (utilisé pour migrations Alembic + admin/devup endpoints) bypass RLS
CREATE ROLE devup_app_role NOINHERIT LOGIN;
CREATE ROLE devup_superadmin_role NOINHERIT LOGIN BYPASSRLS;

-- Application : pool connections par défaut sur devup_app_role
-- Connections superadmin (SET LOCAL ROLE devup_superadmin_role) pour endpoints /admin/devup/*
```

### 15.3 Setting tenant_id helper

```sql
-- Bloc 1 RLSMiddleware : SET LOCAL app.current_tenant_id avant chaque requête HTTP
-- Pattern :
--   SET LOCAL app.current_tenant_id = '42';
--   SET LOCAL app.actor_account_id = '7';

-- Vérification à l'instanciation de connexion (ou via middleware) :
CREATE OR REPLACE FUNCTION assert_tenant_context_set() RETURNS void AS $$
BEGIN
    IF current_setting('app.current_tenant_id', true) IS NULL OR current_setting('app.current_tenant_id', true) = '' THEN
        RAISE EXCEPTION 'app.current_tenant_id not set in session — RLS would expose all tenants';
    END IF;
END;
$$ LANGUAGE plpgsql;
```

---

## Récapitulatif tables nouvelles ou modifiées

### Nouvelles tables (12)

1. `verticals`
2. `outbox_events`
3. `auth_factors`
4. `auth_vertical_scopes`
5. `access_reviews`
6. `points_ledger` (si pas existant) / refondu
7. `revenue_ledger` (si pas existant) / refondu
8. `payment_ledger` (si pas existant) / refondu
9. `notification_log`
10. `feature_flag_tenants`
11. `feature_flag_history`
12. `categorie_produit_seed`
13. `catalogue_produit_price_history`
14. `fsm_transitions`

### Tables modifiées (≥20)

- `tenants` (+10 colonnes Bloc 7)
- `customers` (+6 colonnes)
- `categories` (+4 colonnes, drop brand_code)
- `products` (+2 colonnes, drop 5 colonnes)
- `bundle_items` (+1 colonne)
- `stock_items` (status → ENUM)
- `invoices` (+5 colonnes e-invoicing, UNIQUE per-tenant)
- `invoice_lines` (+ tva_rate_snapshot)
- `pricing_rules` (discount_pct INTEGER → NUMERIC, ENUMs)
- `audit_logs` (+5 colonnes HMAC chain + PII encrypted)
- `notifications` (account_id FK + Mapped + PII)
- `feature_flags` (drop ARRAY target_tenants)
- `categorie_produits` (+ tenant_id NOT NULL)
- `catalogue_produits` (+ tenant_id, categorie_id FK)
- `etl_correction_history` (+ tenant_id)
- `etl_imports` (+ schema_version, ECHEC + AWAITING_VENDOR_MATCH)
- `relances` (+ email_send_error)
- `supplier_order_receipt_lines` (CHECK qty)
- `inventory_movements` (event_id FK)
- `restaurant_*_lines` (+ tva_rate_snapshot)

### Triggers (15+)

1. Ledger immutability × 6 tables
2. Invoice immutability post-emission
3. FSM transition guard générique × ~13 tables
4. Cross-tenant validation × 3 (InternalTransfer, TransferRequest, IngredientMapping)
5. Category cycle prevention + depth
6. Supplier receipt → stock_items sync
7. Stock view refresh notify
8. Feature flag history capture

### Views (1)

- `product_stock_view` (matérialisée)

### ENUMs PostgreSQL natifs (5)

- `stock_item_status`
- `item_condition`
- `pricing_rule_type`
- `pricing_applies_to`
- `audit_entity_type`

### Extensions PostgreSQL requises

- `pg_trgm` (recherche trigram customers/products)
- `citext` (Customer.email case-insensitive — déjà présent)

---

## §16 — Suppliers + Vente fiscal + Deposit immutable (vague 6 — sprint B3.S7)

> **Contexte** : Audit cohérence vague 6 a révélé que les modules `26-supplier`, `22-vente-directe`, `20-deposit`, `24-evenements-incidents` ont leurs frictions P0/P1 documentées en Phase 1 mais aucun DDL Phase 3 ne les adresse. Ce §16 comble le gap (planifié sprint B3.S7).

### 16.1 `suppliers` — UNIQUE per-tenant + CHECK status (V6-P0-03 F826)

```sql
ALTER TABLE suppliers
    ADD CONSTRAINT uq_suppliers_tenant_name UNIQUE (tenant_id, name);

ALTER TABLE suppliers ADD CONSTRAINT ck_suppliers_status_valid
    CHECK (status IN ('active', 'suspended', 'archived'));

COMMENT ON CONSTRAINT uq_suppliers_tenant_name ON suppliers IS
    'V6-P0-03 (F826) — empêche doublons fournisseurs silencieux par tenant.';
```

### 16.2 `supplier_orders` — UNIQUE reference + CHECK status + qty guard (V6-P0-04 F827/F828)

```sql
ALTER TABLE supplier_orders
    ADD CONSTRAINT uq_supplier_orders_tenant_reference UNIQUE (tenant_id, reference);

ALTER TABLE supplier_orders ADD CONSTRAINT ck_supplier_orders_status_valid
    CHECK (status IN ('draft', 'confirmed', 'partially_received', 'received', 'cancelled'));

-- F829 : qty_received <= qty_ordered guard sur receipt_lines
ALTER TABLE supplier_order_receipt_lines ADD CONSTRAINT ck_receipt_qty_within_order
    CHECK (qty_received <= qty_ordered);

COMMENT ON CONSTRAINT uq_supplier_orders_tenant_reference ON supplier_orders IS
    'V6-P0-04 (F827) — empêche réutilisation référence commande per-tenant.';
```

### 16.3 `vente_lines` — `tva_rate_snapshot` (V6-P0-02 F728 — non-conformité fiscale CGI L.441-3)

```sql
-- Migration step-by-step — vague 6 V6-P0-02
-- Étape 1 : ajouter colonne nullable
ALTER TABLE vente_lines ADD COLUMN tva_rate_snapshot NUMERIC(5,4);

-- Étape 2 : backfill depuis products.tva_rate ou tenant.settings.default_tva_rate
UPDATE vente_lines vl SET tva_rate_snapshot = COALESCE(
    (SELECT p.tva_rate_override FROM products p WHERE p.id = vl.product_id),
    (SELECT (t.settings->>'default_tva_rate')::numeric FROM tenants t
     JOIN ventes v ON v.tenant_id = t.id WHERE v.id = vl.vente_id),
    0.20  -- Fallback FR strict
)
WHERE tva_rate_snapshot IS NULL;

-- Étape 3 : NOT NULL après backfill
ALTER TABLE vente_lines ALTER COLUMN tva_rate_snapshot SET NOT NULL;

ALTER TABLE vente_lines ADD CONSTRAINT ck_vente_lines_tva_rate_range
    CHECK (tva_rate_snapshot >= 0 AND tva_rate_snapshot <= 1);

-- F739 — CHECK total ligne == subtotal_cents + tva_cents (cohérence comptable)
-- Contrainte stockée mais calcul Python car pg_check ne supporte pas les calculs cross-row.
-- À vérifier en service-level + invariant CI.

COMMENT ON COLUMN vente_lines.tva_rate_snapshot IS
    'V6-P0-02 (F728) — taux TVA capturé à la vente (immutable). Non-conformité CGI L.441-3 si absent.';
```

### 16.4 `deposits` — `amount_cents` immutable post-création (V6-P1-01 F675)

```sql
-- Trigger immutability spécifique sur deposits.amount_cents
CREATE OR REPLACE FUNCTION trg_deposits_amount_immutable_fn()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.amount_cents IS DISTINCT FROM NEW.amount_cents THEN
        RAISE EXCEPTION 'deposits.amount_cents is immutable post-creation (V6-P1-01 F675). '
                        'Use a CreditNote workflow to compensate.'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_deposits_amount_immutable
    BEFORE UPDATE ON deposits
    FOR EACH ROW
    EXECUTE FUNCTION trg_deposits_amount_immutable_fn();

COMMENT ON TRIGGER trg_deposits_amount_immutable ON deposits IS
    'V6-P1-01 (F675) — empêche modification du montant caution après encaissement (litige juridique).';
```

### 16.5 `evenements` — UNIQUE reference per-tenant (V6-P1-02 F767)

```sql
ALTER TABLE evenements
    ADD CONSTRAINT uq_evenements_tenant_reference UNIQUE (tenant_id, reference);

-- F768 — CHECK status valid
ALTER TABLE evenements ADD CONSTRAINT ck_evenements_status_valid
    CHECK (status IN ('planned', 'confirmed', 'in_progress', 'completed', 'cancelled'));

COMMENT ON CONSTRAINT uq_evenements_tenant_reference ON evenements IS
    'V6-P1-02 (F767) — empêche collision référence événement per-tenant (documents externes).';
```

### 16.6 Migrations associées

Cf. `51-alembic-migrations.md` index pour les revisions :
- `e3f4a5b6c7d8` `2026_07_15_supplier_constraints.py` (B3.S7)
- `e3f4a5b6c7d9` `2026_07_15_vente_lines_tva_snapshot.py` (B3.S7)
- `e3f4a5b6c7da` `2026_07_15_deposits_immutable_trigger.py` (B3.S7)
- `e3f4a5b6c7db` `2026_07_15_evenements_unique_reference.py` (B3.S7)

---

## Validation DDL

**Avant déploiement migration prod**, exécuter sur staging :

```bash
# 1. Apply DDL complet
psql $STAGING_DB -f 50-sql-schema.md.extracted.sql

# 2. Tests d'invariant
python tools/check_ledger_immutable_triggers.py
python tools/check_fsm_transitions_present.py
python tools/check_rls_enabled_on_tenant_tables.py

# 3. Tests E2E
pytest tests/integration/migrations/

# 4. Verify pas de régression perf
python tools/benchmark_queries.py --before-migration baseline.json
```

Cf. `54-ci-invariants.md` pour le détail des scripts.
