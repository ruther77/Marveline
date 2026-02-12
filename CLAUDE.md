# CLAUDE.md — CaroCorp Dev Playbook
# Version: 2.0
# Statut: Obligatoire – Niveau Entreprise Réglementée
# Portée: Tous contributeurs humains & IA
# Environnements: Dev, Staging, Production

---

# PARTIE A — Règles d'interaction IA

## A.1 Stratégie d'écriture de code

1. **Edit simple d'abord** : privilégier l'édition ciblée quand elle suffit.
2. **Réécriture si l'édit ne suffit pas** : créer le fichier dans une version `.new`, comparer les deux versions, garder la meilleure, supprimer l'autre.
3. **Inspection avant écriture** : toujours lire le fichier cible ET ses imports/dépendances avant de modifier quoi que ce soit. Vérifier les noms de fonctions, variables, classes existantes pour éviter toute erreur de nommage.

## A.2 Complétude obligatoire

4. **Pas de sous-engineering** : si une erreur apparaît parce qu'un élément manque (service, helper, config, dépendance), le créer immédiatement plutôt que contourner ou ignorer.
5. **`__init__.py` toujours à jour** : chaque variable, fonction, classe ou workflow créé doit être immédiatement ajouté dans le `__init__.py` correspondant. Rien ne doit manquer à l'export.

## A.3 Tests

6. **Minimum de mocks** : préférer les implémentations réelles. Ne mocker que ce qui est strictement impossible à instancier (services externes, réseau). Créer les fixtures, factories et helpers nécessaires plutôt que mocker.

## A.4 Gouvernance IA

- Doit générer tests pour tout code produit.
- Doit générer migration safe (expand/contract).
- Doit refuser toute violation sécurité ou multi-tenant.
- Doit documenter les décisions architecturales.
- Interdiction de générer du code avec secret hardcodé.
- Doit proposer un plan de rollback si changement risqué.
- Si doute architectural → demander clarification.
- **❌ INTERDICTION ABSOLUE de mentionner son nom (Claude, Claude Sonnet, etc.) dans les fichiers, commits, documentation ou commentaires de code.**

## A.5 Langue

- Répondre en français.
- Code et identifiants techniques restent en anglais.

## A.6 Utilisation Systématique des Constantes (CRITIQUE)

### Directive Obligatoire

**AVANT TOUTE MODIFICATION DE CODE** :

1. ✅ **Consulter** `app/constants/` pour vérifier si une constante existe déjà
2. ✅ **Utiliser** les constantes existantes (jamais de strings hardcodées)
3. ✅ **Créer** de nouvelles constantes si nécessaire
4. ✅ **Vérifier** l'orthographe en se référant TOUJOURS au package `constants`

**INTERDICTION ABSOLUE** : Écrire des valeurs litérales pour des concepts métier, erreurs, headers, ou configurations qui sont utilisés plusieurs fois dans le code.

### Quand Créer une Nouvelle Constante

Créer une constante si **au moins un critère** est vrai :

- La valeur est utilisée **≥ 2 fois** dans le code
- C'est une **valeur métier** (statuts, catégories, types)
- C'est un **message d'erreur** standardisé
- C'est une **configuration** (limites, timeouts, seuils)
- C'est un **header HTTP** ou **clé Redis**
- C'est une **URL/endpoint** ou **méthode HTTP**

### Procédure de Création

```python
# 1. Identifier le fichier approprié dans app/constants/
#    - app/constants/business.py : ProductCategory, ReservationStatus, UserRole
#    - app/constants/errors.py : ErrorMessages, HTTPStatusMessages
#    - app/constants/security.py : SecurityHeaders, RedisKeys
#    - app/constants/http.py : HTTPMethods, PublicEndpoints
#    - app/constants/limits.py : Limits

# 2. Ajouter la constante dans le fichier approprié avec docstring
# Exemple : app/constants/errors.py
class ErrorMessages:
    """Messages d'erreur HTTP standardisés."""
    PRODUCT_NOT_FOUND = "Product not found"  # ✅ Documenté, réutilisable

# 3. Exporter dans app/constants/__init__.py si nouvelle classe
from app.constants.errors import ErrorMessages

__all__ = ["ErrorMessages", ...]

# 4. Utiliser dans le code
from app.constants import ErrorMessages

raise HTTPException(
    status_code=404,
    detail=ErrorMessages.PRODUCT_NOT_FOUND  # ✅ Pas de typo possible
)
```

### Exemples INTERDITS ❌ vs OBLIGATOIRES ✅

**❌ INTERDIT** :
```python
# Strings hardcodées répétées
if product.category == "assiette":  # Typo possible : "asiette"
    ...

raise HTTPException(status_code=404, detail="Product not found")
raise HTTPException(status_code=404, detail="Product not fonud")  # Typo !
```

**✅ OBLIGATOIRE** :
```python
from app.constants import ProductCategory, ErrorMessages

if product.category == ProductCategory.ASSIETTE:  # Autocomplétion IDE
    ...

raise HTTPException(status_code=404, detail=ErrorMessages.PRODUCT_NOT_FOUND)
```

### Organisation de `app/constants/` (Package Modulaire)

Le package est structuré en **5 fichiers spécialisés** par domaine :

```
app/constants/
├── __init__.py          # Exports centralisés (API publique)
│
├── business.py          # CONSTANTES MÉTIER (Business Logic)
│   ├── ProductCategory, ProductCondition, CustomerType
│   ├── ReservationStatus, InvoiceStatus, PaymentMethod
│   └── UserRole (RBAC)
│
├── errors.py            # MESSAGES D'ERREUR (Error Messages)
│   ├── ErrorMessages (21 messages standardisés)
│   └── HTTPStatusMessages
│
├── security.py          # SÉCURITÉ & AUTHENTIFICATION (Security & Auth)
│   ├── SecurityHeaders (13 constantes)
│   └── RedisKeys (6 préfixes + 5 helpers)
│
├── http.py              # HTTP & API (HTTP & API)
│   ├── HTTPMethods (7 méthodes + 2 sets)
│   └── PublicEndpoints (4 endpoints + helper)
│
└── limits.py            # LIMITES & CONFIGURATIONS (Limits & Config)
    └── Limits (12 constantes pagination, sécurité, rate limiting)
```

**Avantages de la structure modulaire** :
- Fichiers plus petits et plus faciles à comprendre (~150 lignes max)
- Séparation claire des responsabilités par domaine
- Facilite l'ajout de nouveaux domaines (ex: `notifications.py`, `emails.py`)
- Imports restent simples grâce à `__init__.py` : `from app.constants import ProductCategory`
```

### Workflow de Développement avec Constantes

**Phase 1 : AVANT d'écrire du code**
```bash
# Consulter le package constants/ pour voir ce qui existe
grep -ri "product" app/constants/
# Ou consulter un fichier spécifique
cat app/constants/business.py  # Pour les Enums métier
cat app/constants/errors.py    # Pour les messages d'erreur
```

**Phase 2 : PENDANT l'écriture**
```python
# Utiliser l'autocomplétion IDE
from app.constants import ProductCategory  # Import explicite

product.category = ProductCategory.ASSIETTE  # IDE propose ASSIETTE, VERRE, etc.
```

**Phase 3 : APRÈS modification de code**
```bash
# Vérifier qu'aucune string hardcodée n'a été introduite
grep -r '"draft"' app/ tests/ | grep -v "constants/"
grep -r '"confirmed"' app/ tests/ | grep -v "constants/"
```

### CAS SPÉCIAUX

#### ⚠️ CHECK Constraints SQL (ATTENTION)

**INTERDICTION** : Ne JAMAIS utiliser les Enums Python dans les CHECK constraints SQL.

```python
# ❌ INTERDIT - SQL ne comprend pas Python
CheckConstraint(
    f"customer_type IN ({CustomerType.INDIVIDUAL}, {CustomerType.COMPANY})",
    name="check_customer_type_valid"
)

# ✅ OBLIGATOIRE - Strings SQL pures
CheckConstraint(
    "customer_type IN ('individual', 'company')",
    name="check_customer_type_valid"
)
```

**Raison** : Les CHECK constraints sont exécutées par PostgreSQL, pas par Python. Les Enums n'existent que dans le code applicatif.

#### ⚠️ Migrations Alembic

Dans les migrations Alembic, utiliser directement les valeurs string (pas les Enums) car Alembic génère du SQL pur.

```python
# Migration : OK d'utiliser strings
op.execute("UPDATE products SET category='autre' WHERE category IS NULL")
```

### Checklist Quotidienne

Avant chaque commit :

- [ ] Aucune string hardcodée pour concepts métier
- [ ] Tous les messages d'erreur utilisent `ErrorMessages` (app/constants/errors.py)
- [ ] Tous les statuts utilisent les Enums appropriés (app/constants/business.py)
- [ ] Les nouveaux concepts métier sont dans le fichier approprié de `app/constants/`
- [ ] Les CHECK constraints SQL utilisent des strings litérales (pas d'Enums)
- [ ] Les imports sont présents (`from app.constants import ...`)
- [ ] Si nouvelle classe créée, elle est exportée dans `app/constants/__init__.py`

### Bénéfices

- ✅ **Sécurité** : Typos impossibles (autocomplétion IDE)
- ✅ **Maintenabilité** : Single source of truth
- ✅ **Refactoring** : Rename symbol fonctionne
- ✅ **Documentation** : Docstrings centralisées
- ✅ **Tests** : Validation au niveau des types (mypy/pylance)

---

# PARTIE B — Principes Directeurs

## B.1 Philosophie d'Ingénierie

- La production est l'environnement de référence.
- La sécurité est un standard, pas une option.
- L'isolation multi-tenant est sacrée.
- Toute action doit être observable.
- Le code est une dette tant qu'il n'est pas testé.
- La simplicité prime sur l'ingéniosité.
- Explicite > implicite.
- Aucun effet de bord caché.
- Toute mutation doit être idempotente si déclenchée via réseau.

## B.2 Sécurité par Défaut

- Zero Trust Architecture.
- Least Privilege Everywhere.
- Défense en profondeur.
- Auditabilité complète.
- Séparation stricte des environnements.
- Aucune confiance implicite interne.

## B.3 Scalabilité Contrôlée

- Stateless API uniquement.
- Horizontal scaling obligatoire.
- Aucune dépendance locale disque.
- Externalisation stockage (S3-like).
- File queues pour tâches lourdes.
- Circuit breaker pour services externes.

## B.4 Framework de décision

Avant d'introduire une nouvelle dépendance, service, abstraction ou pattern architectural, documenter :
- Le problème mesurable.
- Pourquoi l'existant ne suffit pas.
- L'impact opérationnel.
- Le plan de rollback.
- L'impact sécurité.

Aucun changement architectural non documenté n'est autorisé.

---

# PARTIE C — Architecture CaroCorp

## C.1 Stack Technique

- **Backend** : FastAPI + SQLAlchemy 2.0 + Pydantic 2.x
- **Base de données** : PostgreSQL 16 (port 5433)
- **ORM** : SQLAlchemy 2.0 avec Mapped types
- **Migrations** : Alembic
- **Tests** : pytest + fixtures
- **Frontend** : React + TypeScript (à venir Phase 3)

## C.2 Patterns Architecturaux

### Montants Monétaires
- **TOUJOURS en BigInteger centimes**
- 250 = 2.50€
- Évite les erreurs d'arrondi Float/Decimal
- Cohérence avec MassaCorp

### Multi-Tenant
- `tenant_id NOT NULL` sur toute table métier
- Index composite `(tenant_id, colonne_unique)`
- Isolation stricte testée (voir tests/e2e/test_workflows.py)

### Soft Delete
- `is_active BOOLEAN` via SoftDeleteMixin
- Ne jamais supprimer physiquement les données métier
- Préserver l'historique pour audit

### Timestamps
- `created_at`, `updated_at` via TimestampMixin
- `NOT NULL` avec `server_default=now()`

## C.3 Foreign Keys

### RESTRICT (Protéger données)
- `reservations.customer_id → customers.id`
- `reservation_lines.product_id → products.id`
- Empêche suppression accidentelle de données référencées
- **SQLAlchemy** : `passive_deletes=True` sans cascade

### CASCADE (Nettoyer automatiquement)
- `reservation_lines.reservation_id → reservations.id`
- `invoices.reservation_id → reservations.id`
- Suppression en cascade des données enfants

## C.4 Indexes Performance

- **Tous les tenant_id** : Index obligatoire
- **Toutes les foreign keys** : Index obligatoire
- **Colonnes filtrées fréquemment** : Index composite
- Vérifier avec `EXPLAIN ANALYZE`

## C.5 API Haute Disponibilité

- Load balancer.
- Autoscaling horizontal.
- Timeout strict sur appels internes.
- Idempotency obligatoire pour mutations réseau.

## C.6 Base de Données

- Primary + replica(s).
- Backups journaliers.
- PITR activé.
- Monitoring connexions.
- Pooling obligatoire.

## C.7 Workers

- File queue persistante.
- Dead Letter Queue.
- Retry exponentiel.
- Traitement idempotent.

## C.8 Organisation du dépôt

Le domaine ne dépend jamais de l'infrastructure. Les accès base de données sont isolés dans l'infrastructure. Aucune logique métier dans les controllers. Aucune dépendance croisée non justifiée.

---

# PARTIE D — Multi-Tenant (Règle Absolue)

- `tenant_id NOT NULL` sur toute table métier.
- Index composite `(tenant_id, id)`.
- Row-level isolation testée.
- Filtre tenant obligatoire au niveau repository.
- Tests automatiques anti-cross-tenant obligatoires.
- Interdiction de requêtes globales sans justification écrite.
- Audit log cross-tenant interdit.

**Violation = incident critique P0.**

---

# PARTIE E — Sécurité

## E.1 Authentification

- Hash Argon2 ou bcrypt.
- Rotation des tokens.
- Expiration courte des access tokens.
- MFA obligatoire pour : Admin, Accès production, Accès billing.

## E.2 Autorisation

- RBAC strict, rôles définis explicitement, aucun rôle implicite.
- ABAC optionnel pour contextes sensibles.
- Principe du moindre privilège.
- Vérification systématique côté backend.

## E.3 Journalisation des accès

Tout accès à donnée sensible = logué.

## E.4 Secrets & Clés

- Aucun secret en code.
- Vault obligatoire.
- Rotation automatique.
- Clés JWT rotation périodique.
- Séparation clés dev / prod.
- Clés asymétriques recommandées.

## E.5 Chiffrement

- En transit : TLS 1.2 minimum, HSTS activé.
- Au repos : DB chiffrée, sauvegardes chiffrées, champs sensibles chiffrés applicativement si critique.

## E.6 Protection Applicative (OWASP Top 10)

- Injection, Broken auth, XSS, CSRF, SSRF, Mass assignment couverts.
- Rate limiting : Login, Password reset, API publique.
- Protection brute force : Lock temporaire + Alerting.

---

# PARTIE F — Standards de Code

## F.1 Lisibilité

- Pas d'abréviations obscures.
- Pas de nombres magiques.
- Pas de logique implicite.
- Pas de dépendance cachée.

## F.2 Complexité

- Fonction < 40 lignes.
- Une fonction = une responsabilité.
- Pas plus de 3 niveaux d'imbrication.
- Pas de logique métier dans les DTO.

## F.3 Exceptions

- Jamais de catch silencieux.
- Toute erreur doit être loggée.
- Messages d'erreur non techniques côté client.

---

# PARTIE G — Base de Données

## G.1 Conventions

- `snake_case`.
- Pluriel pour tables.
- `created_at`, `updated_at` obligatoires.
- `is_active` pour soft delete (pas deleted_at).

## G.2 Migrations (expand/contract)

1. Ajout colonne nullable.
2. Backfill.
3. Mise à jour code.
4. Suppression legacy.

Jamais de migration destructive directe.

## G.3 Performance

- Toute requête > 100ms doit être analysée.
- Index obligatoire pour colonnes filtrées.
- N+1 interdit.
- Profiling régulier.

---

# PARTIE H — Tests

## H.1 Pyramide

- 70% unitaires.
- 20% intégration.
- 10% e2e.

## H.2 Règles

- Toute règle métier critique testée.
- Tests anti-régression obligatoires.
- Minimum de mocks (implémentations réelles préférées).
- Tests isolés du réseau externe.
- Tests anti-cross-tenant obligatoires.

## H.3 Couverture

- Minimum global : 80%.
- Modules critiques : 95%.

## H.4 Structure CaroCorp

```
tests/
├── unit/           # Tests unitaires modèles, services
├── integration/    # Tests endpoints API
├── e2e/           # Tests workflows complets
└── security/      # Tests sécurité, multi-tenant
```

---

# PARTIE I — Observabilité

## I.1 Logs

Format structuré JSON : `tenant_id`, `user_id`, `trace_id`, `request_id`.

## I.2 Audit Log Immuable

Table append-only : `user_id`, `tenant_id`, `action`, `entity`, `entity_id`, `timestamp`, `IP`, `user_agent`. Interdiction de suppression d'audit.

## I.3 Metrics (RED method)

- Rate, Errors, Duration.
- API latency, Error rate, DB saturation, Queue backlog, Auth failures.

## I.4 Alerting

- Spike 5xx.
- Spike latence.
- Spike login failures.
- Spike accès admin.
- Saturation DB.
- Échec backup.

## I.5 Centralisation

- Logs centralisés.
- Retention policy définie.
- Monitoring sécurité.

---

# PARTIE J — Workflow Git

## J.1 Branching

- `main` → production.
- `develop` → intégration.
- `feature/*` → développement.
- `hotfix/*` → correctif production.
- `release/*` → préparation release.

Interdiction de commit direct sur `main`.

## J.2 Pull Requests

Une PR est valide uniquement si :
- Liée à un ticket.
- Tests inclus.
- Migration incluse si nécessaire.
- Description claire du changement.
- Impact sécurité mentionné.
- Plan de rollback documenté.
- CI au vert.
- Minimum 1 review approuvée.

## J.3 Versioning sémantique

`MAJOR.MINOR.PATCH`. Aucune breaking change sans version majeure, migration documentée, communication interne.

---

# PARTIE K — CI/CD

## K.1 Pipeline CI

- Lint.
- Typecheck.
- Tests unitaires + intégration.
- SAST + Scan dépendances + Scan secrets.
- Vérification migrations.
- Build.

## K.2 Déploiement

- Aucun déploiement manuel en prod.
- Environnement staging obligatoire.
- Déploiement blue/green.
- Rollback en < 5 minutes.
- Approval double pour production.
- Feature flags recommandés.
- Journalisation déploiements.

---

# PARTIE L — RGPD & Conformité

- Export données utilisateur.
- Droit à l'effacement.
- Journal suppression.
- Politique rétention.
- Data minimization by design.

---

# PARTIE M — Gestion des Incidents

## M.1 Classification

- **P0** – Fuite de données.
- **P1** – Indisponibilité majeure.
- **P2** – Bug fonctionnel critique.
- **P3** – Bug mineur.

## M.2 Process

Détection → Containment → Correction → Root cause analysis → Post-mortem documenté.

---

# PARTIE N — Règles Absolues Non Négociables

- Aucune donnée cross-tenant.
- Aucune mutation non auditée.
- Aucun secret en clair.
- Aucun endpoint sans contrôle auth.
- Aucun accès prod non tracé.
- Aucune dépendance non scannée.
- Aucun déploiement sans CI verte.
- Aucune migration destructive directe.
- **Aucune mention du nom de l'IA dans les fichiers, commits ou documentation.**

---

# PARTIE O — Discipline Opérationnelle (Ajouté 2026-02-12)

Issue de l'audit rétrospectif des 5 premiers jours de développement (CaroCorp + CaroCorp_new).
Chaque règle adresse un anti-pattern observé et documenté.

## O.1 Ordre de priorité des tâches

```
1. Corriger les bugs connus (P0/P1)
2. Nettoyer les fichiers orphelins/backup
3. Écrire les tests manquants pour le code existant
4. Organiser la documentation existante
5. Seulement ensuite : nouvelles features
```

## O.2 Définition de "Terminé" (Definition of Done)

Une feature est terminée si et seulement si TOUS ces critères sont remplis :

| # | Critère | Preuve exigée |
|---|---------|---------------|
| 1 | Code produit écrit | Fichiers dans `app/` |
| 2 | Tests unitaires écrits ET persistés | `tests/test_<feature>.py` existe |
| 3 | Tests passent | Sortie `pytest` avec 0 failures |
| 4 | Endpoint vérifié | Pas de 500 sur les routes touchées |
| 5 | `__init__.py` à jour | Exports vérifiés |
| 6 | Migration appliquée (si applicable) | `alembic upgrade head` sans erreur |
| 7 | Constantes utilisées | Pas de strings hardcodées (cf. Partie A.6) |
| 8 | Fichiers backup nettoyés | Pas de `.bak`, `.backup`, `.new` dans le repo |
| 9 | MEMORY.md mis à jour | Avec chemins de fichiers réels et date de vérification |

## O.3 Cadence de livraison

- Maximum 2 features par session de travail
- Chaque feature est complétée (tous critères O.2) avant de passer à la suivante
- Si une feature dépasse 10 fichiers modifiés : la découper en incréments

## O.4 Vérifiabilité de la mémoire

Toute information écrite dans MEMORY.md doit être :
- **Datée** : `(vérifié YYYY-MM-DD)`
- **Sourcée** : chemin du fichier ou commande de vérification
- **Scopée** : strictement limitée à CaroCorp_new (pas de cross-projet)

Format obligatoire pour les résultats de tests :
```
Tests: N/N pass — fichier: tests/test_X.py (vérifié YYYY-MM-DD)
```

## O.5 Hygiène du repo

- Pas de fichiers `.bak`, `.backup`, `.bak2` dans le repo
- `htmlcov/` dans `.gitignore` (artefact de build)
- Documentation dans `docs/` (pas à la racine)
- Pas de `__pycache__` commités

## O.6 Anti-patterns interdits

| Anti-pattern | Description | Remédiation |
|-------------|-------------|-------------|
| Documentation-fleuve | 16 fichiers .md (5168 lignes) à la racine | Organiser dans docs/ par thème |
| Backup oubliés | 9 fichiers .bak/.backup laissés dans le repo | Nettoyer après chaque refactoring |
| Plan verbal | Plan en chat → oublié par compression | TaskCreate ou fichier persistant |
| Vélocité > Qualité | Features livrées sans vérification complète | DoD complet avant passage |
| Doctrine ≠ Pratique | Règles écrites non appliquées | Appliquer ou supprimer |

## O.7 Backlog technique actuel (2026-02-12)

**P1 — Nettoyage :**
- [ ] Supprimer 9 fichiers .bak/.backup orphelins
- [ ] Déplacer 16 fichiers .md racine → `docs/` organisé
- [ ] Ajouter `htmlcov/` au .gitignore
- [ ] Vérifier que les 318 tests passent réellement (run pytest)

**P2 — Améliorations :**
- [ ] Couverture cible 90% (actuellement reporté 88.88%, non vérifié live)
- [ ] Supprimer `app/constants.py.backup`
