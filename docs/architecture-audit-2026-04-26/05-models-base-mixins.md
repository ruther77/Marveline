# Module 05 — Models base + mixins

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/models/base.py` | 134 | `Base(DeclarativeBase)` + `to_dict`/`from_dict` ; mixins `TimestampMixin`, `TenantMixin`, `SoftDeleteMixin` |

**Total** : 134 LoC.

**Dépend de** : `sqlalchemy.orm.DeclarativeBase`, `sqlalchemy.{BigInteger, Boolean, DateTime, func, inspect}`.

**Dépendu par** : **88 fichiers de modèles** (tous les modèles métier).

---

## 2. Lecture par fichier

### 2.1 `Base(DeclarativeBase)` (lignes 8-85)

#### `to_dict(exclude_relations=True) -> dict[str, Any]` (ligne 16)
- Itère sur `inspect(self.__class__).columns` (toutes les colonnes mappées).
- Convertit `datetime` → ISO string.
- **Ne filtre rien** : expose toutes les colonnes, dont `tenant_id`, `is_active`, `created_at`, `updated_at`, et **toutes les colonnes sensibles définies dans les modèles** (ex: `hashed_password`, `encrypted_secret`, `email`).

#### `from_dict(data: dict[str, Any]) -> instance` (ligne 50)
- Filtre les clés inconnues (safety).
- Convertit ISO string → datetime pour `DateTime` columns.
- **Crée l'instance sans l'attacher à la session** (pas de `db.add`).
- Aucune validation de typage des autres champs (ex: int passé en string passe directement).

### 2.2 `TimestampMixin` (lignes 88-104)

```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    nullable=False,
    comment="Date de création de l'enregistrement"
)
updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now(),
    nullable=False,
    comment="Date de dernière modification"
)
```

- `DateTime(timezone=True)` avec `func.now()` server-side → cohérent UTC en PG si `timezone=UTC`.
- `onupdate=func.now()` → SQLAlchemy bump à chaque UPDATE.
- Pas d'index sur `created_at`/`updated_at` au niveau du mixin (chaque table doit ajouter au besoin).

### 2.3 `TenantMixin` (lignes 107-115)

```python
tenant_id: Mapped[int] = mapped_column(
    BigInteger,
    nullable=False,
    index=True,
    comment="ID du tenant (organisation cliente)"
)
```

- **Pas de `ForeignKey("tenants.id")`** → aucune contrainte d'intégrité référentielle.
- `BigInteger` (cohérent avec `Tenant.id` qui est `BigInteger` dans `tenant.py:31`).
- `index=True` → index simple sur `tenant_id` (pas composite).

### 2.4 `SoftDeleteMixin` (lignes 118-134)

```python
is_active: Mapped[bool] = mapped_column(
    Boolean, default=True, nullable=False,
    comment="Actif (False = supprimé logiquement)"
)
def soft_delete(self): self.is_active = False
def restore(self): self.is_active = True
```

- Soft delete par flag boolean — **pas de `deleted_at` timestamp** (donc impossible de savoir QUAND la suppression a eu lieu, ni de purger après N jours).
- `default=True` côté Python (pas server-side).
- `restore()` symétrique de `soft_delete()`.

### 2.5 Couverture observée dans les 88 modèles

#### Composition mixins (sample)
- `Container, ProductVariant, DamageType, Supplier, Product, ApiKey` : `Base, TimestampMixin, TenantMixin, SoftDeleteMixin` ✓ pattern canonique.
- `Account, MFADevice, AuthRole, AuthRoleScope, AuthScope, WebAuthnCredential, AccountOAuthIdentity, CatalogueProduit*, EtlCorrectionHistory` : pas de `TenantMixin` (10 modèles globaux par design).
- `Formula, Notification, TenantSettings, ProductMaintenance, ReservationVersion, TrustedDevice` : déclarent `tenant_id` **manuellement** sans utiliser `TenantMixin`.

#### Hétérogénéité des types
- **Type `tenant_id`** :
  - `BigInteger` via `TenantMixin` (~64 modèles).
  - `BigInteger` manuellement (`product_maintenance.py:18`, `reservation_version.py:20`, `trusted_device.py:31`, `audit_log.py:131`, `account_session.py:63`, `user_role.py:45`).
  - **`Integer` manuellement** : `formula.py:31`, `notification.py:11`, `tenant_settings.py:11`. → 3 modèles avec `tenant_id Integer` au lieu de `BigInteger`. Limite à 2³¹ (~2 milliards) au lieu de 2⁶³, et JOIN PG avec `Tenant.id BigInteger` → cast implicite.
- **Type primary key `id`** :
  - `Integer` : 14 modèles (legacy, ex: `formula.py:30`, `tenant_settings.py:10`, `notification.py:11`, `product_collection.py:28`, `product_image.py:20`, `pricing.py:15`).
  - `BigInteger` : 5 modèles (récents, ex: `tenant_membership.py:52`, `product_maintenance.py:17`, `trusted_device.py:27`).
  - Autres modèles : pas de déclaration explicite (cassé par `Base` ? pas de PK explicite ?).
- **Style de déclaration** :
  - SQLAlchemy 2.0 typed : `Mapped[int] = mapped_column(...)` (récent).
  - SQLAlchemy 1.x untyped : `id = Column(...)` (legacy, ex: `formula.py:30`, `notification.py:11`).
  Mix dans le même codebase.

#### FK vers `tenants` : 2 occurrences seulement
- `tenant_membership.py:63` : `ForeignKey("tenants.id", ondelete="CASCADE")`.
- `tenant_brand.py:22` : idem.
Sur 64 modèles avec `tenant_id`, **2 ont une FK** explicite. Les 62 autres ont juste un BigInteger sans contrainte référentielle.

#### Modèles sans `tenant_id` (10) — par design ou trou ?
- ✅ Par design (global) : `account.py`, `account_oauth_identity.py`, `auth_role.py`, `auth_role_scope.py`, `auth_scope.py`, `mfa.py` (lié à `tenant_membership`), `webauthn_credential.py` (lié à `account`), `catalogue/catalogue_produit_*.py` (catalogue partagé multi-tenant).
- ❓ À vérifier : `etl_correction_history.py` — selon le module 30 (catalogue-shared) → si une correction d'ETL est globale ou tenant-scoped.

---

## 3. Frictions identifiées

(Numérotation continue — F148 commence après le module 04.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F148** | TenantMixin | **`tenant_id` n'a pas de `ForeignKey("tenants.id")` — aucune contrainte d'intégrité référentielle** | `base.py:107-115` | Sur 64 tables `tenant_id NOT NULL`, **62 n'ont aucune FK**. Conséquences :<br>(a) Une INSERT avec `tenant_id=99999` (tenant inexistant) **réussit** côté PG. Les données orphelines existent.<br>(b) DELETE d'un tenant ne CASCADE pas sur ses 60+ tables métier — c'est désactivé par design ? À vérifier mais aucune doc explicite.<br>(c) En cas d'archivage/offboarding tenant (state machine `Tenant.TRANSITIONS` du module 01), aucune garantie automatique de purge des données. Tout repose sur du code Python qui doit énumérer les 64 tables.<br>(d) Multi-tenant à scalabilité maximale = FK universelle obligatoire avec `ON DELETE RESTRICT` (refuse de supprimer un tenant ayant encore des données — force l'offboarding explicite). À fixer en priorité avant tout audit RGPD réel. |
| **F149** | Hétérogénéité types | **`tenant_id` parfois `Integer` (32 bits) au lieu de `BigInteger` (64 bits)** | `formula.py:31`, `notification.py:11`, `tenant_settings.py:11` | `Tenant.id` est `BigInteger` (`tenant.py:31`). Si un tenant_id dépasse 2³¹ = 2 147 483 647, INSERT échoue silencieusement avec overflow ou JOIN cast implicite. Pour un SaaS qui peut générer des UUIDv4 → BigInteger via hash, ou pour la portabilité long terme, hétérogénéité de type = **bug de scalabilité dormant**. À fixer : tous les `tenant_id` en `BigInteger`. |
| **F150** | Base.to_dict | **Expose toutes les colonnes sans filtre** — y compris secrets/PII | `base.py:16-48` ; consommé par `repositories/base.py:262` (cache), exporté potentiellement vers les API responses si appelé directement | `to_dict` itère sur `mapper.columns` sans aucune exclusion. Pour `Account`, expose `hashed_password`. Pour `MFADevice`, expose `encrypted_secret`. Pour `WebAuthnCredential`, expose `public_key`. Pour `Customer`, expose `email`, `phone`, `address`. Si `to_dict` est utilisé pour construire une réponse API (sans schema Pydantic intermédiaire qui filtre), **leak massif de PII et secrets**. **De plus**, le commentaire ligne 7-13 dit "méthodes de sérialisation pour cache Redis" — donc `to_dict` est appelé sur **chaque entité cachée** dans `BaseRepository.get_by_id` (`repositories/base.py:262`) → **secrets stockés en cache Redis en clair**. À confirmer module 06. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F151** | Base | **Pas de `__repr__` standard** | `base.py:8-85` | `print(product)` retourne l'adresse mémoire Python. Debug et logs lisibles cassés. À ajouter un `__repr__` qui inclut au minimum `(class_name, id, tenant_id)`. |
| **F152** | TenantMixin | **Pas d'index composite par défaut** | `base.py:113` (`index=True` seul) | L'index simple `(tenant_id)` ne couvre pas les requêtes typiques `WHERE tenant_id = X AND <autre_col> = Y`. Chaque table doit ajouter `Index("ix_xxx_tenant_xxx", "tenant_id", "<col>")` à la main. Pour 64 tables × N colonnes courantes (status, customer_id, etc.) = N×64 index oubliés possibles. À tester via `EXPLAIN` sur les requêtes courantes. Voir module 06 (repositories). |
| **F153** | TenantMixin | **Pas de validation au niveau ORM `tenant_id > 0`** | `base.py:107-115` | Aucun CHECK constraint. Un bug applicatif qui crée une entité avec `tenant_id=0` ou `tenant_id=-1` passe en DB. À ajouter `CheckConstraint("tenant_id > 0", name="check_..._tenant_positive")`. |
| **F154** | SoftDeleteMixin | **Pas de `deleted_at` timestamp** | `base.py:118-134` | Soft delete par boolean uniquement. Conséquences :<br>(a) Impossible de savoir QUAND la ligne a été soft-deleted → audit RGPD incomplet (la trace est dans `audit_log` mais redondance utile en DB).<br>(b) Impossible de purger automatiquement après N jours (RGPD : data_retention_days du tenant) sans timestamp.<br>(c) Pas de `deleted_by_id` (qui a supprimé) — info dans audit_log mais pas accessible directement.<br>À ajouter : `deleted_at: Optional[datetime]`, `deleted_by_id: Optional[int]`, et `soft_delete(self, deleted_by_id: int)`. |
| **F155** | base | **Hétérogénéité de style SQLAlchemy 2.0 typé vs 1.x untyped** | Modèles 2.0 typed : `Mapped[int] = mapped_column(...)` (ex: `account.py`, `tenant_membership.py`) ; modèles 1.x untyped : `id = Column(...)` (ex: `formula.py:30`, `notification.py:11`) | Confusion à la lecture, type-hints manquants pour mypy/pyright sur les modèles legacy, conventions inconsistantes. À migrer tout en 2.0 typed. |
| **F156** | base | **PK `id` parfois `Integer` (32 bits) — limite 2³¹** | `formula.py:30`, `tenant_settings.py:10`, `notification.py:11`, `product_collection.py:28`, `product_image.py:20`, `pricing.py:15` (14 modèles total) | Pour un SaaS multi-tenant avec rotation de données et historique long, 2³¹ rows peut être atteint sur certaines tables (ex: `notifications` peut grossir vite). À harmoniser tout en `BigInteger`. |
| **F157** | TenantMixin | **6 modèles redéfinissent `tenant_id` au lieu d'utiliser `TenantMixin`** | `formula.py:31`, `notification.py:11`, `tenant_settings.py:11`, `audit_log.py:131`, `account_session.py:63`, `trusted_device.py:31`, `user_role.py:45`, `product_maintenance.py:18`, `reservation_version.py:20` | Duplication, divergence (cf F149 : `Integer` vs `BigInteger`). Un changement futur du `TenantMixin` (ajout FK, index composite, CHECK constraint) ne s'applique pas à ces 6+ modèles. À refactor pour utiliser `TenantMixin` uniformément. |
| **F158** | from_dict | **Pas de validation de cohérence après reconstruction** | `base.py:50-85` | Si une entrée du cache Redis est obsolète (ex: `is_active=True` en cache, `is_active=False` en DB), `from_dict` reconstruit avec les anciennes valeurs sans warning. Le caller doit vérifier la fraîcheur. À documenter ou ajouter un check `if data.get("_cache_version") != current_version`. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F159** | to_dict | Conversion datetime → ISO string ad hoc | `base.py:42-46` | Aucun encodage Decimal, UUID, Enum. Si une colonne est un Decimal (montant) ou un Enum, `to_dict` retourne un objet non-JSON-serializable → l'appel ultérieur à `json.dumps` (cache.py) lève. Réutilise `_DateEncoder` de `cache.py:45-55` (mais ce dernier est dans une classe séparée — duplication). À unifier : `Base.to_dict` doit retourner du JSON-serializable. |
| **F160** | TimestampMixin | Pas d'index sur `created_at`/`updated_at` | `base.py:91-104` | Pour les requêtes "récents" (ex: `ORDER BY created_at DESC LIMIT 10`) ou "modifiés depuis" (ex: webhook polling `WHERE updated_at > X`), pas d'index → table scan. À ajouter à la discrétion des modèles, mais une convention `Index("ix_xxx_created", "tenant_id", "created_at")` serait utile pour les modèles append-heavy. |
| **F161** | from_dict | Conversion ISO → datetime sans gérer microseconds/timezone variants | `base.py:78-82` | `datetime.fromisoformat(...)` accepte `2024-01-15T10:30:00`, `2024-01-15T10:30:00+00:00`, `2024-01-15T10:30:00Z` (Python 3.11+), mais peut échouer sur des formats moins standards. Pas de fallback. |
| **F162** | Base | Pas d'utility `to_pydantic` ni `from_pydantic` | `base.py` | Conversion ORM ↔ Pydantic est faite case-par-case dans les services/endpoints. Une méthode partagée éviterait la duplication. |
| **F163** | SoftDeleteMixin | `default=True` côté Python uniquement (pas server-side) | `base.py:121-126` | Si une INSERT brute (Alembic, script SQL) omet `is_active`, la valeur peut être NULL ou implicite. Devrait être `server_default="t"`. |
| **F164** | TenantMixin | Comment ligne 114 « ID du tenant (organisation cliente) » ne reflète pas le multi-app | (idem) | Avec 4 apps (Marveline, Splendid, Épicerie, Restaurant), un "tenant" peut être chacun de ces 4. À documenter explicitement la sémantique (1 tenant = 1 instance app + brand). |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F165** | Base | `to_dict` paramètre `exclude_relations` non utilisé | `base.py:16` (param accepté, jamais lu dans la fonction). |
| **F166** | base | Commentaires colonnes en français | `base.py:95,103,114,125` — convention non documentée (FR comments / EN code). |
| **F167** | base | `from_dict` n'utilise pas `cls.__init__` mais `cls(**filtered_data)` directement | `base.py:85` — usage standard SQLAlchemy mais ne déclenche pas les `__init__` custom des sous-classes. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `Base` est **importé partout** dans `app/models/*.py` (88 fichiers).
- `to_dict` consommé par `repositories/base.py:262` pour cache Redis → fuite de tous les champs (cf F150).
- `from_dict` consommé par `repositories/base.py:241` pour reconstruire depuis cache.

### 4.2 Cycles évités

- `Base` ne dépend de rien (pas même de `app.config`) → propre.

### 4.3 Forward-references

- F148 (FK manquante) → impacte modules 06 (repositories — peuvent oublier le filtre Python si la FK manque), 09 (tenant offboarding), tous les modules métier.
- F150 (to_dict expose tout) → confirmer module 06 (repositories.base) si effectivement utilisé pour cache.
- F154 (deleted_at manquant) → impacte modules 09 (RGPD retention) et 31 (audit-feature-flag).

### 4.4 Pas de fuite Marveline / Splendid spécifique

Le module 05 est neutre vs multi-brand — c'est l'usage qui peut fuir. La FK manquante (F148) est cependant un **prérequis** pour pouvoir un jour faire :
- `tenant.app_code = 'lesplendid'` distinct de `'marveline'` avec garantie d'isolation.
- Migration de données entre tenants (clone, fork, archivage).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Intégrité tenant (P0)

1. **F148** : ajouter `ForeignKey` dans `TenantMixin` :
   ```python
   class TenantMixin:
       tenant_id: Mapped[int] = mapped_column(
           BigInteger,
           ForeignKey("tenants.id", ondelete="RESTRICT"),
           nullable=False,
           index=True,
       )
   ```
   Migration Alembic : ajout des FK sur les 62 tables manquantes. Tester sur dev avec données réelles (pas de tenant_id orphelin) avant prod. **Préfixe** : avant d'ajouter la FK, scanner les données orphelines :
   ```sql
   SELECT t1.* FROM <table> t1 LEFT JOIN tenants t2 ON t1.tenant_id = t2.id WHERE t2.id IS NULL;
   ```
   Pour chaque table avec orphelins : décision (purge, réassignation au tenant 1 par défaut, archivage).

2. **F149, F156** : harmoniser tous les `id` et `tenant_id` en `BigInteger`. Migration Alembic table par table. Audit `grep -rn "Column(Integer\|mapped_column(Integer" app/models/`.

3. **F150** : soit retirer `to_dict` de `Base` et imposer une couche Pydantic, soit ajouter un champ `__cache_excluded_fields__: ClassVar[set[str]] = set()` :
   ```python
   class Base(DeclarativeBase):
       __cache_excluded_fields__: ClassVar[set[str]] = set()
       def to_dict(self, ...) -> dict:
           # ... mais filtre les champs dans __cache_excluded_fields__
   class Account(Base, TimestampMixin, SoftDeleteMixin):
       __cache_excluded_fields__ = {"hashed_password"}
   class MFADevice(Base, TimestampMixin):
       __cache_excluded_fields__ = {"encrypted_secret", "encrypted_dek"}
   ```
   Et **ne JAMAIS utiliser `to_dict` pour des réponses API** — toujours via Pydantic schemas.

### 5.2 Priorité 2 — Mixins enrichis (P1)

4. **F154** : étendre `SoftDeleteMixin` :
   ```python
   class SoftDeleteMixin:
       is_active: Mapped[bool] = mapped_column(Boolean, server_default="t", nullable=False)
       deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
       deleted_by_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
       def soft_delete(self, deleted_by_id: int) -> None:
           self.is_active = False
           self.deleted_at = datetime.now(timezone.utc)
           self.deleted_by_id = deleted_by_id
       def restore(self) -> None:
           self.is_active = True
           self.deleted_at = None
           self.deleted_by_id = None
   ```
   Migration Alembic : `ALTER TABLE ... ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE NULL; ADD COLUMN deleted_by_id BIGINT NULL;`. Backfill `deleted_at = updated_at` pour les rows `is_active=False` existantes (heuristique, pas exact).

5. **F157** : refactor 6 modèles (`formula`, `notification`, `tenant_settings`, `audit_log`, `account_session`, `trusted_device`, `user_role`, `product_maintenance`, `reservation_version`) pour utiliser `TenantMixin`. Préserver les autres colonnes mais déléguer `tenant_id` au mixin.

6. **F151** : ajouter `__repr__` standard sur `Base` :
   ```python
   def __repr__(self) -> str:
       parts = [f"id={getattr(self, 'id', '?')}"]
       if hasattr(self, "tenant_id"):
           parts.append(f"tenant_id={self.tenant_id}")
       return f"<{self.__class__.__name__} {', '.join(parts)}>"
   ```

7. **F153** : ajouter `CheckConstraint("tenant_id > 0", ...)` au `TenantMixin` via `__table_args__` injection, OU dans les modèles enfants. Approche `__table_args__` au mixin via `declared_attr` est complexe — alternative : convention validée via test au boot (énumère toutes les tables avec `tenant_id` et vérifie le check constraint).

### 5.3 Priorité 3 — Cohérence stylistique (P1)

8. **F155** : migrer tous les modèles 1.x untyped vers SQLAlchemy 2.0 typed. Audit avec `grep -rn "    id = Column" app/models/`. Une PR par domaine pour éviter les megacommits.

9. **F162** : ajouter une utility `Base.to_pydantic(schema_class)` :
   ```python
   def to_pydantic(self, schema: type[T]) -> T:
       return schema.model_validate(self, from_attributes=True)
   ```
   Évite la duplication dans les endpoints/services.

### 5.4 Priorité 4 — Hygiène (P2)

10. **F159** : refactor `to_dict` pour gérer Decimal/UUID/Enum en supprimant la duplication avec `cache.py:_DateEncoder`. Solution : `Base.to_dict` retourne déjà serializable, `cache.py` n'a plus besoin d'encoder custom.

11. **F160** : ajouter une convention `Index("ix_xxx_tenant_created", "tenant_id", "created_at")` dans les modèles append-heavy (notifications, audit_log, inventory_movements) — pas au mixin (chaque modèle décide).

12. **F163** : `is_active server_default="t"`.

13. **F165** : retirer le param `exclude_relations` non utilisé, ou l'implémenter (nécessaire pour éviter de cacher des relations chargées).

### 5.5 Tests à écrire avant refonte

- **F148** : pour chaque table avec `tenant_id`, INSERT avec `tenant_id=999999` doit échouer. Devrait actuellement passer.
- **F149** : assert `inspect(Tenant).columns["id"].type.python_type == int` ET pour toutes les tables `tenant_id`, `column.type == BigInteger` (pas `Integer`). Devrait échouer pour 6 modèles.
- **F150** : `Account(...).to_dict()` ne doit PAS contenir `hashed_password`. Devrait actuellement échouer (le contient).
- **F150 bis** : grep dans tout le code des appels à `<Model>.to_dict()` qui finissent dans une réponse API HTTP — devrait être 0 (toujours via Pydantic).
- **F154** : `Product.soft_delete(deleted_by_id=42)` doit set `is_active=False, deleted_at=now, deleted_by_id=42`.
- **F157** : assert que tous les modèles avec `tenant_id` héritent de `TenantMixin` (introspection MRO).

### 5.6 Hors-scope

- `BaseRepository` (qui consomme `to_dict`/`from_dict`) → module 06.
- `TenantBrand`, `TenantSettings`, `TenantMembership` modèles concrets → module 09.
- `Account`, `MFADevice`, `WebAuthnCredential` → modules 10, 12.

---

## 6. Verdict module 05

| Aspect | État |
|---|---|
| Convention 4 couches | Modèle = couche 1 (la base de tout). |
| Intégrité tenant | **Cassée** : pas de FK sur 62/64 tables (F148), 6 modèles avec `tenant_id Integer` au lieu de `BigInteger` (F149) |
| Sécurité sérialisation | **Trou** : `to_dict` expose tous les champs sans filtre, y compris `hashed_password`, `encrypted_secret`, etc. — utilisé pour cache Redis (F150) |
| Soft delete | **Incomplet** : pas de `deleted_at` ni `deleted_by_id` (F154) — impossible de purger par retention RGPD ou tracer le soft-delete dans la table elle-même |
| Cohérence | **Mixed** : SQLAlchemy 2.0 typed + 1.x untyped coexistent (F155), `id` parfois `Integer` (F156), `tenant_id` parfois redéfini hors mixin (F157) |
| Multi-brand | Neutre (le mixin n'est pas brand-aware) — voir modules 09 et suivants pour la sémantique multi-app |
| Dette | 20 nouvelles frictions : 3 P0, 8 P1, 6 P2, 3 P3 |

**Conclusion** : `models/base.py` est minimaliste (134 LoC pour 88 modèles) — c'est bien dans l'esprit "convention plutôt que configuration", mais **les 3 P0 (F148, F149, F150) sont des trous d'intégrité critiques** :
- Pas de FK = données potentiellement orphelines, RGPD impossible à garantir.
- Type hétérogène = bugs latents de scalabilité.
- `to_dict` qui expose les secrets = leak via cache Redis.

Avant tout audit RGPD réel ou refonte multi-brand, ces 3 fixes sont des prérequis. Le coût migration (62 FK à ajouter, 6 colonnes Integer → BigInteger) est conséquent mais reportable.

→ Module suivant : `06-repositories-base.md` (`app/repositories/base.py`, génériques + filtre tenant).
