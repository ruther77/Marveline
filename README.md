# Marveline - Location de Vaisselle & Materiel Evenementiel

**Version** : 0.1.0
**Statut** : En developpement

---

## Description

Marveline est une application de gestion de location de vaisselle et materiel evenementiel (assiettes, verres, couverts, nappes, mobilier, candy bar, etc.).

### Fonctionnalites

- **Catalogue produits** : gestion des articles, categories et formules (bundles)
- **Reservations** : planification et suivi des evenements clients
- **Inventaire** : stock temps reel et mouvements
- **Facturation** : generation de factures
- **Clients** : base clients avec historique
- **Agenda** : vue calendrier des reservations
- **Administration** : gestion utilisateurs, sessions, audit logs
- **Securite** : MFA (TOTP), RBAC, rate limiting, protection brute force, isolation multi-tenant

---

## Stack technique

| Couche       | Technologie                              |
|-------------|------------------------------------------|
| Backend     | FastAPI + SQLAlchemy 2.0 + Pydantic 2.x |
| Base de donnees | PostgreSQL 16                       |
| Migrations  | Alembic                                  |
| Cache       | Redis                                    |
| Workers     | Celery + Redis (broker)                  |
| Frontend    | React 18 + TypeScript + Vite             |
| Infra       | Docker Compose                           |

---

## Quick Start

### Prerequis

- Docker & Docker Compose
- Git

### Demarrage

```bash
# Cloner le repo
git clone https://github.com/ruther77/Marveline.git
cd Marveline

# Configurer les variables d'environnement
cp .env.example .env  # adapter les valeurs

# Demarrer les services
docker compose up -d

# API disponible sur
# http://localhost:8001/docs (Swagger UI)

# Frontend disponible sur
# http://localhost:3000
```

### Services Docker

| Service         | Port  | Description               |
|----------------|-------|---------------------------|
| `api`          | 8001  | API FastAPI               |
| `frontend`     | 3000  | Interface React           |
| `db`           | 5432  | PostgreSQL 16             |
| `redis`        | 6379  | Cache & message broker    |
| `celery-worker`| -     | Taches asynchrones        |

---

## Structure du projet

```
.
├── app/
│   ├── api/v1/endpoints/    # Endpoints REST
│   ├── core/                # Config, securite, deps
│   ├── constants/           # Constantes metier
│   ├── middleware/           # Audit, securite, metrics
│   ├── models/              # Modeles SQLAlchemy
│   ├── repositories/        # Couche acces donnees
│   ├── schemas/             # Schemas Pydantic
│   ├── services/            # Logique metier
│   ├── tasks/               # Taches Celery
│   └── utils/               # Utilitaires
├── alembic/                 # Migrations DB
├── frontend/
│   └── src/
│       ├── api/             # Clients API
│       ├── components/      # Composants React
│       ├── pages/           # Pages (admin, agenda, auth, events, inventory, products, profile)
│       ├── hooks/           # Custom hooks
│       ├── stores/          # State management
│       ├── types/           # Types TypeScript
│       └── errors/          # Error handling
├── tests/
│   ├── unit/                # Tests unitaires
│   ├── integration/         # Tests d'integration
│   ├── security/            # Tests securite & multi-tenant
│   ├── e2e/                 # Tests end-to-end
│   └── load/                # Tests de charge (k6)
├── docs/                    # Documentation
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

---

## API Endpoints

| Module          | Prefix                  | Description                 |
|----------------|-------------------------|-----------------------------|
| Auth           | `/api/v1/auth`          | Authentification, tokens    |
| MFA            | `/api/v1/mfa`           | Multi-factor authentication |
| Sessions       | `/api/v1/sessions`      | Gestion des sessions        |
| Products       | `/api/v1/products`      | Catalogue produits          |
| Categories     | `/api/v1/categories`    | Categories produits         |
| Bundles        | `/api/v1/bundles`       | Formules / packs            |
| Reservations   | `/api/v1/reservations`  | Reservations evenements     |
| Customers      | `/api/v1/customers`     | Gestion clients             |
| Invoices       | `/api/v1/invoices`      | Facturation                 |
| Audit          | `/api/v1/audit`         | Logs d'audit                |
| Health         | `/api/v1/health`        | Health check & metrics      |

---

## Tests

```bash
# Lancer tous les tests
docker compose run --rm --entrypoint "" api python -m pytest tests/ -v

# Tests unitaires uniquement
docker compose run --rm --entrypoint "" api python -m pytest tests/unit/ -v

# Tests securite
docker compose run --rm --entrypoint "" api python -m pytest tests/security/ -v

# Tests de charge (necessite k6)
cd tests/load && bash run_load_tests.sh
```

---

## Securite

- Authentification JWT avec rotation de tokens
- MFA via TOTP (compatible Google Authenticator)
- Hachage Argon2 des mots de passe
- Protection brute force avec lockout progressif
- Rate limiting par endpoint
- RBAC (Role-Based Access Control)
- Isolation multi-tenant stricte (`tenant_id` sur toute table metier)
- Audit log signe (HMAC-SHA256)
- Validation inputs (SQL injection, XSS, path traversal)

---

## Conventions

- Montants monetaires en **centimes** (BigInteger) : `250` = 2.50 EUR
- Soft delete via `is_active` (jamais de suppression physique)
- Timestamps `created_at` / `updated_at` sur tous les modeles
- Migrations expand/contract uniquement (jamais destructives)

---

## Licence

Projet prive.
