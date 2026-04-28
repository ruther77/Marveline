# Module 08 — Schemas base + common (Pydantic)

## 1. Périmètre

| Fichier | LoC | Rôle |
|---|---|---|
| `app/schemas/base.py` | 83 | `BaseSchema` (Pydantic config), `TimestampSchema`, `TenantSchema`, `SoftDeleteSchema`, `IDSchema`, `EntityResponseSchema` (mixins) |
| `app/schemas/common.py` | 191 | `PaginationParams`, `PaginatedResponse[T]`, `ErrorDetail`, `ErrorResponse`, `SuccessResponse`, `ImportRowError`, `ImportReport` |

**Total** : 274 LoC.

**Dépend de** : `pydantic.{BaseModel, ConfigDict, Field, field_validator}`, `app.constants.Limits` (pour `MAX_PAGE_SIZE`, `DEFAULT_PAGE_SIZE`).

**Dépendu par** : 66 sous-schemas métier (un par domaine — customer, product, reservation, devis, invoice, etc.).

---

## 2. Lecture par fichier

### 2.1 `base.py` (83 LoC)

#### `BaseSchema(BaseModel)` (lignes 8-28)
- `model_config = ConfigDict(...)` :
  - `from_attributes=True` — conversion ORM → DTO.
  - `populate_by_name=True` — accepte alias.
  - `str_strip_whitespace=True` — auto-strip.
  - `validate_assignment=True` — re-validation à l'assignation.
  - `json_encoders={Decimal: float}` — Decimal sérialisé en float (perte de précision !).
  - `json_schema_extra={"examples": []}` — overridable par enfants.

#### Mixins
- `TimestampSchema(BaseSchema)` (31-42) : `created_at`, `updated_at` (datetime, required).
- `TenantSchema(BaseSchema)` (45-52) : `tenant_id: int = Field(..., gt=0)`.
- `SoftDeleteSchema(BaseSchema)` (55-61) : `is_active: bool = True` (default, pas required).
- `IDSchema(BaseSchema)` (64-71) : `id: int = Field(..., gt=0)`.
- `EntityResponseSchema(IDSchema, TimestampSchema, TenantSchema, SoftDeleteSchema)` (74-83) : composition des 4 mixins (MRO).

### 2.2 `common.py` (191 LoC)

- `T = TypeVar("T")`.

#### `PaginationParams(BaseModel)` (12-40)
- `skip: int = Field(default=0, ge=0)`.
- `limit: int = Field(default=Limits.DEFAULT_PAGE_SIZE, ge=1)`.
- `@field_validator('limit') limit_max_1000` (lignes 36-40) : caps à `Limits.MAX_PAGE_SIZE`. **Silent capping** — pas de raise si > 1000.
- **Hérite de `BaseModel` directement, pas de `BaseSchema`** — pas de `from_attributes`, pas de `str_strip_whitespace`.

#### `PaginatedResponse(BaseSchema, Generic[T])` (43-90)
- `items: list[T]`, `total: int`, `skip: int`, `limit: int` (tous required).
- `@property has_more`, `@property page_count` — calculs dérivés non sérialisés.

#### `ErrorDetail(BaseModel)` (93-109)
- `field: Optional[str]`, `message: str`, `code: Optional[str]`.
- **Hérite de `BaseModel` directement** au lieu de `BaseSchema`.

#### `ErrorResponse(BaseModel)` (112-153)
- `detail: str`, `code: int (400-599)`, `errors: Optional[list[ErrorDetail]]`.
- Examples docstring (lignes 121-135) : format `{detail, code, errors}`.
- **Pas le format utilisé par `exception_handler.create_error_response`** (qui utilise `{success, error, message, detail, details, errors, request_id}` — cf F127 module 04). **Schemas et middlewares incohérents**.

#### `SuccessResponse(BaseModel)` (156-177)
- `success: bool = True`, `message: str`, `data: Optional[dict]`.
- `data: Optional[dict]` — type `dict` non typé (perte de typage).

#### `ImportRowError`, `ImportReport` (180-191)
- `ImportReport.errors: list[ImportRowError] = default_factory=list`.

### 2.3 Adoption observée dans les 66 sous-schemas

#### Statistiques (grep)
- **`from BaseSchema`** : 38 fichiers / 66 = **58% d'adoption**.
- **`from BaseModel` direct (Pydantic native)** : 123 classes — bypass de la convention.
- **`EntityResponseSchema` ou autres mixins** : seulement **13 fichiers** (api_key, reservation, loyalty, etc.) = ~20% d'adoption.
- **Redéclaration `model_config = ConfigDict(...)` malgré héritage** : **26 fichiers** dupliquent `from_attributes=True`.
- **Mix `model_config = ConfigDict(...)` (Pydantic 2.0)** vs **`model_config = {"from_attributes": True}` (dict raw, non typé)** : 24 vs 2 fichiers (notification.py, evenements.py).

#### Exemple de redéclaration redondante
`schemas/container.py` : 5 occurrences de `model_config = ConfigDict(from_attributes=True)` ligne 40, 79, 93, 126, 151 — alors que `BaseSchema` le fournit déjà.

---

## 3. Frictions identifiées

(Numérotation continue — F232 commence après le module 07.)

### 3.1 Frictions P0

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F232** | base | **`json_encoders={Decimal: float}` — perte de précision sur les montants** | `base.py:23` | `BaseSchema` configure tout DTO pour sérialiser `Decimal` → `float` JSON. Pour les **montants en centimes** (BigInteger), pas d'impact. **Mais** pour les montants en `Decimal` (taux de change, taux TVA fractionnel, ratios), `float(Decimal("0.20"))` peut donner `0.19999999999...` selon les opérations. Convention codebase : montants en centimes (cf F-mod05). Mais **certains champs Decimal existent** (à confirmer dans les modèles) — exposés à la perte de précision JSON. À auditer : `grep -rn "Decimal" app/models/`. À fixer : `json_encoders={Decimal: str}` (string-safe) ou supprimer (Pydantic 2.0 gère Decimal nativement). |
| **F233** | common | **`ErrorResponse` schema diverge du format réel des middlewares** | `common.py:112-153` (`{detail, code, errors}`) vs `middleware/exception_handler.py:43-58` (`{success, error, message, detail, details, errors, request_id}`) | 2 formats coexistent :<br>- `ErrorResponse` Pydantic — utilisé pour OpenAPI doc et certains endpoints qui le retournent explicitement.<br>- `create_error_response` middleware — utilisé pour les exceptions converties.<br>Frontend doit gérer les 2 formats. **Documentation OpenAPI erronée** : un endpoint qui déclare `responses={404: ErrorResponse}` ment au client — la vraie réponse contient `{success, error, message, ...}`. Cf F127 module 04. À unifier : `ErrorResponse` doit refléter exactement la sortie des middlewares. |

### 3.2 Frictions P1

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F234** | base | **Adoption `BaseSchema` à 58%** | grep stats : 234 classes via `BaseSchema`, 123 via `BaseModel` direct | 35% des schemas bypassent la base — perdent `str_strip_whitespace`, `populate_by_name`, encoders custom. Conséquences :<br>- Les inputs avec espaces autour ne sont pas trimés.<br>- Conversion ORM → DTO peut échouer si `from_attributes=False` par défaut.<br>- Configuration JSON encoders inconsistante.<br>Audit : `grep -rn "class.*BaseModel)" app/schemas/` puis migration une par une. |
| **F235** | base | **26 schemas redéclarent `model_config = ConfigDict(...)` malgré héritage** | `schemas/container.py` 5 fois, `schemas/audit.py` 3 fois, `schemas/damage_type.py`, `schemas/product_maintenance.py`, `schemas/deposit.py`, `schemas/notification.py`, `schemas/evenements.py`, … | Duplication de `from_attributes=True` (déjà dans `BaseSchema.model_config`). Si on change `BaseSchema.model_config`, les redéclarations écrasent. Cause probable : copy-paste avant que `BaseSchema` n'existe. À nettoyer : retirer toutes les redéclarations qui n'ajoutent rien. |
| **F236** | base | **Mix `ConfigDict(...)` (typé) vs `{"from_attributes": True}` (dict raw)** | `schemas/notification.py:20`, `schemas/evenements.py:31` (dict raw) vs reste (ConfigDict) | Pydantic 2.0 accepte les 2, mais le dict raw perd le typage IDE et la validation de clé. Convention non documentée. À harmoniser tout en `ConfigDict(...)` ou hériter de `BaseSchema`. |
| **F237** | base | **`SoftDeleteSchema.is_active: bool = True` default** | `base.py:58-61` | Pour un **schema d'entrée** (Create/Update), `is_active=True` par défaut force la création active. OK. **Mais** pour un **schema de réponse**, `is_active` peut être False (entité soft-deleted retournée via `include_inactive=True`). Le default ne reflète pas la valeur DB. À séparer en `SoftDeleteCreateSchema` (default True) vs `SoftDeleteResponseSchema` (required, lit la valeur DB). |
| **F238** | base | **Pas de schemas Create / Update / Response distincts dans la base** | `base.py:74-83` (`EntityResponseSchema` seul) | Convention REST/CRUD typique : `XxxCreate`, `XxxUpdate`, `XxxResponse` distincts. La base ne fournit que `EntityResponseSchema`. Chaque sous-schema doit définir ses propres `Create` et `Update` à la main. À ajouter :<br>```python<br>class CreateSchemaBase(BaseSchema):<br>    """Schema de création — pas de timestamps, pas d'ID, pas de tenant_id (déduit du context)."""<br><br>class UpdateSchemaBase(BaseSchema):<br>    """Schema de mise à jour — tous les champs optionnels."""<br>```<br>Et un mixin `PartialMixin` qui met tous les fields en `Optional` automatiquement. |
| **F239** | base | **`TenantSchema` exposé en réponse — leak `tenant_id`** | `base.py:45-52` ; consommé par `EntityResponseSchema` (74) → toute réponse d'entité expose `tenant_id` | Le `tenant_id` est une donnée interne d'isolation. Pour un user authentifié sur tenant 5, **chaque réponse contient `"tenant_id": 5`**. Pas un leak cross-tenant (le user connaît son propre tenant), mais :<br>(a) Pollue le payload JSON.<br>(b) Indique aux outils de fuzz/discovery l'architecture multi-tenant.<br>(c) Pour des intégrations B2B, expose un détail d'implémentation.<br>À séparer : `EntityResponseSchema` interne vs `PublicEntityResponseSchema` qui omet `tenant_id`. |
| **F240** | common | **`PaginationParams` hérite de `BaseModel` direct** | `common.py:12` | Pas de `from_attributes`, pas de `str_strip_whitespace`. Les inputs `?skip= 10 &limit= 50 ` (espaces) ne sont pas trimés. À hériter de `BaseSchema`. |
| **F241** | common | **`PaginationParams.limit_max_1000` silent cap** | `common.py:36-40` | Si client demande `limit=5000`, retourne `1000` sans erreur ni warning. Le client pense avoir reçu 5000 résultats mais en a 1000. **Mauvaise UX** + bug latent (pagination broken). À raise `ValueError(f"limit must be <= {MAX_PAGE_SIZE}")` ou retourner un header `X-Pagination-Capped: true`. |
| **F242** | common | **`SuccessResponse.data: Optional[dict]` non typé** | `common.py:174-177` | `dict` plain — perd le typage IDE/OpenAPI. Pour des actions retournant des données structurées (ex: `confirm_reservation` retourne le statut), pas de schema généré. À typer via Generic : `class SuccessResponse(BaseModel, Generic[T]): data: Optional[T]`. |
| **F243** | common | **`ErrorDetail`, `ErrorResponse`, `SuccessResponse`, `ImportRowError`, `ImportReport` héritent de `BaseModel` direct** | `common.py:93, 112, 156, 180, 187` | Bypass `BaseSchema`. Pas de `str_strip_whitespace`, pas de config commune. Convention codebase ignorée dans le module qui devrait la porter. |

### 3.3 Frictions P2

| ID | Couche | Friction | Citation | Impact |
|---|---|---|---|---|
| **F244** | base | `EntityResponseSchema` MRO peut générer des conflits | `base.py:74` (`EntityResponseSchema(IDSchema, TimestampSchema, TenantSchema, SoftDeleteSchema)`) | MRO : `IDSchema → TimestampSchema → TenantSchema → SoftDeleteSchema → BaseSchema → BaseModel → object`. Si un mixin redéfinit un field défini ailleurs (improbable ici), conflit silencieux. Pydantic 2.0 le gère mais documenté pas clair. À documenter l'ordre des mixins. |
| **F245** | base | `validate_assignment=True` peut causer perf hits | `base.py:22` | Re-validation à chaque assignation. Pour un endpoint qui fait `obj.field = value` en boucle, coût ×N. À documenter la convention "assignation rare". |
| **F246** | common | `ErrorResponse.code: int (400-599)` mais `ErrorMessages` utilise des codes string (`INVALID_CREDENTIALS`) | `common.py:143-148` vs `errors.py` codes string | Confusion : `code` est-il le HTTP status (400) ou l'error_code applicatif (`INVALID_CREDENTIALS`) ? Le doc dit "Code HTTP" mais l'usage dans le code utilise les 2. À clarifier en 2 champs : `http_status: int`, `error_code: str`. |
| **F247** | common | `PaginatedResponse.has_more` et `page_count` sont `@property` | `common.py:80-90` | Les `@property` Pydantic ne sont pas sérialisées en JSON par défaut (Pydantic 2 nécessite `@computed_field`). Le client ne reçoit donc PAS `has_more` ni `page_count`. À convertir en `@computed_field` ou retirer (caller doit calculer). |
| **F248** | base | Aucun mixin pour les schemas avec **soft delete + delete metadata** (F154 module 05) | `base.py` | `SoftDeleteSchema` n'a que `is_active`. Si on ajoute `deleted_at` et `deleted_by_id` au `SoftDeleteMixin` ORM (cf F154 module 05), pas de mirror schema. À synchroniser. |
| **F249** | common | `ImportReport.errors` peut grossir non-borné | `common.py:191` (`default_factory=list`) | Pour un import CSV de 10 000 lignes toutes en erreur, `errors` contient 10 000 entrées, payload JSON énorme. À paginer ou cap (`errors[:100]` + `truncated: bool`). |
| **F250** | base | `BaseSchema.model_config.json_schema_extra={"examples": []}` | `base.py:25-27` | Liste vide. Inutile sauf si chaque schéma override. Convention non utilisée dans le codebase (à confirmer). À retirer ou exemplifier. |

### 3.4 Frictions P3

| ID | Couche | Friction | Citation |
|---|---|---|---|
| **F251** | base | `Optional` importé mais non utilisé | `base.py:4` (`from typing import Optional` mais pas usage). |
| **F252** | base | Pas de `__all__` | `base.py` — exports implicites. Convention codebase utilise `__all__` ailleurs. |
| **F253** | common | `T = TypeVar("T")` pas borné | `common.py:9` — `T` non typé. À borner `T = TypeVar("T", bound=BaseModel)`. |
| **F254** | common | `ErrorResponse` exemples docstring dans la doc, pas dans `model_config.json_schema_extra` | `common.py:120-135` — docstring riche mais pas exploitable par OpenAPI. |

---

## 4. Dépendances inter-modules / fuites

### 4.1 Couplages observés

- `schemas/base` → `pydantic`, `decimal`, `datetime` (standard).
- `schemas/common` → `schemas/base.BaseSchema`, `app/constants/Limits` (saine).
- Tous les sous-schemas → `schemas/base` (via `BaseSchema` ou mixins).

### 4.2 Cycles évités

- Pas de cycle observé.

### 4.3 Forward-impact

- F237 (`SoftDeleteSchema.is_active default True`) impacte tous les schemas Create/Update qui en héritent — modules 14-25.
- F239 (`tenant_id` exposé) impacte toutes les réponses API — modules 14-35.
- F242 (`SuccessResponse.data: dict` non typé) impacte les endpoints qui retournent des données structurées via SuccessResponse.

### 4.4 Fuites Marveline / multi-brand

Module schemas neutre vs multi-brand — la convention Pydantic est agnostique.
**Mais** : aucune préparation pour les variations de schémas par brand (ex: Splendid avec champs CGV différents). Si on suit F195 module 07, les schemas `Reservation`, `Devis`, `Invoice` devront exposer `applicable_settings` ou similaire.

### 4.5 Confirmations forward

- **F127 module 04** confirmé ici (F233) : `ErrorResponse` schema ≠ `create_error_response` middleware format.
- **F154 module 05** : si on ajoute `deleted_at`/`deleted_by_id`, `SoftDeleteSchema` doit suivre (F248).

---

## 5. Recommandations de refonte

### 5.1 Priorité 1 — Format erreur unifié (P0)

1. **F233** : aligner `ErrorResponse` et `create_error_response` :
   ```python
   # schemas/common.py
   class ErrorResponse(BaseSchema):
       success: bool = False
       error: str = Field(..., description="Error code (ex: NOT_FOUND, INVALID_CREDENTIALS)")
       message: str = Field(..., description="Human-readable message")
       detail: str | dict = Field(..., description="Detail (str or structured dict)")
       details: Optional[dict] = None
       errors: Optional[list[ErrorDetail]] = None
       request_id: Optional[str] = None
   ```
   `middleware/exception_handler.create_error_response` doit retourner cette shape exactement.
   Tests : OpenAPI `responses={404: ErrorResponse}` doit générer un schema qui matche la réponse réelle.

### 5.2 Priorité 2 — Adoption BaseSchema (P1)

2. **F234, F243** : migration BaseModel → BaseSchema dans les 123 classes restantes :
   - Audit `grep -rn "class.*BaseModel\b" app/schemas/`.
   - PR par domaine pour éviter mégacommit.
   - Tests régression : pour chaque endpoint, vérifier que la réponse contient les mêmes clés/valeurs après migration.

3. **F235** : retirer les 26 redéclarations `model_config = ConfigDict(from_attributes=True)`. Audit `grep -A1 "class.*BaseSchema)" app/schemas/ | grep "ConfigDict"`.

4. **F236** : harmoniser tout en `ConfigDict(...)`. Convertir les 2 occurrences de dict raw.

### 5.3 Priorité 3 — Convention Create/Update/Response (P1)

5. **F238** : ajouter dans `base.py` :
   ```python
   class CreateSchemaBase(BaseSchema):
       """Schema de création — pas d'ID, pas de timestamps, pas de tenant_id."""
       pass

   class UpdateSchemaBase(BaseSchema):
       """Schema de mise à jour — partiel."""
       pass

   class ResponseSchemaBase(IDSchema, TimestampSchema):
       """Schema de réponse — sans tenant_id (interne)."""
       pass

   class FullResponseSchema(IDSchema, TimestampSchema, TenantSchema, SoftDeleteSchema):
       """Schema de réponse complet — pour les endpoints admin/internes uniquement."""
       pass
   ```
   Convention : endpoints publics retournent `ResponseSchemaBase` (sans tenant_id), endpoints admin retournent `FullResponseSchema`.

6. **F239** : par défaut, **ne PAS exposer `tenant_id`** dans les réponses publiques. `EntityResponseSchema` devient `_InternalEntityResponseSchema` (pour usage interne / debug). Endpoints publics utilisent `EntityResponseSchema` sans `tenant_id`.

7. **F237** : séparer `SoftDeleteSchema` :
   ```python
   class SoftDeleteCreateSchema(BaseSchema):
       is_active: bool = True
   class SoftDeleteResponseSchema(BaseSchema):
       is_active: bool = Field(...)  # required, reflète DB
   ```

### 5.4 Priorité 4 — Pagination robuste (P1)

8. **F241** : `PaginationParams.limit_max_1000` doit raise au lieu de capper silencieusement, OU retourner un header `X-Pagination-Capped` au niveau de la response.

9. **F247** : convertir `has_more` et `page_count` en `@computed_field` :
   ```python
   from pydantic import computed_field
   class PaginatedResponse(BaseSchema, Generic[T]):
       # ...
       @computed_field
       @property
       def has_more(self) -> bool:
           return (self.skip + self.limit) < self.total
       @computed_field
       @property
       def page_count(self) -> int:
           return (self.total + self.limit - 1) // self.limit if self.limit else 0
   ```

10. **F242** : typer `SuccessResponse.data` :
    ```python
    class SuccessResponse(BaseSchema, Generic[T]):
        success: bool = True
        message: str
        data: Optional[T] = None
    ```

### 5.5 Priorité 5 — Hygiène (P2-P3)

11. **F232** : enlever `json_encoders={Decimal: float}`. Si Decimal devient un cas d'usage, utiliser `str` :
    ```python
    json_encoders={Decimal: str}
    ```

12. **F246** : éclater `ErrorResponse.code` en 2 champs (`http_status: int`, `error_code: str`).

13. **F249** : `ImportReport.errors` capper à 100 entrées + flag `truncated: bool`.

14. **F250** : retirer `json_schema_extra={"examples": []}` ou commencer à le remplir.

15. **F253** : borner `T = TypeVar("T", bound=BaseModel)`.

16. **F252** : ajouter `__all__` dans `base.py` et `common.py`.

### 5.6 Tests à écrire avant refonte

- **F233** : test OpenAPI `endpoint_404_response_schema == ErrorResponse`. Devrait actuellement échouer.
- **F234** : `from app.schemas.X import XCreate ; assert issubclass(XCreate, BaseSchema)` pour tous les schemas. Devrait échouer pour ~35%.
- **F239** : pour chaque endpoint public, vérifier que `tenant_id` n'est PAS dans la réponse JSON. Devrait actuellement contenir.
- **F241** : `client.get("/api/v1/products?limit=5000")` doit retourner 422 (ou header `X-Pagination-Capped`). Devrait actuellement retourner 1000 résultats silencieusement.
- **F247** : `client.get("/api/v1/products")` réponse JSON doit contenir `has_more` et `page_count`. Devrait actuellement les omettre.

### 5.7 Hors-scope

- Sous-schemas métier (`customer.py`, `product.py`, etc.) → modules 14-25.
- `tenant_brand`, `auth.py` → modules 09-13.

---

## 6. Verdict module 08

| Aspect | État |
|---|---|
| Convention 4 couches | Schemas = couche 3 (DTO entre service et endpoint). Mixins définis (`IDSchema`, `TenantSchema`, `TimestampSchema`, `SoftDeleteSchema`, `EntityResponseSchema`). |
| Adoption | **Faible** : 58% des schemas utilisent `BaseSchema`, 20% utilisent les mixins, 26 fichiers redéclarent `ConfigDict` superflument |
| Cohérence formats | **Cassée** : `ErrorResponse` (schema) ≠ `create_error_response` (middleware) — 2 formats erreur en parallèle (F233) |
| Sécurité données | **Leak `tenant_id` dans toutes les réponses** (F239), `Decimal → float` perte précision (F232) |
| Pagination | **Silent capping** à 1000 (F241), `has_more`/`page_count` non sérialisés (F247) |
| Multi-brand | Neutre — pas de couplage Marveline/Splendid à ce niveau |
| Dette | 23 nouvelles frictions : 2 P0, 10 P1, 7 P2, 4 P3 |

**Conclusion** : `schemas/base.py` + `common.py` proposent une **base correcte** (mixins par domaine, config Pydantic 2.0, types pagination/erreur génériques) mais **l'adoption à 58% trahit la convention** : 35% des schemas redéfinissent leur `model_config` localement, dupliquent `from_attributes=True`, ou bypassent complètement `BaseSchema` pour hériter directement de `BaseModel`. Le résultat est un codebase où **la convention « schemas isolés » existe sur le papier mais pas dans la pratique**.

Le P0 critique (F233) — incohérence `ErrorResponse` schema vs middleware — doit être traité avant tout déploiement public où la doc OpenAPI est utilisée par des intégrateurs (générateur de SDK, tests contractuels).

→ Module suivant : `09-tenant-multi-app-brand.md` — **CRITIQUE** pour la séparation Marveline/Splendid (Tenant model, TenantBrand, TenantSettings, TenantMembership, app_code, brand_code, provisioning).
