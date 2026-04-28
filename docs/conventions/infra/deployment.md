# Infra — Déploiement

## Docker Multi-Stage (Production)

```dockerfile
# Dockerfile
# Stage 1 : Build
FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-dev --no-interaction

# Stage 2 : Runtime (minimal, sécurisé)
FROM python:3.12-slim AS runtime
WORKDIR /app

# Utilisateur non-root
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Copier uniquement les dépendances installées
COPY --from=builder /app/.venv /app/.venv
COPY app/ ./app/
COPY alembic/ ./alembic/

# Permissions restrictives
RUN chown -R appuser:appgroup /app
USER appuser

# Filesystem en lecture seule (sauf /tmp)
# docker run --read-only --tmpfs /tmp ...

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

## Blue/Green Deployment

```bash
# Déploiement sans interruption de service
# 1. Déployer la version "green" (nouvelle)
docker compose -f docker-compose.green.yml up -d

# 2. Vérifier la santé du green
curl -f http://green:8000/health

# 3. Basculer le load balancer
# nginx: upstream backend { server green:8000; }

# 4. Attendre que les connexions blue se terminent
sleep 30

# 5. Arrêter blue
docker compose -f docker-compose.blue.yml down

# En cas de problème : rollback immédiat
# nginx: upstream backend { server blue:8000; }
```

## GitHub Actions CI/CD

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check . && mypy app/

      - name: Tests
        run: pytest tests/ -v --cov=app --cov-fail-under=80
        env:
          DATABASE_URL: postgresql://postgres:test@localhost/test_db
          REDIS_URL: redis://localhost:6379

      - name: Migration dry-run
        run: alembic upgrade head --sql | grep -E "DROP TABLE|DROP COLUMN" && exit 1 || true

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        run: ./scripts/deploy.sh
```

## Trunk-Based Development

```
main (trunk)
  ↑ feature/add-payment (courte durée < 2 jours)
  ↑ fix/invoice-calculation
  ↑ chore/update-dependencies

# Règles :
# - Pas de branches longues (> 2 jours → décomposer)
# - Feature flags pour code non terminé en production
# - Rebase sur main avant merge (pas de merge commits)
# - Squash merge pour les features
```

## Conventional Commits

```
feat: add payment recording to invoices
fix: correct total calculation with charges
docs: update API documentation for v2
test: add anti-cross-tenant tests for payments
refactor: extract payment validation to service
chore: update dependencies
perf: add index on reservations.status
ci: add migration dry-run step
```

```
# Format complet
type(scope): description courte

Corps (optionnel): explication du pourquoi

Refs: #123
Breaking Change: BREAKING CHANGE: removed endpoint /v1/old-endpoint
```

## Environnements

```yaml
# docker-compose.yml (base)
# docker-compose.override.yml (dev local — non committé)
# docker-compose.prod.yml (production)

# Variables par env
# .env.example (committé, sans valeurs)
# .env (non committé, local)
# Secrets en production : Vault ou Doppler (voir secrets.md)
```

## ULID (Identifiants Publics)

```python
import ulid

# Utiliser ULID comme identifiant externe (exposé dans l'API)
# PK interne reste BigInteger pour les performances

class Reservation(Base, TimestampMixin):
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # PK interne
    external_id: Mapped[str] = mapped_column(
        String(26),
        default=lambda: str(ulid.new()),
        unique=True,
        nullable=False,
    )  # Exposé dans l'API — ULID est time-sortable

# Dans les endpoints : utiliser external_id dans l'URL
@router.get("/{external_id}")
async def get_reservation(external_id: str, ...):
    return service.get_by_external_id(tenant_id, external_id)
```

## Règles

- Image Docker : non-root, read-only filesystem, image slim
- Multi-stage : séparer build et runtime
- Healthcheck sur tous les services
- Blue/Green pour zéro downtime
- CI bloque si : lint fail, tests fail, coverage < 80%, migration destructive
- Conventional Commits obligatoires (vérifiés par commitlint en CI)
- ULID pour les identifiants exposés dans l'API
