# Module 14 — Customer (Marveline)

> **Phase C — Domaines métier Marveline.** Audit du domaine Customer : modèle de données, repository, service, endpoints REST, RFM analytics, campaigns email, import CSV.
>
> **Forward-références purgées :**
> - F148 (mod. 05) — `TenantMixin` sans FK
> - F294 (mod. 10) — `forgot_password` envoie email synchroniquement
> - F407 (mod. 13) — API keys sur `Permission` v2 (impact `Scope.CUSTOMERS_*`)

---

## 1. Inventaire des fichiers lus intégralement

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/customer.py` | 149 | Modèle SQLAlchemy + CHECK constraints |
| `app/repositories/customer.py` | 399 | Sync + Async repos avec search/history/RFM helpers |
| `app/services/customer.py` | 185 | CRUD + `send_rfm_campaign` |
| `app/api/v1/endpoints/customers.py` | 763 | 9 endpoints REST + RFM analytics + CSV import |
| `app/schemas/customer.py` | 409 | 11 schémas Pydantic |

**Volume total** : ~1 905 LoC.

> ⚠ **Aucun model `customer_history`** — l'historique est calculé à la volée par `get_customer_history` (jointure Reservation + Invoice). Aucune table d'audit dédiée.

---

## 2. Architecture observée

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Customer (clients location vaisselle)             │
│  ─────────────────────────────────────────────────────────────────── │
│  Type : individual | company | professional | association            │
│  CHECK : individual → first+last_name | autres → company_name        │
│  UNIQUE : (tenant_id, email)                                         │
│  Relations : Customer → Reservation (1:N) — passive_deletes=True    │
│              (FK ondelete=RESTRICT côté Reservation)                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       9 endpoints REST                                │
│  GET    /customers                  list paginated, search           │
│  GET    /customers/rfm              RFM global (NO PAGINATION)       │
│  POST   /customers/rfm/campaign     email blast par segment SYNC     │
│  GET    /customers/{id}/rfm-profile RFM individuel                   │
│  GET    /customers/{id}             détail                            │
│  GET    /customers/{id}/history     reservations+invoices+stats      │
│  POST   /customers                  create                            │
│  PATCH  /customers/{id}             update                            │
│  DELETE /customers/{id}             soft (default) ou hard delete    │
│  POST   /customers/import           CSV (UTF-8, 8 colonnes)          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              SEGMENTATION RFM (Recency / Frequency / Monetary)        │
│   3 implémentations dupliquées :                                      │
│     1. /customers/rfm                  (l. 173-184)                   │
│     2. /customers/rfm/campaign         (l. 251-262)                   │
│     3. _compute_rfm_for_customer       (l. 331-342)                   │
│   Source : Reservation(status="returned") + Invoice(status="paid")   │
│   Segments : Champions (R≤30, F≥5) | Loyal (R≤90, F≥3) |             │
│              Potential (R≤180) | At Risk (R≤365) | Lost | New (F=0) │
└─────────────────────────────────────────────────────────────────────┘
```

**Cohérence multi-tenant** : OK — toutes les requêtes filtrent `tenant_id`. `email_exists` aussi (avec UNIQUE constraint DB).

**Cohérence multi-app/multi-brand** : ⚠ Customer n'a **pas** de notion d'`app_code`/`brand_code`. Un client Marveline et un client Splendid coexistent sans distinction au niveau modèle (`tenant_id` les distingue si on suppose 1 tenant = 1 brand, mais cf. mod. 09 — `tenant_settings.brand_code` ≠ `tenant_id` strict).

---

## 3. Frictions identifiées — module 14

> Compteur global cumulé (modules 01–13) ≈ 441 frictions.
> Le module 14 ouvre à **F442**.

### 3.1 P0 — Bloquant production

#### F442 — `send_rfm_campaign` envoie les emails **synchroniquement** dans une boucle (HTTP block 8+ min)

**Constat.** `services/customer.py:163-175` :
```python
sent = 0
failed = 0
for _cid, name, email in customer_emails:
    try:
        await notification_service.send_plain_email(
            to=email, subject=subject, body=f"Bonjour {name},\n\n{message}",
        )
        sent += 1
    except Exception:
        ...
```

Aucun `asyncio.gather`, aucun queue Celery, `await` séquentiel. Pour un segment "Loyal" avec 1000 clients × ~500 ms par email SMTP = **~8 minutes** de blocage HTTP. Le gateway timeout (Nginx default 60s, Cloudflare 100s) coupe la connexion → côté frontend, l'admin voit "erreur 504" alors que l'envoi continue côté worker.

Pire : `db.commit()` n'est appelé qu'à la fin. Si l'admin retry, doublons d'emails.

**Action** : refactor en queue Celery (`task = send_campaign_async.delay(tenant_id, segment, ...)`) + retourner immédiatement `{task_id: "...", status: "queued"}`. Endpoint `GET /campaigns/{task_id}/status` pour suivre.

**Cf. F294** (mod. 10) — pattern récurrent dans le code, racine commune (pas de mécanisme générique de queue).

---

#### F443 — Logique RFM **dupliquée 3 fois** (drift garanti à la prochaine modification)

**Constat.** Trois implémentations exactes des mêmes seuils de segmentation :

```python
# endpoints/customers.py:173-184 (GET /rfm)
if frequency == 0:               segment = "New"
elif recency_days <= 30 and frequency >= 5:  segment = "Champions"
elif recency_days <= 90 and frequency >= 3:  segment = "Loyal"
elif recency_days <= 180:        segment = "Potential"
elif recency_days <= 365:        segment = "At Risk"
else:                            segment = "Lost"

# endpoints/customers.py:251-262 (POST /rfm/campaign) — copie exacte
# endpoints/customers.py:331-342 (_compute_rfm_for_customer) — copie exacte
```

Modifier un seuil = trois lieux à mettre à jour. Test d'invariant absent.

**Pourquoi P0** : la cohérence métier de la segmentation (clients "Champions" reçoivent le même message des deux endpoints) repose sur la discipline manuelle. Une variation involontaire (typo, optimisation locale) = drift segmentation = email envoyé à la mauvaise cohorte.

**Action** : extraire `RFMService.compute_segment(recency_days, frequency, monetary_cents) -> str` dans `app/services/rfm.py`. Constantes seuils dans `app/constants/business.py` (`RFM_CHAMPION_RECENCY=30`, `RFM_CHAMPION_FREQUENCY=5`, etc.). Test d'invariant : "deux endpoints rfm/global et rfm/{id} produisent le même segment pour le même client".

---

#### F444 — Pagination **absente** sur `GET /customers/rfm` (charge TOUS les clients du tenant)

**Constat.** `endpoints/customers.py:157-162` :
```python
customers = (await db.execute(
    select(Customer).filter(
        Customer.tenant_id == current_user.tenant_id,
        Customer.is_active == True,
    )
)).scalars().all()
```

Aucun `LIMIT`. Pour un tenant à 50 000 clients (objectif SaaS) = 50 000 rows en mémoire + 50 000 itérations Python pour calculer les segments. + 2 agrégats `GROUP BY customer_id` chargés en `dict` Python.

`/customers/rfm/campaign` (l. 234-239) et `/customers/{id}/history` (mod. l. 178-189) ont le même problème.

**Conséquence** : crash OOM au-delà de ~5 000 clients ; lent même pour Marveline (~500 clients aujourd'hui, mais n'évolue pas).

**Action** : (a) paginer le retour ; (b) ou exécuter les agrégats en SQL pur (window function pour recency, sum/count en GROUP BY) sans charger les rows individuels ; (c) vue matérialisée `customer_rfm_view` rafraîchie quotidiennement.

---

#### F445 — Pagination absente sur `GET /customers/{id}/history` (réservations 5 ans = 1000+ rows)

**Constat.** `repositories/customer.py:178-189` :
```python
reservations = (
    self.db.execute(
        select(Reservation).filter(...)
        .order_by(Reservation.event_date.desc())
    )
    .scalars().all()
)
```

Pas de `LIMIT`. Un client B2B traiteur événementiel sur 5 ans = ~1 réservation/semaine = 260 réservations + 260 factures. Acceptable. Un grand client = 1 000+. Schema `CustomerHistory` n'a pas de pagination.

**Action** : `LIMIT 100` par défaut + paramètre `?from_date=&to_date=` pour fenêtre.

---

#### F446 — Import CSV : **`commit` par ligne** (10 000 lignes = 10 000 transactions)

**Constat.** `endpoints/customers.py:754-757` :
```python
try:
    await CustomerService(db).create_customer(validated, current_user.tenant_id)
    await db.commit()  # ← commit dans la boucle
    report.created += 1
except Exception as exc:
    await db.rollback()
```

Pour 10 000 lignes = 10 000 round-trips DB + 10 000 transactions. Avec PostgreSQL local ~5 ms par commit = 50 secondes minimum. En réseau (RDS, Aiven) = 30+ minutes. Le HTTP timeout coupe la requête.

**Action** : batch par 100, `await db.commit()` toutes les 100 réussites. Ou `bulk_insert_mappings` (SQLAlchemy 2.0 `insert(...).on_conflict_do_nothing(...)`).

---

#### F447 — `email_exists` exclut les soft-deleted → réutilisation possible → IntegrityError au restore

**Constat.** `repositories/customer.py:78-86` :
```python
def email_exists(...):
    query = select(Customer).filter(Customer.email.ilike(...))
    query = self._apply_tenant_filter(query, tenant_id)
    query = self._apply_active_filter(query)  # ← exclut is_active=False
    ...
```

Scénario :
1. Client A créé avec `email=jean@dupont.fr`.
2. A est soft-deleted (`is_active=False`).
3. Nouveau client B créé avec le même email → `email_exists` retourne False → INSERT OK… *si la contrainte UNIQUE l'autorise*.

`models/customer.py:138` : `UniqueConstraint("tenant_id", "email")` — **pas filtrée sur `is_active`**. Donc l'INSERT crashe en `IntegrityError` (UNIQUE violation), retour 500 au lieu de 409.

Pire scénario inverse :
1. A soft-deleted, email réutilisé par B (impossible cf. ci-dessus, mais si la contrainte UNIQUE était partielle), puis A restauré (`is_active=True`) → collision.

Dans tous les cas, le code applicatif et la contrainte DB ne sont **pas alignés**.

**Action** : (a) soit `UniqueConstraint` partielle `WHERE is_active = TRUE` ; (b) soit `email_exists` ne filtre pas `is_active` (cohérent avec UNIQUE strict).

---

### 3.2 P1 — Forte friction architecturale

#### F448 — Seuils RFM hardcodés (30, 90, 180, 365 + 5, 3) absents de `constants`

**Constat.** Cf. F443. Aucune entrée dans `app/constants/business.py`.

**Action** : `RFMThresholds` namespace constants, configurable per tenant via `tenant_settings` à terme.

---

#### F449 — `Reservation.status == "returned"` string hardcoded dans 3 endpoints RFM

**Constat.** Lignes 132, 225, 311. Cf. mod. 18 (Reservation FSM) — drift si on renomme `returned` → `completed`.

**Action** : `from app.constants import ReservationStatus; ReservationStatus.RETURNED.value`.

---

#### F450 — `siret` regex `^\d{14}$` sans validation Luhn

**Constat.** `schemas/customer.py:84` valide uniquement la longueur + format. Un SIRET INSEE valide a un checksum Luhn sur les 14 chiffres (en réalité sur les 9 du SIREN). `12345678901234` passe validation Pydantic mais ne correspond à aucune entreprise réelle.

**Conséquence** : factures émises avec un SIRET invalide → rejet comptable, demande de redress par client.

**Action** : `field_validator` avec `validators.siret_luhn(value)` (algorithm public, ~10 LoC).

---

#### F451 — `vat_number` aucune validation (DB + schema)

**Constat.** `models/customer.py:103-107` `String(20)` libre. `schemas/customer.py:88-92` `max_length=20` sans pattern. Format VIES (FR + 11 chars, DE + 9 digits, etc.) non vérifié.

**Action** : regex multi-pays `^[A-Z]{2}[A-Z0-9]+$` minimum, validation VIES API en mode strict (rate limit attention).

---

#### F452 — `country` default "France" hardcoded — bloque expansion + Splendid potentiellement multi-pays

**Constat.** `models/customer.py:89-94` + `schemas/customer.py:74-78`. String libre, défaut "France". Pour Splendid (cf. mod. 09), si étend à Belgique/Suisse → champ ne s'aligne pas.

**Action** : ISO 3166-2 alpha-2 (`String(2)`) + tenant_settings.default_country.

---

#### F453 — `search` `ilike "%term%"` sur 4 colonnes sans index trigram → full scan

**Constat.** `repositories/customer.py:136-142` :
```python
search_pattern = f"%{search_term.lower()}%"
text_filter = (
    Customer.first_name.ilike(search_pattern) |
    Customer.last_name.ilike(search_pattern) |
    Customer.company_name.ilike(search_pattern) |
    Customer.email.ilike(search_pattern)
)
```

Aucun index `gin (lower(first_name) gin_trgm_ops)`. PostgreSQL fait un Seq Scan + filtre row-par-row. Pour 50k customers = 200 ms typique. Recherche UI typeahead = lag visible.

**Action** : extension `pg_trgm` + index GIN sur les 4 colonnes lowercased.

---

#### F454 — `notes` String(2000) plain text — peut contenir PII (RGPD), pas chiffré

**Constat.** `models/customer.py:110-114` : "Note interne (non visible client)". Les commerciaux y stockent typiquement : numéro de téléphone perso, anniversaire, allergies (RGPD données de santé), références familiales, raisons de plainte. PII en clair, accessible en lecture par tout user avec scope `customers:read`.

**Action** : (a) chiffrer en repos via `EncryptedField` (envelope encryption mod. 12) ; (b) ajouter `notes_redacted` flag pour masquer aux rôles non-managers.

---

#### F455 — Aucun `created_by`/`updated_by` (pas de trace "qui a créé ce client")

**Constat.** `Customer` hérite `TimestampMixin` (`created_at`/`updated_at`) mais aucune référence à l'account/membership créateur. Un client "douteux" inséré → aucun moyen de remonter à l'auteur sans `audit_log`.

**Action** : ajouter `created_by_membership_id`, `updated_by_membership_id` (FK SET NULL).

---

#### F456 — `delete_customer` aucun audit log (soft-delete invisible)

**Constat.** `services/customer.py:123-139` n'appelle pas `AuditService.log_action`. Cf. mod. 12 F386 — pattern récurrent : actions destructives sans audit.

**Action** : `await audit_service.log_action(action="CUSTOMER_DELETED", entity_type="Customer", entity_id=customer_id, ...)`.

---

#### F457 — CSV import `_CUSTOMER_CSV_FIELDS` exclut `siret` + `vat_number` (B2B inimportable)

**Constat.** `endpoints/customers.py:641-644` :
```python
_CUSTOMER_CSV_FIELDS = {
    "customer_type", "email", "first_name", "last_name",
    "phone", "address", "city", "postal_code", "country",
}
```

Pas de `siret`, pas de `vat_number`. L'admin qui importe une liste de clients B2B (la cible principale Marveline location événementiel B2B) doit re-saisir manuellement les SIRET après import. Inutilisable en pratique pour la migration depuis Excel.

**Action** : ajouter `siret`, `vat_number`, `notes`, `company_name` à la liste autorisée + le payload (`row.get("siret")`, etc.).

---

#### F458 — `CustomerUpdate.email: Optional[EmailStr]` permet `email=None` explicite → `IntegrityError 500`

**Constat.** `schemas/customer.py:161-165` : `email: Optional[EmailStr]`. Un client envoie `PATCH {"email": null}` → `model_dump(exclude_unset=True)` ne l'exclut **pas** (`exclude_unset` exclut les champs absents, pas ceux explicitement à `None`). `setattr(customer, "email", None)` → `Customer.email NOT NULL` → IntegrityError → catch generic `except Exception → HTTPException(500)` (cf. F460) → fuite "psycopg.errors.NotNullViolation: …".

**Action** : `model_validator` qui rejette `email=None` (ou `Field(default=None, exclude_none=True)`).

---

#### F459 — `email_exists` filtre soft-deleted (cf. F447) — **incohérent** avec UNIQUE constraint DB

Cf. F447. Service code et contrainte DB désalignés.

---

#### F460 — Pattern endpoint `except Exception → 500 detail=str(e)` (3× — fuite info interne)

**Constat.** `endpoints/customers.py:484-489, 543-548, 593-597` :
```python
except Exception as e:
    logger.exception("Unexpected error in create_customer")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"An error occurred while creating customer: {str(e)}"
    )
```

`str(e)` peut contenir le message PostgreSQL brut (ex. `"duplicate key value violates unique constraint \"uq_customer_tenant_email\" DETAIL: Key (tenant_id, email)=(1, jean@dupont.fr) already exists."`) → fuite schéma DB + nom de contrainte → enumeration tenant possible.

**Action** : `detail="Internal server error"` générique ; le détail est dans `logger.exception` côté serveur uniquement. Pattern à corriger sur tous les endpoints (cf. mod. 04 ExceptionHandler).

---

#### F461 — `Customer.country` String(100) free text → drift "France"/"FRANCE"/"FR"

Cf. F452. Stats par pays inutilisables (groupements éclatés).

---

#### F462 — `CustomerHistory` schema n'inclut **pas** les ventes directes ni les relances (vue partielle)

**Constat.** `schemas/customer.py:358-364` : `reservations + invoices + stats`. Manque :
- `ventes` (Vente — ventes directes sans réservation, mod. 22+)
- `relances` (Relance — courriers de relance impayés, mod. 23+)
- `evenements` (incidents/réclamations, mod. 24+)
- `loyalty_points_history` (mod. 25+)

L'admin qui veut une fiche client 360° voit une vue tronquée.

**Action** : étendre `CustomerHistory` avec sections optionnelles `?include=ventes,relances,evenements,loyalty`.

---

#### F463 — Aucune relation Customer ↔ Account/User (impossible "ce client est aussi user")

**Constat.** Pas de `account_id` ou `user_id` sur `Customer`. Un client qui ouvrirait un compte self-service (futur portail) ne pourrait pas être lié à son enregistrement Customer existant.

**Action** : `account_id: Mapped[Optional[int]] = ForeignKey("accounts.id", ondelete="SET NULL")` nullable pour soft-link.

---

#### F464 — `customer_type` 4 valeurs (`individual`, `company`, `professional`, `association`) mais `display_name` ne traite que individual vs autres

**Constat.** `models/customer.py:142-146` :
```python
@property
def display_name(self) -> str:
    if self.customer_type == CustomerType.INDIVIDUAL:
        return f"{self.first_name} {self.last_name}"
    return self.company_name or "Client sans nom"
```

`professional` et `association` sont traités identique à `company` — pas de différenciation visuelle. La distinction métier (`professional` = profession libérale, `association` = loi 1901) est invisible côté UI.

**Action** : préfixer le display_name : `"Asso. " + company_name` pour association, `"Pro. " + company_name` pour professional.

---

#### F465 — `customer_type` colonne DB `String(20)` sans enum natif PostgreSQL

**Constat.** `models/customer.py:31-35`. CHECK constraint compense, mais un enum DB serait plus type-safe et performant pour les filtres.

---

### 3.3 P2 — Friction modérée

#### F466 — `display_name` property dans model + computed_field dans schema = duplication

**Constat.** Logique répétée trois fois (`models/customer.py:142-146`, `schemas/customer.py:262-266`, `:301-305`). Drift entre rendering server-side (model) et client-side (schema).

**Action** : computed dans le schema seulement, supprimer du model.

---

#### F467 — `notes` `String(2000)` au lieu de `Text` — limite arbitraire

**Constat.** Note longue d'historique commercial (5 ans de relations) déborde rapidement.

**Action** : `Text` (ou colonne séparée `customer_notes` 1:N).

---

#### F468 — `Customer.tenant_id` pas de FK vers `tenants` (cf. F148 mod. 05)

Confirmé.

---

#### F469 — `Customer.email` pas de format validé en DB

**Constat.** Pydantic `EmailStr` valide à l'écriture API mais migration directe SQL peut insérer "abc". Aucun `CHECK (email ~ '@')` ni domain extension.

**Action** : `CHECK (email LIKE '_%@_%._%')` minimum.

---

#### F470 — `get_customer_history` retourne `dict` non typé

**Constat.** `repositories/customer.py:165-223` returns `dict`. L'endpoint reconstruit manuellement les schémas. TypeError silencieux possible si la structure dérive.

**Action** : retour `CustomerHistoryDTO` Pydantic ou TypedDict.

---

#### F471 — RFM `New` segment quand `frequency == 0` mais "new" ≠ "jamais réservé"

**Constat.** Un client créé hier sans réservation = "New". Un client de 2018 jamais réservé (créé pour devis annulé) = aussi "New". Conflation de deux états.

**Action** : ajouter "Inactive" pour `created_at < 90j AND frequency = 0` ; "Truly New" pour `created_at <= 30j AND frequency = 0`.

---

#### F472 — `RFMCampaignRequest.segment` regex hardcoded

**Constat.** `schemas/customer.py:388-392` : `pattern=r"^(Champions|Loyal|Potential|At Risk|Lost|New)$"`. Drift garanti si on ajoute `Inactive` (cf. F471) à un seul endroit.

**Action** : enum partagée `RFMSegment` (StrEnum).

---

#### F473 — `CustomerType` 4 valeurs mais le code suggère 2 grandes catégories (B2C / B2B)

`individual` = B2C ; `company`/`professional`/`association` = B2B. Une colonne `is_b2b: bool` simplifierait les filtres.

---

#### F474 — `address` String(500) générique vs `street`/`postal_code`/`city` séparés

**Constat.** `models/customer.py:71-87` : on a `address` (libre 500 chars) **et** `city` + `postal_code` séparés. Redondance + incohérence : `address` peut contenir "Paris 75001" alors que `city="Lyon"` `postal_code="69001"`.

**Action** : choisir un seul mode. Idéalement `street`, `street_2` (Apt/Bât), `postal_code`, `city`, `country` séparés (RGPD-friendly, validation par pays).

---

#### F475 — `phone` String(20) sans validation E.164

**Constat.** `models/customer.py:64-68`. `+33612345678` (E.164) et `06 12 34 56 78` (national) tous deux acceptés. Bloque l'intégration SMS / appels.

**Action** : `phonenumbers` library, normaliser à E.164 à l'écriture.

---

#### F476 — `list_with_pending_relances` ORDER BY `(company_name, last_name)` → NULL FIRST en PostgreSQL = NULL en haut

**Constat.** `repositories/customer.py:256` : un individual a `company_name=NULL` → trié en haut, juste avant les company "AAA Co".

**Action** : `ORDER BY company_name NULLS LAST, last_name NULLS LAST`.

---

#### F477 — Aucun test d'invariant RFM (drift des seuils non détecté)

**Action** : test "les 3 implémentations donnent le même segment pour le même `(R, F, M)`".

---

#### F478 — `_CUSTOMER_CSV_REQUIRED = {customer_type, email}` mais `individual` exige aussi `first_name` + `last_name`

**Constat.** Le check côté CSV ne vérifie que `customer_type + email`. Une ligne `customer_type=individual,email=jean@x.fr,first_name=,last_name=` passera le check primaire, puis Pydantic `model_validator` raisera ValueError → catch en `report.errors`. OK fonctionnel mais l'erreur est tardive.

**Action** : pré-validation conditionnelle sur les colonnes requises selon `customer_type`.

---

#### F479 — Pas de `Repository.bulk_create` — boucle individuelle pour CSV import

Cf. F446. Architectural pattern manquant.

---

#### F480 — `notification_service.send_plain_email` synchrone (cf. F294 mod. 10)

Confirmé. Source unique du problème.

---

### 3.4 P3 — Cosmétique / dette légère

#### F481 — Endpoint docstrings exposent JSON examples très verbeux (~30 LoC chacun)

Surface OpenAPI lourde. Préférer `Field(... examples=[...])` Pydantic.

#### F482 — `CustomerHistoryReservation.total_amount_cents: int` non Optional alors que reservation peut être pré-devis

#### F483 — RFM segment string libre dans schema vs enum (F472 doublon)

#### F484 — Comments `# noqa: E712` répétés pour `is_active == True` — pattern à factoriser

---

## 4. Synthèse module 14

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 6 | F442 (campaign sync), F443 (RFM dupliqué 3×), F444 (RFM no pagination), F445 (history no pagination), F446 (CSV commit/ligne), F447 (email_exists filtre soft-deleted) |
| P1 | 18 | F448 → F465 |
| P2 | 15 | F466 → F480 |
| P3 | 4 | F481 → F484 |
| **Total module 14** | **43** | F442 → F484 |

**Compteur cumulé après module 14** : ≈ 441 + 43 = **484 frictions** (61 P0, 199 P1, 172 P2, 52 P3).

---

## 5. Forward-références à traiter

- **Module 15 (Product / Catalog)** : confirmer absence de relation `Product.customer_segments` (pricing par segment RFM ?).
- **Module 18 (Reservation / FSM)** : valider que `status="returned"` est bien le statut "completed" RFM (cf. F449).
- **Module 22 (Vente directe)** : intégrer dans `CustomerHistory` (cf. F462).
- **Module 25 (Loyalty)** : confirmer relation Customer ↔ LoyaltyMember séparée (probable — mod. 12 mentionnait `LoyaltyTier`).
- **Module 99 (registry)** : F442 + F294 (mod. 10) + send sync emails = pattern systémique → réclamer un `CeleryEmailService` global.

---

## 6. Décision architecturale recommandée

> **Triplet P0 immédiat** :
> 1. **Extraire `RFMService` + constantes seuils** (F443 + F448) — supprime la duplication 3× et stabilise la segmentation.
> 2. **Queue Celery pour `send_rfm_campaign`** (F442) — pattern réutilisable pour `forgot_password`, relances, notifications (F294).
> 3. **Pagination forced sur `/customers/rfm` + `/customers/{id}/history`** (F444 + F445) — éviter l'OOM SaaS.
>
> **Refactor structurel** :
> - Vue matérialisée `customer_rfm_view` (rafraîchie nuit) : recency, frequency, monetary par customer + tenant — supprime les joins lourds par requête.
> - Index trigram (pg_trgm) sur first_name/last_name/company_name/email (F453).
> - Tenant_settings.default_country + champ `country` ISO 3166-2 (F452 + F461).
> - `created_by_membership_id` + audit log soft-delete (F455 + F456).
> - SIRET Luhn validator + VAT VIES validator (F450 + F451).
