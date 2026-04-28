# Module 07 — Constants

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/constants/__init__.py` | 193 | Re-export ~70 symboles depuis tous les sous-modules |
| `app/constants/business.py` | 564 | Enums métier + règles CGV Marveline hardcodées |
| `app/constants/errors.py` | 446 | `ErrorMessages` (200+ messages) + `HTTPStatusMessages` |
| `app/constants/security.py` | 401 | `SecurityHeaders`, `RedisKeys`, `BruteForceThresholds`, `CredentialStuffingThresholds`, `Argon2Params`, `PasswordPolicy`, `SessionConfig`, `MFAConfig`, `RateLimitScope` |
| `app/constants/loyalty.py` | 301 | Enums + constantes 2 programmes loyalty (L'Incontournable, Marveline) |
| `app/constants/http.py` | 112 | `HTTPMethods`, `PublicEndpoints`, `AuthEndpoints`, `HealthEndpoints`, `PASSWORD_CHANGE_ALLOWED` |
| `app/constants/approvisionnement.py` | 111 | Enums ETL alimentaire + seuils Jaro-Winkler |
| `app/constants/limits.py` | 96 | `Limits` (pagination, tokens, password reset, business) |
| `app/constants/_template_domaine.py` | 82 | Template pour créer un nouveau domaine de constantes |
| `app/constants/metrics.py` | 24 | (déjà couvert module 03 — F87, F112) `PATH_NORMALIZATION_PATTERNS` |

**Total** : 2 330 LoC.

**Dépend de** : `enum.Enum` standard library uniquement (pure constantes).

**Dépendu par** : tous les modules du codebase (modèles, schémas, services, repositories, middlewares, endpoints).

---

## 2. Lecture par fichier

### 2.1 `business.py` (564 LoC)

#### Enums métier (16)
- `ProductCategory` (lignes 14-44) : **20 catégories Marveline** (`assiettes, bancs, candy_bar, chaises, couverts, decorations, housses, machines, mange_debout, mobilier, nappages, nappes, porcelaine, serviettes, tables, vaisselle, vaisselle_service, vaisselle_enfants, verres, accessoires_transport`).
- `ProductCondition` (47-59) : 4 valeurs (NEUF, BON, USE, HORS_SERVICE).
- `CustomerType` (62-74) : 4 valeurs.
- `ReservationStatus` (77-101) : 10 valeurs.
- `InvoiceStatus` (104-122) : 5 valeurs.
- `DepositStatus` (125-140) : 3 valeurs.
- `PaymentMethod` (143-155) : 4 valeurs.
- `UserRole` (158-184) : **7 valeurs** dont `ADMIN = "admin"` legacy (commentaire ligne 181-184 : "Migration Alembic convertira admin → tenant_admin").
- `TokenType` (187-197) : ACCESS, REFRESH.
- `MovementType` (203-213) : DEPARTURE, RETURN.
- `MovementStatus` (216-234) : 5 valeurs.
- `DeliveryMethod` (237-247) : 3 valeurs.
- `InspectionStatus` (250-261) : 4 valeurs.
- `ItemCondition` (264-275) : 4 valeurs.
- `ProductColor` (278-298) : **8 couleurs Marveline** (BLANC, IVOIRE, BORDEAUX, NOIR, ROUGE, VERT_AMANDE, VERT_SAPIN, TAUPE).
- `ProductGamme` (301-322) : **6 gammes Marveline** (CLASSIQUE, ELEGANCE, OPEN_UP, PRESTIGE, VINTAGE, BOIS).
- `StockItemStatus` (325-348) : 6 valeurs.
- `DevisStatus` (392-416) : 9 valeurs.
- `VenteStatus` (419-438) : 7 valeurs.
- `EventStatus` (441-462) : 8 valeurs.
- `ReservationDeliveryMethod` (465-475) : 3 valeurs (SELF, CARRIER, PICKUP).
- `ContainerType` (483-495) : 5 valeurs (BAC, CARTON, PALETTE, HOUSSE, CAISSE).
- `RelanceStatus` (498-512) : 3 valeurs.

#### Constantes module-level — règles métier Marveline (lignes 355-389, 478-480)
Source explicite : commentaire ligne 356 « CGV et FAQ marveline.fr (relevé 2026-02-17) »
- `DEPOSIT_RATE: float = 3.0`
- `SELFIE_BOOTH_DEPOSIT_CENTS: int = 300_000`
- `ADVANCE_PAYMENT_PERCENT: int = 40`
- `ADVANCE_DUE_DAYS: int = 7`
- `BALANCE_DUE_DAYS_BEFORE_EVENT: int = 7`
- `LATE_RETURN_PENALTY_RATE: float = 0.20`
- `LINEN_MIN_BOOKING_DAYS: int = 90`
- `HOURLY_RATE_WEEKDAY_CENTS: int = 3_000` (30€)
- `HOURLY_RATE_WEEKEND_CENTS: int = 6_000` (60€)
- `TVA_RATE: float = 0.20`
- `LOW_STOCK_THRESHOLD: int = 5`
- `WEIGHT_SURCHARGE_THRESHOLD_GRAMS = 500_000` (500 kg)
- `WEIGHT_SURCHARGE_CENTS = 5000` (50€)
- `EVENT_TYPE_MIN_DAYS: dict[str, int]` (lignes 516-521) : `mariage:3, entreprise:2, anniversaire:1, autre:1`.
- `SYSTEM_TENANT_ID: int = 0` (ligne 352).

### 2.2 `errors.py` (446 LoC)

- `ErrorMessages` (8-423) : **200+ constantes string** organisées en 17 sections par status HTTP / domaine :
  - 404 (resources not found) : 50+ entrées.
  - 403 IAM v2 : 3.
  - 400 (validation/business) : ~100 (Products, Categories, Bundles, Variants, Reservations, Invoices, Credit notes, Payments, Deposits, Devis, Ventes, Movements, Stock, Damages, Events, Suppliers, Collections, Delivery zones, Formulas, Pricing, Customers, Relances, Images, Maintenance, Notifications, Generic).
  - 401/403 auth : 26.
  - 400/401 MFA : 12.
  - 400/401 password reset : 4.
  - 403 CSRF : 3.
  - 429/400 brute force : 3.
  - 429 rate limit : 1.
  - 500/503 internal : 5.
  - 400/403 tenant : 3.
  - 400/401 API keys : 4.
  - Feature flags : 2.
  - Sessions : 3.
  - Users : 3.
  - Loyalty : 14.
- `HTTPStatusMessages` (426-440) : 5 messages génériques.

#### Détails

- **Messages en anglais** majoritairement (commentaire ligne 4 : « All messages are in English. Frontend handles i18n/translation to French »).
- **Mais** : 3 messages en **français** :
  - Ligne 62 : `DEPARTURE_LINE_NOT_FOUND = "Ligne de départ inconnue"`.
  - Ligne 132-134 : `RESERVATION_ADVANCE_NOT_PAID = "Acompte non encaissé — impossible de livrer. ..."`.
  - Ligne 135-138 : `RESERVATION_SIGNATURE_REQUIRED = "Signature contractuelle manquante — impossible de livrer. ..."`.
- Template `{scope}` ligne 295 : `SCOPE_REQUIRED = "Required scope: {scope}"` — placeholder jamais formaté.

### 2.3 `security.py` (401 LoC)

#### Classes
- `SecurityHeaders` (13-62) : 16 constantes nom + 6 valeurs + `CSP_DEFAULT` block.
- `RedisKeys` (65-248) : ~30 préfixes string + 18 helpers `@staticmethod`. Mix de patterns :
  - Callables : `refresh_whitelist`, `access_blacklist`, `token_family`, `jti_meta`, `user_sessions_index`, `session`, `csrf_token`, `stepup`, `brute_force_user`, `brute_force_ip`, `brute_force_device`, `brute_force_pwd_change`, `totp_used`, `mfa_session`, `revoked_device`, `revoked_device_attempt`, `ws_ticket`, `reservation_counter`, `invoice_counter`, `rbac_scope_cache`, `rate_limit`.
  - Préfixes brut sans helper : `BRUTE_FORCE_LOCK`, `BRUTE_FORCE_ALERT`, `CREDENTIAL_STUFFING`, `CAPTCHA_REQUIRED`, `LOGIN_BLOCKED`, `PASSWORD_RESET_TOKEN`, `PASSWORD_RESET_RATE`, `DEGRADED_*`, `API_KEY_CACHE`, `FEATURE_FLAG_CACHE`.
- `BruteForceThresholds` (251-266) : 6 constantes (CAPTCHA_THRESHOLD=3, DELAY_THRESHOLD=5, ATTEMPT_WINDOW_SECONDS=900, BASE_DELAY_SECONDS=1, MAX_DELAY_SECONDS=30).
- `CredentialStuffingThresholds` (269-286) : 6 constantes (MINUTE_WINDOW_SECONDS=600, WARNING_THRESHOLD=50, CAPTCHA_THRESHOLD=200, BLOCK_THRESHOLD=500, CAPTCHA_TTL=1800, BLOCK_TTL=300).
- `Argon2Params` (289-304) : HASH_LENGTH=32, SALT_LENGTH=16, BCRYPT_PREFIX, ARGON2ID_PREFIX. Commentaire ligne 295-297 : « TIME_COST, MEMORY_COST et PARALLELISM sont définis dans config.py ».
- `PasswordPolicy` (307-322) : MIN_LENGTH=8, ADMIN_MIN_LENGTH=12, MAX_LENGTH=128, ELEVATED_ROLES=("admin", "manager").
- `SessionConfig` (325-334) : MAX_SESSIONS_PER_USER=5, SESSION_TTL_SECONDS=604800.
- `MFAConfig` (337-357) : 8 constantes incluant `ISSUER_NAME = "Marveline"` ligne 356.
- `RateLimitScope` enum (360-388) : 10 valeurs (4 communes + 4 epicerie/restaurant + 2 mutations/reads).

### 2.4 `loyalty.py` (301 LoC)

#### Enums (10)
- `LoyaltyProgramType` (15-23) : POINTS, TIERED_DISCOUNT.
- `LoyaltyTier` (28-45) : **5 valeurs des 2 programmes mélangés** : STANDARD, VIP (programme 1) + NOUVEAU, HABITUE, PRIVILEGIE (programme 2).
- `LedgerType` (50-64) : EARN, REDEEM, EXPIRE, ADJUST, BONUS.
- `LedgerSource` (67-81) : RESTAURANT, EPICERIE, REFERRAL, PROMO, WELCOME, MANUAL, FLASH.
- `RevenueLedgerType` (84-94) : PURCHASE, REFUND, ADJUST.
- `RewardTier` (99-111) : WELCOME, TIER_1, TIER_2, TIER_3.
- `RedemptionStatus` (114-122) : USED, REVOKED.
- `WalletPlatform` (127-131) : APPLE, GOOGLE.
- `WalletPassStatus` (134-138) : ACTIVE, INACTIVE.
- `FlashOfferTarget` (143-151) : ALL, VIP.
- `FlashOfferStatus` (154-164) : SCHEDULED, ACTIVE, ENDED.
- `LoyaltyNotifType` (169-177) : 6 valeurs.
- `NotifChannel` (180-185) : WALLET, SMS, EMAIL.

#### Constantes business L'Incontournable (lignes 188-235) — 12 constantes
- `POINTS_PER_EUR_RESTAURANT = 10`
- `POINTS_PER_EUR_EPICERIE = 5`
- `VIP_MULTIPLIER = 1.5`
- `VIP_THRESHOLD_POINTS_PER_YEAR = 3000`
- `VIP_GRACE_DAYS = 90`
- `POINTS_EXPIRY_MONTHS_EARNED = 12`
- `POINTS_EXPIRY_MONTHS_BONUS = 6`
- `REFERRAL_BONUS_POINTS = 200`
- `MAX_REFERRALS_PER_MEMBER = 3`
- `REWARD_TIER_1_COST = 500`
- `REWARD_TIER_2_COST = 1500`
- `REWARD_TIER_3_COST = 3000`
- `EXPIRY_WARNING_DAYS_FIRST = 14`
- `EXPIRY_WARNING_DAYS_SECOND = 3`
- `CHURN_RISK_MIN_DAYS = 21`
- `CHURN_RISK_MAX_DAYS = 35`

#### Constantes business Marveline (lignes 238-253) — 5 constantes
- `TIER_HABITUE_THRESHOLD_CENTS = 50_000` (500€)
- `TIER_PRIVILEGIE_THRESHOLD_CENTS = 200_000` (2000€)
- `DISCOUNT_HABITUE_PERCENT = 5`
- `DISCOUNT_PRIVILEGIE_PERCENT = 10`
- `REVENUE_WINDOW_MONTHS = 24`

### 2.5 `http.py` (112 LoC)

- `HTTPMethods` (10-35) : 7 méthodes + 2 frozensets (SAFE, UNSAFE).
- `PublicEndpoints` (38-56) : 6 endpoints + classmethod `all()` qui retourne un nouveau set.
- `AuthEndpoints` (59-83) : **17 routes hardcodées** (login, refresh, csrf, logout, mfa_verify, change_password, me + 6 V2 routes).
- `PASSWORD_CHANGE_ALLOWED` (87-92) : frozenset 4 entrées.
- `HealthEndpoints` (95-104) : BASE, READY, LIVE.

### 2.6 `limits.py` (96 LoC)

`Limits` classe agrégat avec 14 constantes :
- Pagination : `MAX_PAGE_SIZE=1000`, `DEFAULT_PAGE_SIZE=100`.
- Sécurité : `CSRF_TOKEN_MIN_LENGTH=32`, `PASSWORD_MIN_LENGTH=8`, `RSA_KEY_MIN_BITS=2048`.
- Rate limit : `REQUESTS_PER_MINUTE=100`, `RATE_LIMIT_WINDOW_SECONDS=60`.
- Tokens : `ACCESS_TOKEN_EXPIRE_SECONDS=900`, `REFRESH_TOKEN_EXPIRE_SECONDS=604800`, `MAX_SESSIONS_PER_USER=5`.
- Password reset : `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30`, `PASSWORD_RESET_MAX_PER_EMAIL=3`, `PASSWORD_RESET_WINDOW_MINUTES=15`, `PASSWORD_CHANGE_MAX_ATTEMPTS=3`, `PASSWORD_CHANGE_WINDOW_SECONDS=900`.
- Business : `RESERVATION_REFERENCE_PADDING=4`, `INVOICE_NUMBER_PADDING=4`.

### 2.7 `approvisionnement.py` (111 LoC)

- `SourceFournisseur` enum (8-21) : METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM (5 valeurs hardcodées).
- `TypeImportFournisseur` enum (24-35) : CSV_METRO, CSV_TAIYAT, MANUEL.
- `EtlStatutImport` enum (38-58) : 8 valeurs avec **mix anglais/français** (PENDING, RUNNING, PREVIEW, VALIDATED, REJECTED, **SUCCES, PARTIEL, ECHEC**).
- `EtlTypeConflit` enum (61-74) : EAN_COLLISION, DESIGNATION_PROCHE, CATEGORIE_INCONNUE.
- `EtlResolutionConflit` enum (77-87) : PENDING, MERGED, KEPT_SEPARATE.
- `UniteAchat` enum (90-103) : KG, L, PIECE, CARTON, BOITE, SACHET.
- `ETL_SEUIL_MATCH = 0.85`, `ETL_SEUIL_CONFLIT_ALERTE = 0.75` (lignes 110-111).

### 2.8 `__init__.py` (193 LoC)

Re-export massif : ~70 symboles dans `__all__`. Mélange Enums métier + règles business + messages + sécurité + HTTP + limites + métriques + loyalty (×30 entrées loyalty seules).

---

## 3. Frictions identifiées

(Numérotation continue — F195 commence après le module 06.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F195** | constants/business | **Constantes CGV Marveline hardcodées en module-level — toutes les apps en héritent** | `business.py:355-389` (block « RÈGLES MÉTIER MARVELINE.FR ») + `business.py:478-480` | Source explicite : commentaire ligne 356 « CGV et FAQ marveline.fr ». Constantes :<br>- `DEPOSIT_RATE = 3.0` (caution × 3)<br>- `SELFIE_BOOTH_DEPOSIT_CENTS = 300_000` (3000€ fixe)<br>- `ADVANCE_PAYMENT_PERCENT = 40`<br>- `ADVANCE_DUE_DAYS = 7`<br>- `BALANCE_DUE_DAYS_BEFORE_EVENT = 7`<br>- `LATE_RETURN_PENALTY_RATE = 0.20`<br>- `LINEN_MIN_BOOKING_DAYS = 90`<br>- `HOURLY_RATE_WEEKDAY_CENTS = 3_000`<br>- `HOURLY_RATE_WEEKEND_CENTS = 6_000`<br>- `LOW_STOCK_THRESHOLD = 5`<br>- `WEIGHT_SURCHARGE_THRESHOLD_GRAMS = 500_000`<br>- `WEIGHT_SURCHARGE_CENTS = 5000`<br>**Conséquence multi-tenant** : Splendid utilise les CGV Marveline (caution × 3, acompte 40%, etc.) — **impossible** de signer un contrat différent par tenant sans toucher au code. Pour un SaaS multi-brand, **toutes ces valeurs doivent être en `tenant_settings` overridable**, avec ces valeurs comme defaults pour Marveline. À fixer **avant** tout signing Splendid avec CGV différent. |
| **F196** | constants/business | **`TVA_RATE = 0.20` hardcodé global** | `business.py:385-386` | TVA 20% s'applique à la location (Marveline) mais :<br>- Épicerie : 5.5% (alimentation) ou 10% (restauration sur place).<br>- Restaurant : 10% pour consommation sur place, 5.5% pour à emporter.<br>**Calcul TVA faux pour 50% des apps**. À déplacer en `app/constants/tax.py` avec mapping par catégorie produit, ou en `tenant_settings.tva_rate` + `product.tva_rate` override. |
| **F197** | constants/loyalty | **2 programmes loyalty mélangés dans une seule enum + constantes globales** | `loyalty.py:28-45` (`LoyaltyTier` mélange STANDARD/VIP de l'Incontournable + NOUVEAU/HABITUE/PRIVILEGIE de Marveline) ; `loyalty.py:188-253` (constantes business des 2 programmes en module-level) | Conséquences :<br>(a) **Pas de typage par programme** : un member L'Incontournable peut avoir `tier=HABITUE` (palier Marveline) en DB sans erreur — bug latent.<br>(b) **Pour ajouter un 3ème programme** (ex: Splendid VIP avec seuil 5000 pts/an, Restaurant Splendid avec ratio 8 pts/€), édition du code Python + migration enum DB.<br>(c) Constantes hardcodées à 2 programmes — pas extensible.<br>**Architecture cible** : table `loyalty_program` (tenant-scoped) avec colonnes `points_per_eur_*`, `vip_threshold`, `tier_thresholds`, `reward_costs_json`. Tous les services lisent depuis là, pas depuis les constantes. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F198** | constants/business | **`ProductCategory` 20 catégories Marveline-only** | `business.py:14-44` | Catégories : `assiettes, bancs, candy_bar, chaises, couverts, decorations, ...`. Pour épicerie (denrées alimentaires : `boucherie, charcuterie, fromages, fruits_legumes, ...`) ou restaurant (plats : `entrees, plats, desserts, boissons, ...`), ces catégories ne s'appliquent pas. **L'enum est partagé entre tous les tenants** mais n'est valide que pour Marveline. Pour Splendid, un événementiel haut de gamme aura potentiellement d'autres catégories (`mobilier_lounge, scenographie, stands_buffet`).<br>**Architecture cible** : table `product_category` (tenant-scoped) avec colonne `slug` libre. L'enum disparaît, devient une référence string vers la table. Risque actuel : DB CHECK constraint sur `product.category IN (...)` couple chaque tenant à Marveline. |
| **F199** | constants/business | `ProductColor` (8 couleurs) et `ProductGamme` (6 valeurs) hardcodées Marveline | `business.py:278-298, 301-322` | Idem F198 — couplage Marveline. Splendid/épicerie/restaurant n'utilisent pas `VERT_AMANDE`, `VERT_SAPIN`, `TAUPE`, `OPEN_UP`, `PRESTIGE`, `BOIS`. À déplacer en `product_variant_attributes` table ou supprimer (lecture libre via `ProductVariant.color: str`). |
| **F200** | constants/business | `ContainerType`, `EVENT_TYPE_MIN_DAYS`, `ReservationDeliveryMethod` hardcodés Marveline | `business.py:483-495, 516-521, 465-475` | Logistique Marveline (BAC, CARTON, PALETTE, HOUSSE, CAISSE), types d'événements (mariage 3j, entreprise 2j…) — ne s'appliquent pas à épicerie ou restaurant. À déplacer. |
| **F201** | constants/business | **`UserRole` legacy `ADMIN = "admin"`** (avec commentaire « migration à venir ») | `business.py:181-184` | Migration "Alembic convertira admin → tenant_admin" annoncée, jamais faite. Code legacy continue d'utiliser `ADMIN`. Nouveau code utilise `TENANT_ADMIN`. Mix des 2 = source d'inconsistance. À planifier la migration ou supprimer la valeur legacy. |
| **F202** | constants/errors | **3 messages en français qui cassent la convention « English only »** | `errors.py:62, 132-134, 135-138` | Convention déclarée ligne 4 : « All messages are in English. Frontend handles i18n/translation to French ». Mais 3 messages sont en FR :<br>- `DEPARTURE_LINE_NOT_FOUND = "Ligne de départ inconnue"`<br>- `RESERVATION_ADVANCE_NOT_PAID` (long texte FR)<br>- `RESERVATION_SIGNATURE_REQUIRED` (long texte FR)<br>Frontend ne peut pas traduire fidèlement → texte FR brut affiché aux utilisateurs anglophones. À traduire en EN ou changer la convention en FR partout. |
| **F203** | constants/errors | `ErrorMessages` 200+ entrées dans une seule classe | `errors.py:8-423` | Single Responsibility violée — Auth, Resources, Validation, MFA, CSRF, Loyalty, etc. dans une mégaclasse. À éclater en 17 sous-classes alignées sur les sections existantes (commentaires `# -----` les délimitent déjà). Avantages : import ciblé, navigation IDE plus rapide. |
| **F204** | constants/errors | **Duplication messages avec `core/exceptions.py`** | `errors.py:275, 278` (`INVALID_CREDENTIALS = "Invalid email or password"`, `TOKEN_EXPIRED = "Token has expired"`) vs `exceptions.py:55, 61` (mêmes messages dans les exceptions) | Source unique de vérité cassée. Si on change le wording côté `ErrorMessages.INVALID_CREDENTIALS`, les exceptions levées par `raise InvalidCredentials()` continuent d'utiliser l'ancien message. À unifier : exceptions consomment `ErrorMessages` ou inverse. |
| **F205** | constants/errors | Template `{scope}` jamais formaté | `errors.py:295` (`SCOPE_REQUIRED = "Required scope: {scope}"`) | Placeholder orphelin — aucun callsite ne fait `.format(scope=...)`. Soit dead code, soit bug latent (message exposé tel quel `"Required scope: {scope}"`). À auditer ou retirer. |
| **F206** | constants/security | **`MFAConfig.ISSUER_NAME = "Marveline"` hardcodé** | `security.py:356` | Cf F06 module 01 — label TOTP affiché dans Google Authenticator. Pour Splendid, devrait afficher "Le Splendid". À dériver de `tenant_brand.display_name` au moment de l'enrôlement TOTP. |
| **F207** | constants/security | `RedisKeys` mix callable / préfixe brut — convention incohérente | `security.py:65-248` | 21 préfixes ont un helper `@staticmethod` callable, **9 préfixes n'en ont pas** : `BRUTE_FORCE_LOCK`, `BRUTE_FORCE_ALERT`, `CREDENTIAL_STUFFING`, `CAPTCHA_REQUIRED`, `LOGIN_BLOCKED`, `PASSWORD_RESET_TOKEN`, `PASSWORD_RESET_RATE`, `DEGRADED_*`, `API_KEY_CACHE`, `FEATURE_FLAG_CACHE`. Cf F30, F36 module 01. Forces les call-sites à `f"{RedisKeys.X}{id}"` (concat manuelle). À harmoniser : tout en callable. |
| **F208** | constants/security | **Pas de tenant scoping dans les clés Redis** | `security.py:142-249` (tous les helpers) | `RedisKeys.csrf_token(session_id)` → `csrf:{session_id}`. **Pas de tenant_id dans la clé**. Si 2 tenants ont des sessions avec le même UUID (collision astronomique mais théorique), conflit. Pour rate_limit, login, brute_force : pas de scoping tenant non plus. Cf F84 module 03. À ajouter `:t{tenant_id}:` dans tous les helpers. |
| **F209** | constants/security | `RateLimitScope` couvre épicerie/restaurant mais **pas Marveline ni Splendid** | `security.py:360-388` | 4 scopes app-specific : `EPICERIE_AUTHENTICATED`, `EPICERIE_MUTATIONS`, `RESTAURANT_AUTHENTICATED`, `RESTAURANT_MUTATIONS`. Pas de `MARVELINE_*` ni `LESPLENDID_*`. Marveline + Splendid tombent dans `USER_AUTHENTICATED` partagé. Cf F113 module 04. |
| **F210** | constants/limits | **Doublons entre `Limits` et `SessionConfig` / `settings`** | `limits.py:22, 61-62` vs `security.py:333` (MAX_SESSIONS_PER_USER) ; `limits.py:55-58` vs `config.py:74-75` (ACCESS/REFRESH_TOKEN_EXPIRE_SECONDS) ; `limits.py:38-39` vs `config.py:77` (RSA_KEY_SIZE) | 3 sources de vérité pour la même valeur. Si on tune `MAX_SESSIONS_PER_USER = 10`, faut-il modifier `limits.py`, `security.py:SessionConfig`, ou `config.py:settings` ? Risque divergence. Le commentaire `Argon2Params:295-297` reconnaît partiellement le problème (« source unique de vérité depuis variables d'environnement ») mais la résolution est partielle. À unifier : settings.py = source pour valeurs overridables env, constants/limits.py = défauts non-overridables. Pas de redéclaration. |
| **F211** | constants/limits | `Limits` classe agrégat sans domaine | `limits.py:12-92` | Mélange pagination + sécurité + tokens + password reset + business. À éclater (`PaginationLimits`, `SecurityLimits`, `BusinessLimits`, `RetryLimits`). Cf modèle `_template_domaine.py` qui propose une approche par domaine. |
| **F212** | constants/http | `AuthEndpoints` **17 routes hardcodées** | `http.py:59-83` | À chaque ajout d'endpoint d'auth (V3, OAuth Google, WebAuthn enrollment, …), édition de la classe + ajout dans `CSRFProtectionMiddleware.exempt_paths` (cf F124 module 04). Devrait être dérivé du router FastAPI lui-même via tag `auth` ou décorateur `@auth_endpoint`. |
| **F213** | constants/loyalty | `LoyaltyNotifType` 6 valeurs hardcodées | `loyalty.py:169-177` | Tous les types de notifications loyalty. Pour un nouveau programme (ex: Splendid avec notifs spécifiques), édition du code. À déplacer en table `loyalty_notif_template`. |
| **F214** | constants/approvisionnement | `SourceFournisseur` enum 5 valeurs hardcodées | `approvisionnement.py:8-21` | METRO, TAIYAT, EUROCIEL, ETHAN, GNANAM. Tout nouveau fournisseur = édition code + migration. À déplacer en table `suppliers.etl_parser_code` libre. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F215** | constants/__init__ | Re-export massif de ~70 symboles | `__init__.py:20-95` | Tout import de `app.constants` charge les 9 sous-modules + leurs ~2300 LoC. Cf F38 module 01. À déprécier — favoriser imports précis (`from app.constants.business import UserRole`). |
| **F216** | constants/__init__ | Ordre des re-exports illogique | `__init__.py:20-95` | Enums métier mélangés avec constantes business + messages erreur + sécurité + HTTP. À réorganiser par bloc thématique. |
| **F217** | constants/business | Workflow `ReservationStatus` ambigu | `business.py:80-90` | Commentaire docstring : « RETURNED_DISPUTE → RETURNED → COMPLETED » puis « → COMPLETED (clôture directe) ». Pas clair si l'on peut clôturer directement depuis RETURNED_DISPUTE ou seulement via RETURNED. À documenter en machine d'état formelle. |
| **F218** | constants/business | Convention naming : `(str, Enum)` au lieu de `StrEnum` | `business.py` entier | Python 3.11+ a `StrEnum` qui simplifie. Le codebase utilise systématiquement `(str, Enum)` (legacy). Convention non documentée. À harmoniser. |
| **F219** | constants/loyalty | `RewardTier` 4 valeurs hardcodées | `loyalty.py:99-111` | WELCOME, TIER_1, TIER_2, TIER_3. Pour ajouter TIER_4 ou modifier les seuils, édition + migration enum DB. À déplacer en table `rewards_catalog` (déjà mentionnée dans le doc fichier). |
| **F220** | constants/loyalty | Mix nommage MAJUSCULES vs lowercase | `loyalty.py:50-94` (`EARN, REDEEM`) vs `loyalty.py:15-23` (`POINTS, TIERED_DISCOUNT` aussi MAJUSCULES) | Cohérent en réalité (UPPERCASE dans Enum), mais `LoyaltyProgramType.POINTS.value == "points"` (lowercase value). Les value strings sont parfois lowercase, parfois UPPERCASE — à vérifier dans la DB. |
| **F221** | constants/security | `BruteForceThresholds`, `CredentialStuffingThresholds` non-overridable | `security.py:251-286` | Pas de tenant override. Pour un tenant à fort trafic légitime (haute saison événementielle Marveline ?), `WARNING_THRESHOLD = 50/min` peut être atteint. À déplacer en `tenant_settings` ou par-app. |
| **F222** | constants/security | `Argon2Params` partagé settings/constants | `security.py:289-304` (HASH_LENGTH, SALT_LENGTH ici) vs `config.py:108-110` (TIME_COST, MEMORY_COST, PARALLELISM) | Le commentaire ligne 295-297 reconnaît la séparation mais elle est arbitraire. À soit centraliser tout dans settings, soit clarifier (params secrets-rotatable vs format-stable). |
| **F223** | constants/security | `SessionConfig.MAX_SESSIONS_PER_USER` doublon avec `Limits.MAX_SESSIONS_PER_USER` | `security.py:333` vs `limits.py:62` | Cf F210. |
| **F224** | constants/http | `PublicEndpoints.all()` retourne un nouveau set chaque appel | `http.py:53-56` | Devrait être un attribut frozen `ALL: ClassVar[frozenset[str]] = frozenset({...})`. Performance négligeable mais convention. |
| **F225** | constants/http | `HealthEndpoints` séparé de `PublicEndpoints` malgré que health soit public | `http.py:95-104` vs `:38-56` (Health présent dans PublicEndpoints aussi !) | `PublicEndpoints.HEALTH = "/api/v1/health"` ET `HealthEndpoints.BASE = "/api/v1/health"`. Doublon. À unifier. |
| **F226** | constants/approvisionnement | `EtlStatutImport` mix anglais/français dans les valeurs | `approvisionnement.py:51-58` (PENDING, RUNNING, PREVIEW, VALIDATED, REJECTED en EN ; SUCCES, PARTIEL, ECHEC en FR) | Inconsistance. Soit tout en EN (PARTIAL, FAILURE) soit tout en FR (EN_ATTENTE, EN_COURS). À harmoniser. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F227** | _template_domaine | Template livré dans le package au lieu de `docs/` | `_template_domaine.py` — devrait être dans `docs/templates/` ou `scripts/templates/`. |
| **F228** | constants/errors | Ponctuation finale incohérente | `errors.py` divers — certains messages avec `.`, d'autres sans. |
| **F229** | constants/business | `EVENT_TYPE_MIN_DAYS` dict module-level | `business.py:516-521` — devrait être class-attribute. |
| **F230** | constants/security | `RedisKeys.CSP_DEFAULT` block dans `SecurityHeaders` | `security.py:55-62` — block CSP devrait être éclaté par directive et générable selon les besoins (nonce, brand domain). |
| **F231** | constants/loyalty | Seuils churn/expiry trop nombreux | `loyalty.py:226-235` (CHURN_RISK_MIN_DAYS=21, MAX_DAYS=35, EXPIRY_WARNING_DAYS_FIRST=14, SECOND=3) — micro-paramètres tuning, devraient être en `loyalty_program` table. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `constants/__init__` → tous les sous-modules (re-export massif).
- `constants/security` → `enum.Enum` (standalone).
- Tous les autres → `enum.Enum` (standalone).
- **Aucune dépendance externe** au module constants — propre.

### 4.2 Fuites identité Marveline / Splendid (synthèse)

Frictions multi-brand cumulées dans ce module :
- **F195** : 12 constantes CGV Marveline en module-level.
- **F196** : `TVA_RATE = 0.20` hardcodé pour les 4 apps.
- **F197** : Loyalty 2 programmes mélangés.
- **F198** : `ProductCategory` 20 catégories Marveline-only.
- **F199** : `ProductColor`, `ProductGamme` Marveline-only.
- **F200** : `ContainerType`, `EVENT_TYPE_MIN_DAYS`, `ReservationDeliveryMethod` Marveline-only.
- **F206** : `MFAConfig.ISSUER_NAME = "Marveline"`.
- **F209** : `RateLimitScope` couvre épicerie/restaurant mais pas Marveline/Splendid distincts.

→ La couche `constants/` est **explicitement Marveline-centric**. Aucune préparation pour multi-brand. Toute extension multi-tenant nécessite refonte profonde.

### 4.3 Forward-references confirmées

- F30, F36, F37 module 01 (RedisKeys conventions) confirmés ici (F207, F208).
- F84 module 03 (rate limit pas tenant-aware) confirmé ici (F208, F209).
- F113 module 04 (pas de scope MARVELINE/LESPLENDID) confirmé ici (F209).

### 4.4 Forward-impact

- **F195** impactera tous les modules métier qui consomment ces constantes :
  - `services/devis`, `services/reservation`, `services/invoice` → calculs acompte, caution, pénalités.
  - À auditer dans modules 18, 19, 21, 22.
- **F197** impactera modules 25 (loyalty).
- **F198, F199** impactera modules 15 (product-catalog) — `Product.category` peut être contraint par CHECK.

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Multi-brand business (P0)

1. **F195** : créer une table `tenant_business_rules` (ou enrichir `tenant_settings`) avec colonnes :
   ```python
   # tenant_settings.py
   class TenantSettings(Base, TimestampMixin):
       tenant_id: Mapped[int]
       deposit_rate: Mapped[float] = 3.0
       advance_payment_percent: Mapped[int] = 40
       advance_due_days: Mapped[int] = 7
       balance_due_days_before_event: Mapped[int] = 7
       late_return_penalty_rate: Mapped[float] = 0.20
       linen_min_booking_days: Mapped[int] = 90
       hourly_rate_weekday_cents: Mapped[int] = 3000
       hourly_rate_weekend_cents: Mapped[int] = 6000
       low_stock_threshold: Mapped[int] = 5
       weight_surcharge_threshold_grams: Mapped[int] = 500_000
       weight_surcharge_cents: Mapped[int] = 5000
       selfie_booth_deposit_cents: Mapped[int] = 300_000
       # ... + version, modified_by, applies_from
   ```
   Service `tenant_settings` lit avec fallback sur `app/constants/business.py`. Service métier (`devis`, `reservation`) lit depuis `tenant_settings`, **jamais directement** depuis les constantes.

2. **F196** : créer `app/constants/tax.py` :
   ```python
   class TaxRate:
       LOCATION_EVENT = 0.20  # rental/event services
       FOOD_TAKEAWAY = 0.055   # alimentation à emporter
       FOOD_ONSITE = 0.10      # restauration sur place
       ALCOHOL = 0.20          # boissons alcoolisées
       SHIPPING = 0.20
   ```
   Ou mieux : `product.tva_rate` colonne, défaut depuis `tenant_settings.default_tva_rate`.

3. **F197** : refondre le module loyalty :
   - Table `loyalty_program` avec colonnes : `tenant_id, type, points_per_eur, vip_threshold, vip_multiplier, points_expiry_months, reward_costs_json, tier_thresholds_json, ...`.
   - `LoyaltyTier` enum éclaté en `IncontournableTier(STANDARD, VIP)` et `MarvelineTier(NOUVEAU, HABITUE, PRIVILEGIE)`. Ou typage par `program_type`.
   - Constantes `loyalty.py` deviennent **defaults** lus seulement si pas de row `loyalty_program` pour le tenant.

### 5.2 Priorité 2 — Nettoyage duplications (P1)

4. **F210** : choisir une source de vérité par valeur :
   - `MAX_SESSIONS_PER_USER` : seulement dans `Limits`. Supprimer de `SessionConfig`.
   - `ACCESS_TOKEN_EXPIRE_SECONDS` : seulement dans `settings.JWT_ACCESS_TOKEN_EXPIRE_SECONDS`. Supprimer de `Limits`.
   - `RSA_KEY_MIN_BITS` : seulement dans `settings.JWT_RSA_KEY_SIZE`. Supprimer de `Limits.RSA_KEY_MIN_BITS`.
   Audit `grep -rn "MAX_SESSIONS_PER_USER\|ACCESS_TOKEN_EXPIRE_SECONDS\|RSA_KEY"` puis update sites.

5. **F204** : choisir source unique entre `ErrorMessages` et `core/exceptions` :
   - Option A : `exceptions.py` consomme `ErrorMessages` :
     ```python
     class InvalidCredentials(AppException):
         message = ErrorMessages.INVALID_CREDENTIALS
     ```
   - Option B : `ErrorMessages` génère depuis les exceptions. Préférer A (lisibilité).

6. **F225** : merger `HealthEndpoints` dans `PublicEndpoints` ou inverse. Health est public, doublon évident.

### 5.3 Priorité 3 — Splendid multi-brand (P1)

7. **F198** : `ProductCategory` enum **gèle pour Marveline** (compat existing data) ; nouveaux tenants utilisent une table `product_category_ref(tenant_id, slug, label, sort_order)`. CHECK constraint `product.category` migré vers FK.

8. **F199** : `ProductColor`, `ProductGamme` → tabulaire. Idem `ContainerType` (F200).

9. **F206** : supprimer `MFAConfig.ISSUER_NAME`, lire `tenant_brand.display_name` au runtime.

10. **F209** : ajouter dans `RateLimitScope` :
    ```python
    MARVELINE_AUTHENTICATED = "marveline_authenticated"
    MARVELINE_MUTATIONS = "marveline_mutations"
    LESPLENDID_AUTHENTICATED = "lesplendid_authenticated"
    LESPLENDID_MUTATIONS = "lesplendid_mutations"
    ```
    Et `rate_limiter.get_scope_config` lit les overrides depuis `tenant_settings`.

### 5.4 Priorité 4 — Hygiène (P1-P2)

11. **F207** : tous les `RedisKeys` ont un helper callable. Pas d'accès direct au préfixe :
    ```python
    @staticmethod
    def brute_force_lock(identifier: str) -> str:
        return f"{RedisKeys.BRUTE_FORCE_LOCK}{identifier}"
    @staticmethod
    def password_reset_token(token: str) -> str:
        return f"{RedisKeys.PASSWORD_RESET_TOKEN}{token}"
    # etc.
    ```

12. **F208** : ajouter `:t{tenant_id}:` dans tous les helpers où le scoping tenant est attendu (tous sauf credential stuffing global).

13. **F202** : traduire les 3 messages FR en EN ou changer la convention `errors.py` en FR partout (cohérence > convention).

14. **F203** : éclater `ErrorMessages` en sous-classes alignées sur les sections (`ResourceErrors`, `AuthErrors`, `ValidationErrors`, `MFAErrors`, `RateLimitErrors`, etc.).

15. **F211** : éclater `Limits` :
    ```python
    class PaginationLimits:
        MAX_PAGE_SIZE = 1000
        DEFAULT_PAGE_SIZE = 100
    class SecurityLimits:
        CSRF_TOKEN_MIN_LENGTH = 32
        PASSWORD_MIN_LENGTH = 8
    class TokenLimits:
        ACCESS_EXPIRE_SECONDS = 900
        REFRESH_EXPIRE_SECONDS = 604800
    # etc.
    ```

16. **F212** : `AuthEndpoints` dérivé du router FastAPI :
    ```python
    def get_auth_endpoints() -> set[str]:
        return {route.path for route in auth_router.routes}
    ```
    Dynamique au lieu d'hardcodé.

### 5.5 Priorité 5 — Cosmétique (P3)

17. **F215** : déprécier `from app.constants import *`, favoriser imports précis.

18. **F226** : harmoniser `EtlStatutImport` (tout EN ou tout FR).

19. **F227** : déplacer `_template_domaine.py` dans `docs/templates/`.

20. **F218** : migrer vers `StrEnum` (Python 3.11+) progressivement.

### 5.6 Tests à écrire avant refonte

- **F195** : pour chaque service métier qui consomme `DEPOSIT_RATE`, `ADVANCE_PAYMENT_PERCENT`, etc., tester avec 2 tenants ayant des valeurs différentes en `tenant_settings`. Devrait actuellement échouer (1 seule valeur globale).
- **F196** : test `Devis.total_ttc` calculé pour un produit alimentaire (TVA 5.5%) vs location (TVA 20%). Devrait actuellement échouer (TVA 20% partout).
- **F197** : 2 programmes loyalty distincts, member palier `STANDARD` programme 1 ne peut pas avoir un palier `HABITUE` programme 2. Devrait actuellement passer (validation absente).
- **F204** : `raise InvalidCredentials()` puis modifier `ErrorMessages.INVALID_CREDENTIALS = "Credentials invalides"` → l'exception expose le nouveau message. Devrait actuellement échouer (exception garde le hardcode).
- **F210** : fuzz test changement `MAX_SESSIONS_PER_USER = 10` dans 1 source → vérifier que les 3 sources sont cohérentes.

### 5.7 Hors-scope

- Les ENUMs concrets (statuts, types) — couvert dans les modules métier qui les consomment.
- Les machines d'état (workflows) — module 19 (reservations), 22 (invoices), etc.

---

## 6. Verdict module 07

| Aspect | État |
|---|---|
| Convention « constantes isolées » | **Respectée structurellement** (9 sous-modules par domaine) **mais polluée par hardcodes Marveline** (F195, F198, F199, F200, F206, F209) |
| Multi-brand | **Couche entièrement Marveline-centric** : 12 constantes CGV en module-level, 20 catégories produit Marveline, 8 couleurs Marveline, MFA issuer Marveline, RateLimit scopes sans Marveline/Splendid |
| Multi-app | TVA 20% hardcodé inapplicable à épicerie (5.5%) / restaurant (10%) — F196 |
| Loyalty | 2 programmes mélangés (F197) — pas extensible à un 3ème |
| Doublons | `MAX_SESSIONS_PER_USER`, `ACCESS_TOKEN_EXPIRE_SECONDS`, `RSA_KEY_MIN_BITS` en 2-3 endroits (F210) ; `ErrorMessages` ↔ `exceptions.py` (F204) |
| Hygiène | 200+ messages dans une classe (F203), 17 routes auth hardcodées (F212), mix EN/FR dans messages (F202, F226) |
| Re-export | 70+ symboles eager-loaded (F215) |
| Dette | 37 nouvelles frictions : 3 P0, 17 P1, 12 P2, 5 P3 |

**Conclusion** : le module `constants/` est **techniquement propre dans son organisation** (un fichier par domaine, template fourni, utilisation cohérente d'`Enum`) **mais sa raison d'être — centraliser pour faciliter le tuning — est trahie** par :
1. **Hardcodes Marveline qui devraient être en `tenant_settings`** (F195, F196, F197) → toute modification CGV/loyalty pour Splendid = patch code + déploiement.
2. **Doublons** entre `Limits` / `SessionConfig` / `settings` (F210) → tuning ambigu.
3. **Couplage produit Marveline** dans les enums (F198, F199, F200) → impossible d'ajouter un brand avec un catalogue différent sans refonte profonde.

Pour respecter la convention « isolation maximale + scalabilité », **les 3 P0 (F195, F196, F197) sont des prérequis architecturaux** avant tout multi-brand sérieux. Le coût refonte est ~5-10 tables nouvelles + refactor des services métier qui lisent ces constantes (modules 14-25).

→ Module suivant : `08-schemas-base.md` (`app/schemas/base.py`, `common.py`, conventions Pydantic).
