# Index des Conventions — Marveline

> Point d'entrée unique. En cas de doute, consulter ce fichier d'abord.

---

## Règles de Décision Rapide

### "Je dois créer une nouvelle table métier"
→ [`core/01-models.md`](core/01-models.md) — TimestampMixin, SoftDeleteMixin, tenant_id NOT NULL, index composite

### "Je dois définir un schéma Pydantic"
→ [`core/02-schemas.md`](core/02-schemas.md) — Base/Create/Update/Response, montants en centimes, validators

### "Je dois écrire une requête DB"
→ [`core/03-repositories.md`](core/03-repositories.md) — filtre tenant obligatoire, pas de N+1, get_or_404

### "Je dois écrire la logique métier"
→ [`core/04-services.md`](core/04-services.md) — stateless, pas d'accès DB direct, exceptions NotFound

### "Je dois créer un endpoint FastAPI"
→ [`core/05-endpoints.md`](core/05-endpoints.md) — auth, RBAC, pagination, error handling

### "Je dois écrire des tests"
→ [`core/06-tests.md`](core/06-tests.md) — pyramide 70/20/10, anti-cross-tenant, db.flush() obligatoire

### "Je dois créer un composant React"
→ [`core/07-frontend.md`](core/07-frontend.md) — React Query, Zustand, pattern erreur mutation

### "Je dois gérer des constantes ou enums"
→ [`core/08-constants-enums.md`](core/08-constants-enums.md) — app/constants/, pas de magic strings

### "Je dois créer une migration Alembic"
→ [`core/09-migrations.md`](core/09-migrations.md) — expand/contract, jamais destructive, dry-run CI

---

## Règles de Décision — Patterns

### "Mon service peut échouer / retry / timeout"
→ [`patterns/resilience.md`](patterns/resilience.md) — Circuit Breaker, Retry+Jitter, Timeout, Bulkhead, Saga

### "Je dois concevoir/versionner une API"
→ [`patterns/api-design.md`](patterns/api-design.md) — ETag, Cursor Pagination, Sparse Fieldsets, Versioning

### "J'ai un problème de performance DB ou cache"
→ [`patterns/performance.md`](patterns/performance.md) — Materialized Views, Partial Index, Cache Tags, pgBouncer

### "J'ai un besoin de sécurité avancée"
→ [`patterns/security.md`](patterns/security.md) — SSRF, Field Encryption, Re-auth, ReDoS, CSP, mTLS

### "Je dois améliorer l'UX frontend (formulaires, scroll, état)"
→ [`patterns/frontend-advanced.md`](patterns/frontend-advanced.md) — Zod, MSW, URL State, Optimistic UI, PWA, Infinite Scroll

### "J'ai besoin de messaging, events ou webhooks"
→ [`patterns/event-driven.md`](patterns/event-driven.md) — Outbox, Saga, Domain Events, SSE, Event Sourcing

---

## Règles de Décision — Infrastructure

### "Je dois configurer Celery / tâches async"
→ [`infra/celery-async.md`](infra/celery-async.md) — DLQ, retry, idempotence, Celery + OpenTelemetry

### "Je dois monitorer / tracer / alerter"
→ [`infra/observability.md`](infra/observability.md) — OpenTelemetry, Slow Query, SLO/Error Budget, Sentry

### "J'ai des obligations RGPD"
→ [`infra/rgpd.md`](infra/rgpd.md) — anonymisation, droit à l'oubli, audit trail, rétention

### "Je dois déployer / CI-CD"
→ [`infra/deployment.md`](infra/deployment.md) — Docker multi-stage, Blue/Green, GitHub Actions, Trunk-Based

### "Je dois gérer des secrets"
→ [`infra/secrets.md`](infra/secrets.md) — Vault/Doppler, rotation, DB SSL, no-hardcode

### "Je dois tester/documenter backup et restore"
→ [`infra/backup-restore.md`](infra/backup-restore.md) — runbook pg_dump, restore, RTO/RPO

---

## Règles de Décision — Design

### "Je dois définir des tokens visuels (couleurs, typographie, spacing)"
→ [`design/design-tokens.md`](design/design-tokens.md) — CSS custom properties, Tailwind config, dark mode

### "Je dois vérifier l'accessibilité"
→ [`design/accessibility.md`](design/accessibility.md) — axe-playwright WCAG 2.1 AA, Lighthouse CI, aria-label

---

## Règles de Décision — Décisions Actées

### "Je veux comprendre les décisions T1-T10 actées du projet"
→ [`decisions/T1-T10-actees.md`](decisions/T1-T10-actees.md)

### "Je dois créer un ADR (Architecture Decision Record)"
→ [`decisions/ADR-template.md`](decisions/ADR-template.md)

### "Je dois configurer les hooks pre-commit"
→ [`decisions/pre-commit.md`](decisions/pre-commit.md)

---

## Conventions Critiques (Rappel Express)

| Convention | Règle |
|---|---|
| Montants | `BigInteger` centimes (250 = 2.50€). Jamais de float. |
| Multi-tenant | `tenant_id NOT NULL` sur toute table métier. Filtre obligatoire en repo. |
| Soft delete | `is_active BOOLEAN` via `SoftDeleteMixin`. Jamais de DELETE physique. |
| Timestamps | `created_at` / `updated_at` via `TimestampMixin`. Toujours. |
| Exceptions | `NotFound` (pas `NotFoundError`) depuis `app.core.exceptions` |
| Migrations | `expand/contract` uniquement. Jamais de `DROP COLUMN` direct. |
| Secrets | Zéro secret hardcodé. Zéro magic string pour concepts métier. |
| Auth | Aucun endpoint sans auth. RBAC vérifié backend. |
| Tests | Min 80% coverage. Critiques 95%. Anti-cross-tenant obligatoire. |
| DB | `db.flush()` explicite après mutations ORM (session `autoflush=False`). |

---

## Matrice de Priorités

| Niveau | Description | Action |
|---|---|---|
| P0 | Bloquant — sécurité, cross-tenant, perte données | Fix immédiat, ticket, post-mortem |
| P1 | Important — dégradation service, performance critique | Fix dans le sprint |
| P2 | Amélioration — dette technique, UX | Planifier |
| P3 | Optionnel — optimisations futures | Backlog |

---

*Source : `docs/conventions/CONVENTIONS.md` (référence complète ~8578 lignes)*
