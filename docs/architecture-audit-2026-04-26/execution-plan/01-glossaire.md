# Glossaire DEVUP

> Ce glossaire est **normatif**. Les termes ci-dessous sont les seuls autorisés dans le code, les commits, les tickets, et les commentaires. Toute autre formulation = drift sémantique = correction en review.

## A

### **`Account`**
Identité globale d'un utilisateur **cross-tenant**. Modèle SQLAlchemy : `app/models/account.py`.
- Porte : `email` (CITEXT UNIQUE), `hashed_password`, `first_name`, `last_name`, `is_active`, `password_change_required`.
- **NE porte PAS** : `tenant_id` (cross-tenant), `address`, `postal_code` (migrés vers `Customer` Bloc 2 Q7=B), `pin_hash` (migré vers `auth_factor` Bloc 2 Q6=B).
- 1 Account peut avoir N `TenantMembership` (cf. ci-dessous).

### **`auth_factor`** (Bloc 2 Q6=B)
Table unique remplaçant `MFADevice`, `WebAuthnCredential`, `TrustedDevice`.
- Schema : `(membership_id FK, type ENUM('TOTP','FIDO','PIN'), encrypted_secret, credential_id, sign_count, pin_hash, ...)`
- Lié à `TenantMembership` (pas à `Account` directement) — permet à un user multi-tenant d'avoir des facteurs différents par tenant.

### **`auth_vertical_scopes`** (Bloc 2 §2.3, renommé Bloc 7)
Table M:N qui restreint quels scopes RBAC sont attribuables à un vertical.
- Ex : scope `restaurant:write` n'est attribuable qu'à un user dont le tenant a `vertical='restaurant'`.
- Filtrée à l'émission du JWT (`TokenService.issue_tokens`).
- **Ancien nom** (avant Bloc 7) : `auth_app_scopes`. Migration B7.S1.

### **`app_code`**
Identifiant **unique d'instance tenant** (string, ex: `'marveline'`, `'splendid'`, `'massacorp_epi'`, `'massacorp_resto'`, `'atdt'`, `'client_x_resto'`).
- Pattern : `^[a-z][a-z0-9_]+$` (regex CHECK).
- UNIQUE sur la table `tenants`.
- **Différent de `vertical`** : 2 tenants peuvent partager le même `vertical` (ex: `marveline` et `splendid` ont tous deux `vertical='location'`) mais ont des `app_code` distincts.

### **AppSelector**
Page racine `/` post-login (frontend). Liste les `TenantMembership` du user, groupés par `vertical`. Header DEVUP universel pour les superadmins, white-label per-tenant côté UI client.

## B

### **`brand_code`** ⚠️ **OBSOLÈTE post Bloc 7 Q43=B**
Concept abandonné. Avant Bloc 7, désignait un sous-marquage intra-tenant (Marveline + Splendid sous un même tenant). Q43=B verrouille **2 tenants distincts** → drop intégral des colonnes `Product.brand_code`, `Category.brand_code`, `Bundle.brand_code`, `ProductCollection.brand_code`, `Tenant.is_multi_brand`, header `X-Brand-Code`. Migration Sprint B7.S2.

## C

### **CITE_SPEC**
Action protocolaire (skill `senior-protocol`) qui déverrouille `START_CODING(component)`. Exige une citation verbatim d'une section de spec lue intégralement.

### **CMP / PMP** (Coût Moyen Pondéré, Q13=A verrouillée)
Méthode de valorisation stock épicerie. Recalcul à chaque entrée stock :
```
WAC_new = (qty_old × WAC_old + qty_in × cost_in) / (qty_old + qty_in)
```
Stocké dans `stock_management.weighted_avg_cost_cents`.

### **Conversion Devis → Réservation atomique**
Flow critique Bloc 3 §3.2.6. Une seule TX pour : reserve_stock + créer Reservation(`status='confirmed'`) + émettre Invoice(`status='emitted'`, Q12=A) + outbox audit. Lock `FOR UPDATE` sur le devis. Si une étape échoue → rollback intégral.

## D

### **DEVUP**
Société de développement (SIRET 99903696500013). Opérateur SaaS. **N'EST PAS** Marveline. Marveline est un **client** de DEVUP (un tenant `vertical='location'`).

### **DLQ (Dead Letter Queue)**
Q42=B verrouillée → DLQ **native RabbitMQ** via `x-dead-letter-exchange`. Reçoit automatiquement les messages morts (NACK + max_retries épuisés). Métrique Prometheus `celery_dlq_total{task_name}`. UI RabbitMQ Management pour replay manuel admin.

## F

### **FSM (Finite State Machine)**
Pattern canonique Bloc 3 §3.2.1. Classe helper `app/core/fsm.py` :
```python
class FSM(Generic[State]):
    transitions: dict[State, set[State]]  # défini par sous-classe
    @classmethod
    def assert_transition(cls, from_, to): ...
    @classmethod
    @asynccontextmanager
    async def transit(cls, db, entity, *, from_, to, actor_id, payload): ...
```
Sous-classes : `DevisFSM`, `ReservationFSM`, `DepositFSM`, `InvoiceFSM`, `VenteFSM`, `RelanceFSM`, `EpicerieVenteFSM`, `CommandeRestaurantFSM`, `LigneCommandeFSM`, `EtlImportFSM`, `EtlConflictFSM`, `InternalTransferFSM`, `TransferRequestFSM`, `StockItemFSM`.
Matrice + CHECK constraint DB + trigger BEFORE UPDATE qui valide `OLD.status → NEW.status`.

### **Friction (FXXX)**
Identifiant unique global d'une friction documentée dans l'audit code (modules 01-35). Numérotation F1 à F1154. Référencée dans `architecture-cible.md` et tickets sprint.

## L

### **LedgerEntryMixin** (Bloc 3 §3.2.15)
Mixin SQLAlchemy partagé par `PointsLedger`, `RevenueLedger`, `PaymentLedger`. Convention : append-only, `balance_after` dénormalisé, advisory_lock_key dérivé de `member_id`/`customer_id`. Trigger DB `BEFORE UPDATE/DELETE → RAISE EXCEPTION`.

## M

### **`Membership`** = **`TenantMembership`**
Lien N:N entre `Account` et `Tenant`. Schema : `(account_id FK, tenant_id FK, role ENUM(6), status ENUM('active','suspended','revoked'), created_at, ...)`.
- Un Account peut avoir plusieurs Memberships (un par tenant accessible).
- 6 rôles globaux fixes (Q9=A) : `superadmin` (DEVUP ops), `admin` (tenant), `manager`, `staff`, `viewer`, `api`.
- L'AppSelector frontend liste les Memberships d'un user pour qu'il choisisse son tenant courant.

### **mTLS** (Q40=B verrouillée)
Mutual TLS — les deux parties (client + serveur) présentent un certificat X.509. Utilisé pour `/metrics` (Prometheus scraper avec client cert), pour authentifier le scraper sans Basic auth ni IP whitelist. Implémentation via service mesh (Istio/Linkerd) ou nginx-ingress mTLS.

## O

### **Outbox pattern** (Bloc 1 Q4=A)
Pattern transactionnel pour audit + events :
1. Insert dans `outbox` table dans la même TX que l'action métier.
2. Worker async `outbox_dispatcher_task` lit `outbox` et publie vers `audit_log`, RabbitMQ events, etc.
3. Garantie : si la TX métier rollback, l'event aussi (pas de perte silencieuse contraire à l'AuditMiddleware actuel F1000).

## P

### **`PricingEngine`** (renommé Bloc 7, ex-`PricingService`)
Classe canonique `app/services/pricing/engine.py`. Fusion de l'actuel `services/pricing_engine.py` + endpoint `/pricing/simulate`. Cumul additif des règles (Q25=A). Source unique pour Devis, Reservation, Vente.
- `discount_pct: Numeric(5,4)` (ex: `0.10` pour 10%) — convention unique, plus de `÷100` ni `÷10000`.
- Snapshot complet retourné (TVA, discount, formule) capturé sur la ligne.

### **`Principal`**
Protocol Python remplaçant `UserCompat` (supprimé Bloc 1 §1.2.1).
```python
class Principal(Protocol):
    account_id: int
    active_tenant_id: int
    membership_role: str
    scopes: frozenset[str]
```
Implémenté par `Account` (login user) ou `ApiKeyClient` (API key auth).

## R

### **RBAC v3 (Scope enum)**
Système d'autorisation actuel. 62 scopes (cf. `architecture-cible.md` §2.3 catalogue Scopes v3). Plus de Permission v2 (40 valeurs supprimées Bloc 2). Format : `domain:action` (ex: `customers:read`, `products:write`, `audit:read_pii`).

### **RLS (Row-Level Security)** (Bloc 1 Q2=A)
Filtre tenant enforced **DB-side** :
```sql
CREATE POLICY tenant_isolation ON products
USING (tenant_id = current_setting('app.current_tenant_id')::bigint);
```
Repository Python qui oublie le filtre tenant = SELECT vide, plus jamais de leak cross-tenant via repo bug.

## T

### **`Tenant`**
Une instance client hébergée sur DEVUP. Schema (Bloc 7 §7.2) :
```python
class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    id: Mapped[int]
    app_code: Mapped[str]               # UNIQUE — identifiant instance
    vertical: Mapped[str]               # FK verticals.code (ENUM extensible)
    country_code: Mapped[str] = 'FR'    # Q3=B France strict
    legal_name, siret, vat_number
    # White-label per-tenant (Q44=A+C)
    brand_display_name, brand_logo_url, brand_email_from,
    brand_dkim_domain, brand_primary_color
    settings: Mapped[dict]              # JSONB tenant_settings
    peppol_id, chorus_pro_id            # e-invoicing prep (Q19=A)
```

### **`TenantMembership`** → cf. **`Membership`**

### **`tenant_settings`**
Champ JSONB sur `Tenant.settings` pour les configurations runtime per-tenant. Validé par schema Pydantic. Contient :
- `default_tva_rate`, `default_deposit_pct` (Q14=C)
- `rfm_thresholds` (Q27=B) — validé par schema `RFMThresholds`
- `devis_default_expiry_days` (Q17=D, default 30)
- `postmark_server_token` (chiffré KMS, Q18=A)
- `epicerie_tenant_id` (FK pour resto liés à un épi, cf. `IngredientEpicerieMapping`)

### **`tva_rate_snapshot`** (Bloc 3 TR-3, §3.2.3)
Colonne `Numeric(5,4) NOT NULL` sur **toutes les lignes facturables** (DevisLine, ReservationLine, VenteLine, InvoiceLine, EpicerieVenteLigne, LigneCommandeRestaurant). Capture la TVA à l'émission de la ligne. Élimine le fallback `0.20` hardcoded.

## V

### **`Vertical`**
Modèle métier extensible. Énuméré dans la table `verticals` (Bloc 7 §2.2).
- `'location'` — événementiel/vaisselle/mobilier (tenants : Marveline, Splendid)
- `'epicerie'` — POS épicerie alimentaire (tenants : MassaCorp Épi, futurs)
- `'restaurant'` — cuisine + commandes + tables (tenants : MassaCorp Resto, L'Incontournable, futurs)
- `'autour_de_table'` — nouveau modèle prévu (catalogue + packs spécifiques)
- … (ajout = 1 migration + 1 module React, pas de hardcode)

Différent de `app_code`, qui désigne une **instance** de vertical (ex: `marveline` est une instance de `location`).

## W

### **White-label per-tenant** (Q44=A+C)
Chaque tenant configure son branding (logo, couleur primaire, email_from, DKIM domain) via colonnes `Tenant.brand_*`. Côté UI client, le tenant voit son branding en first-class. Footer "Powered by DEVUP" discret. Côté admin DEVUP / AppSelector, header DEVUP universel.

---

## Termes interdits / dépréciés

| Terme | Remplacement | Raison |
|---|---|---|
| ~~`UserCompat`~~ | `Principal` Protocol ou `(Account, Membership)` | Supprimé Bloc 1 §1.2.1 |
| ~~`brand_code`~~ (Catalogue) | Aucun (catalogue strictement per-tenant) | Q43=B obsolète |
| ~~`is_multi_brand`~~ | Aucun | Q43=B obsolète |
| ~~`X-Brand-Code`~~ (header) | Aucun | Q43=B obsolète |
| ~~`auth_app_scopes`~~ | `auth_vertical_scopes` | Renommé Bloc 7 |
| ~~`PricingService`~~ | `PricingEngine` | Cohérent code source `services/pricing_engine.py` |
| ~~`Permission`~~ enum v2 | `Scope` enum v3 | Supprimé Bloc 2 §2.3 |
| ~~`MFADevice`~~, ~~`WebAuthnCredential`~~, ~~`TrustedDevice`~~ | `auth_factor` | Unifié Bloc 2 Q6=B |
| ~~`tenant.app_code IN ('marveline', 'epicerie', 'restaurant', 'lesplendid')`~~ CHECK enum strict | UNIQUE + regex `^[a-z][a-z0-9_]+$` + FK `verticals.code` | Bloc 7 |
| ~~`quantite_par_portion`~~ | `quantite_par_batch` | Bug F906 — l'attribut n'existe pas dans `RecetteTypePreparation` |
| ~~`smtplib.SMTP()` sync~~ | `EmailGateway` async (Postmark) | Bloc 6 §6.2.1 |
| ~~`AuditMiddleware._audit_mutation`~~ | Service-level + `@audit_action` decorator | Bloc 6 §6.2.3 |
| ~~`÷ 100` / `÷ 10000` discount_pct~~ | `Numeric(5,4)` direct (ex: `0.10`) | Bloc 4 §4.2.5 |
| ~~Multi-pays printer~~ | FR strict EUR + cp858 hardcoded | Q41=B |
| ~~Basic auth `/metrics`~~ | mTLS pur via service mesh | Q40=B |
| ~~DLQ Redis simple~~ | DLQ AMQP RabbitMQ via `x-dead-letter-exchange` | Q42=B |
| ~~Multi-brand France maintenu~~ | Multi-tenant France maintenu | Q43=B |
| ~~"4 brands"~~ | "verticals extensibles" | Bloc 7 |

---

## Convention de citation

Dans les commits, tickets, PR descriptions :
- ✅ `fix(B5.S1): F906 marmite — quantite_par_portion → quantite_par_batch`
- ✅ `feat(B3.S2): FSM helper class + DB triggers immutability`
- ❌ `fix bug` (pas de référence FXXX ou sprint)
- ❌ `multi-brand identity` (terme obsolète Q43=B)
