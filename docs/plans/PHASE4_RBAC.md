# Phase 4 : RBAC - Roles, Permissions, Hierarchie

## Etat actuel

- 3 roles en enum : `admin`, `manager`, `staff`
- `require_role(*roles)` dans `deps.py` : verifie `user.role in allowed_roles`
- Pas de permissions granulaires, pas de hierarchie formelle
- Helpers sur User : `is_admin`, `is_manager`, `can_write`, `can_read`
- Tout est hardcode dans le code, aucune table en base

## Problemes identifies

1. **Pas de granularite** : un manager a acces a TOUT sauf users, ou RIEN
2. **Pas de hierarchie formelle** : `is_manager` retourne True pour admin par convention, pas par design
3. **Scoping flou** : `require_role(UserRole.ADMIN)` ne dit pas QUELLE permission est requise
4. **Extensibilite nulle** : ajouter un role (ex: `accountant`, `viewer`) = modifier du code partout
5. **Pas d'audit des permissions** : impossible de savoir qui a acces a quoi

## Architecture cible

### Choix : RBAC hierarchique code-defined + extensible DB

**Pourquoi pas full DB-backed ?**
- 3 roles, ~30 permissions : la complexite DB (admin UI, cache invalidation, migrations) n'est pas justifiee
- Le systeme de permissions code-defined est deterministe, testable, sans cache
- On structure le code pour migrer vers DB-backed plus tard si besoin (interface abstraite)

**Pourquoi pas rester sur le systeme actuel ?**
- Impossible d'ajouter des roles sans modifier N fichiers
- Pas de separation role/permission (violation SRP)
- Endpoints expriment "qui" (admin) au lieu de "quoi" (products:write)

### Modele de permissions

```
Permission = "{resource}:{action}"

Resources : products, categories, bundles, reservations, invoices,
            customers, inventory, users, sessions, audit, health

Actions   : read, write, delete, admin
```

**Liste exhaustive des permissions :**

| Permission             | Description                          |
|------------------------|--------------------------------------|
| products:read          | Consulter le catalogue               |
| products:write         | Creer/modifier des produits          |
| products:delete        | Supprimer des produits               |
| categories:read        | Consulter les categories             |
| categories:write       | Creer/modifier des categories        |
| categories:delete      | Supprimer des categories             |
| bundles:read           | Consulter les formules               |
| bundles:write          | Creer/modifier des formules          |
| bundles:delete         | Supprimer des formules               |
| reservations:read      | Consulter les reservations           |
| reservations:write     | Creer/modifier des reservations      |
| reservations:delete    | Annuler des reservations             |
| invoices:read          | Consulter les factures               |
| invoices:write         | Creer/modifier des factures          |
| customers:read         | Consulter les clients                |
| customers:write        | Creer/modifier des clients           |
| customers:delete       | Supprimer des clients                |
| inventory:read         | Consulter le stock                   |
| inventory:write        | Mouvements de stock                  |
| users:read             | Consulter les utilisateurs           |
| users:write            | Modifier des utilisateurs            |
| users:admin            | Creer/supprimer des utilisateurs     |
| sessions:read          | Consulter les sessions actives       |
| sessions:admin         | Revoquer des sessions                |
| audit:read             | Consulter les logs d'audit           |
| health:read            | Health checks (public)               |

### Hierarchie des roles

```
Level 100 : ADMIN    -> toutes les permissions
Level 50  : MANAGER  -> herite de STAFF + write/delete sur domaine metier
Level 10  : STAFF    -> read-only sur domaine metier
```

**Mapping role -> permissions :**

```python
ROLE_PERMISSIONS = {
    "staff": {
        "products:read", "categories:read", "bundles:read",
        "reservations:read", "invoices:read", "customers:read",
        "inventory:read", "health:read",
    },
    "manager": {
        # herite de staff +
        "reservations:write", "reservations:delete",
        "invoices:write",
        "customers:write", "customers:delete",
        "inventory:write",
    },
    "admin": {
        # herite de manager +
        "products:write", "products:delete",
        "categories:write", "categories:delete",
        "bundles:write", "bundles:delete",
        "users:read", "users:write", "users:admin",
        "sessions:read", "sessions:admin",
        "audit:read",
    },
}
```

**Resolution avec hierarchie :**
```python
def get_effective_permissions(role: str) -> set[str]:
    """Resout les permissions en incluant l'heritage hierarchique."""
    hierarchy = ["staff", "manager", "admin"]
    role_index = hierarchy.index(role)
    permissions = set()
    for i in range(role_index + 1):
        permissions |= ROLE_PERMISSIONS[hierarchy[i]]
    return permissions
```

### Fichiers a creer / modifier

```
CREER :
  app/core/permissions.py          # Permission enum + ROLE_PERMISSIONS + resolution
  tests/unit/test_permissions.py   # Tests hierarchie, resolution, edge cases

MODIFIER :
  app/core/deps.py                 # Ajouter require_permission(), garder require_role() en compat
  app/api/v1/endpoints/products.py # require_role() -> require_permission("products:write")
  app/api/v1/endpoints/categories.py
  app/api/v1/endpoints/bundles.py
  app/api/v1/endpoints/reservations.py
  app/api/v1/endpoints/invoices.py
  app/api/v1/endpoints/customers.py
  app/api/v1/endpoints/audit.py
  app/api/v1/endpoints/sessions.py
  app/api/v1/endpoints/auth.py     # Inclure permissions dans /me response
  app/schemas/auth.py              # UserInfo += effective_permissions: list[str]
  app/constants/security.py        # Ajouter Permission enum si on prefere le centraliser
```

### Design detaille

#### 1. Permission enum (`app/core/permissions.py`)

```python
from enum import Enum

class Permission(str, Enum):
    """Permissions granulaires format resource:action."""
    PRODUCTS_READ = "products:read"
    PRODUCTS_WRITE = "products:write"
    PRODUCTS_DELETE = "products:delete"
    # ... (toutes les permissions)

ROLE_HIERARCHY: list[str] = ["staff", "manager", "admin"]

ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "staff": { Permission.PRODUCTS_READ, ... },
    "manager": { Permission.RESERVATIONS_WRITE, ... },  # delta seulement
    "admin": { Permission.PRODUCTS_WRITE, ... },         # delta seulement
}

def get_effective_permissions(role: str) -> set[Permission]:
    """Permissions effectives avec heritage hierarchique."""
    ...

def has_permission(role: str, permission: Permission) -> bool:
    """Verifie si un role a une permission (avec heritage)."""
    return permission in get_effective_permissions(role)
```

#### 2. Dependency `require_permission` (`app/core/deps.py`)

```python
def require_permission(*permissions: Permission):
    """Factory : verifie que l'utilisateur a TOUTES les permissions requises."""
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_perms = get_effective_permissions(current_user.role)
        missing = set(permissions) - user_perms
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Permissions manquantes: {', '.join(str(p) for p in missing)}"
            )
        return current_user
    return dependency

# Type aliases mis a jour
ProductWriter = Annotated[User, Depends(require_permission(Permission.PRODUCTS_WRITE))]
ReservationManager = Annotated[User, Depends(require_permission(Permission.RESERVATIONS_WRITE))]
```

#### 3. Utilisation dans les endpoints

```python
# Avant (role-based, opaque) :
@router.post("", dependencies=[Depends(require_role(UserRole.ADMIN))])
def create_product(...): ...

# Apres (permission-based, explicite) :
@router.post("")
def create_product(
    current_user: User = Depends(require_permission(Permission.PRODUCTS_WRITE)),
    ...
): ...
```

#### 4. Enrichissement /me response

```python
class UserInfo(BaseSchema):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    tenant_id: int
    is_active: bool
    permissions: list[str]  # NOUVEAU : permissions effectives
    created_at: str | None
```

Cela permet au frontend de gerer l'affichage conditionnel (boutons, menus) sans hardcoder les roles.

### Retrocompatibilite

- `require_role()` reste fonctionnel (wrapper autour de require_permission)
- `CurrentUser`, `AdminUser`, `ManagerUser` type aliases conserves
- Les helpers `is_admin`, `can_write` sur User restent (deprecated progressivement)
- Aucune migration DB necessaire (les roles restent un string sur User)

### Tests requis

```
tests/unit/test_permissions.py :
  - test_staff_has_only_read_permissions
  - test_manager_inherits_staff_permissions
  - test_admin_inherits_all_permissions
  - test_unknown_role_raises_error
  - test_has_permission_positive
  - test_has_permission_negative
  - test_require_permission_allows_authorized
  - test_require_permission_blocks_unauthorized
  - test_require_permission_multiple_permissions_all_required
  - test_permissions_list_in_user_info
```

### Risques et mitigations

| Risque | Mitigation |
|--------|-----------|
| Regression endpoints | Tester chaque endpoint avec chaque role |
| Oubli de permission sur nouveau endpoint | Linter/test qui detecte les endpoints sans require_permission |
| Performance (resolution a chaque requete) | Resolution O(1) (3 roles, sets precalcules) |
| Confusion frontend | /me retourne permissions effectives |

### Estimation

- **Fichiers impactes** : ~15 (1 nouveau, 14 modifies)
- **Complexite** : Moyenne (refactoring systematique mais mecanique)
- **Risque** : Faible (retrocompatible, pas de migration DB)
