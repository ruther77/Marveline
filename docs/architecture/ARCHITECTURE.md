# Architecture CaroCorp

## Vue d'ensemble

CaroCorp est une application de gestion de location de vaisselle et accessoires pour événements, construite avec une architecture moderne et sécurisée.

## Stack Technique

### Backend
- **FastAPI** : Framework web moderne et performant
- **SQLAlchemy 2.0** : ORM pour PostgreSQL
- **Alembic** : Gestion des migrations de base de données
- **Pydantic** : Validation des données et configuration
- **Python 3.11+**

### Base de données
- **PostgreSQL 16** : Base de données principale (port 5433)
- **Redis 7** : Cache, sessions, broker Celery (port 6380)

### Tâches asynchrones
- **Celery** : Worker pour tâches de fond
- **Queues dédiées** :
  - `reservations` : Gestion des réservations
  - `invoicing` : Facturation automatique
  - `notifications` : Envoi d'emails/SMS
  - `reports` : Génération de rapports

### Infrastructure
- **Docker Compose** : Orchestration des conteneurs
- **Poetry** : Gestion des dépendances Python
- **GitHub Actions** : CI/CD automatisé

## Structure du Projet

```
CaroCorp_new/
├── app/
│   ├── api/v1/              # Endpoints API
│   │   └── endpoints/       # Controllers par domaine
│   ├── core/                # Configuration, database
│   ├── models/              # Modèles SQLAlchemy
│   ├── repositories/        # Accès aux données
│   ├── services/            # Logique métier
│   ├── middleware/          # CSRF, security headers, rate limit
│   ├── schemas/             # Schémas Pydantic
│   └── tasks/               # Tâches Celery
├── tests/
│   ├── unit/                # Tests unitaires
│   ├── integration/         # Tests d'intégration
│   ├── e2e/                 # Tests end-to-end
│   └── security/            # Tests de sécurité
├── alembic/                 # Migrations de base de données
├── frontend/                # Application React (futur)
├── docs/                    # Documentation
├── scripts/                 # Scripts utilitaires
└── .github/workflows/       # CI/CD GitHub Actions
```

## Patterns Architecturaux

### Multi-Tenant
- Toutes les tables métier incluent `tenant_id`
- RLS (Row-Level Security) sur PostgreSQL
- Isolation complète des données par tenant

### Repository Pattern
- Séparation logique métier / accès données
- Facilite les tests unitaires
- Réutilisabilité du code

### Dependency Injection
- FastAPI Depends() pour les dépendances
- Configuration centralisée via Pydantic Settings
- Facilite le mocking en tests

## Sécurité

### Authentification
- JWT avec refresh tokens
- Tokens stockés dans Redis
- Expiration configurable

### Protection CSRF
- Middleware CSRF sur toutes les routes modifiantes
- Token généré par session
- Validation dans headers `X-CSRF-Token`

### Headers de Sécurité
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Strict-Transport-Security`
- `Content-Security-Policy`

### Rate Limiting
- Middleware de rate limiting par IP
- Stockage dans Redis
- Configurable par endpoint

## CI/CD Pipeline

### Étapes GitHub Actions
1. **Lint** : Black, Flake8, MyPy
2. **Security** : Bandit, Safety
3. **Tests** : Unit, Integration, E2E
4. **Build** : Docker image
5. **Deploy** : Automatique sur main/develop

### Métriques de Qualité
- Coverage > 80%
- Type hints obligatoires
- Pas de vulnerabilités critiques

## Isolation des Ports

CaroCorp utilise des ports distincts de MassaCorp :

| Service    | CaroCorp | MassaCorp |
|------------|----------|-----------|
| API        | 8001     | 8000      |
| PostgreSQL | 5433     | 5432      |
| Redis      | 6380     | 6379      |
| Frontend   | 3002     | 3000      |

## Migration depuis MassaCorp

### Code Partagé
Une librairie `massacorp-shared` sera créée pour :
- Modèles de base (TimestampMixin, TenantMixin)
- Middlewares de sécurité
- Utilitaires communs
- Configuration CI/CD

### Modules Spécifiques
- **MassaCorp** : Épicerie, restaurant, stock alimentaire
- **CaroCorp** : Location vaisselle, réservations, événements

## Prochaines Étapes

1. ✅ Structure de base créée
2. 🔄 Modèles de données métier
3. 🔄 Endpoints API REST
4. 🔄 Tests complets
5. 🔄 Documentation API
6. 🔄 Déploiement staging
