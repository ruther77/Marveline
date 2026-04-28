# Quickstart Dev — Par où commencer lundi matin

> **Pour qui** : tout dev qui rejoint le chantier de refonte DEVUP (Bloc 1-7).
> **Temps de lecture** : 10 min.
> **Pré-requis** : avoir lu `00-INDEX.md` et `architecture-cible.md` §1-§3.

---

## 1. Setup local (15 min)

```bash
git clone git@github.com:devup/devup.git
cd devup
cp .env.example .env

# Démarrer infra
docker-compose up -d postgres redis rabbitmq

# Backend Python 3.12 + Poetry
poetry install
alembic upgrade head

# Frontend monorepo
cd frontend && pnpm install && pnpm dev
```

**Vérification** : `curl localhost:8000/health/live` → `{"status": "alive"}`.

---

## 2. Lecture obligatoire avant de coder (30 min)

| Doc | Pourquoi | Quand |
|---|---|---|
| `architecture-cible.md` §1 (vue d'ensemble) | Saisir les 7 blocs et leurs dépendances | Toujours |
| `architecture-cible.md` §3.6 / §4.6 / §5.6 / §6.6 / §7.6 | Décisions verrouillées Q1-Q45 (source de vérité) | Toujours |
| `02-conventions.md` | Naming, tests, git, PR review | Toujours |
| `50-sql-schema.md` | DDL canonique (sera votre référence) | Avant migration |
| `54-ci-invariants.md` | Scripts CI qui bloquent les régressions | Avant push |

---

## 3. Workflow ticket Jira-ready

Chaque ticket de sprint suit le format identique :

1. **Lire le sprint doc** (`13-sprint-B3.SX.md`)
2. **Identifier la story qui vous est assignée**
3. **Lire la section "Contexte" + "Solution" de la story** — la solution est déjà esquissée en pseudo-code
4. **Implémenter** en respectant `app/services/` pattern
5. **Tester** : pyramide tests (`53-tests-strategy.md`)
6. **PR review** : 1 reviewer + CI green obligatoire avant merge
7. **DoD checklist** : cocher toutes les cases avant de fermer le ticket

---

## 4. Règles d'or (à imprimer et coller au mur)

### A1-A11 (extension `~/.claude/CLAUDE.md`)
1. **A1** Pas de donnée cross-tenant — RLS + filtre repository
2. **A2** Pas de mutation non auditée — `@audit_action` ou audit explicite
3. **A3** Pas de secret en clair — `EncryptedField` KMS
4. **A4** Pas d'endpoint sans auth — `require_scope`
5. **A5** Pas de déploy sans CI verte — bloquant
6. **A6** Pas de migration destructive — pattern 4 étapes
7. **A7** Pas de mention "IA" dans code/commits
8. **A8** Pas d'édition Python sans `mcp__context-engine__prepare()`
9. **A9** Pas d'implémentation paresseuse — pas de stub silencieux
10. **A10** Tout bug détecté → `NOTE_BUG()` immédiat
11. **A11** Fix Before Feature permanent

### Multi-tenant
- Toute table métier porte `tenant_id NOT NULL`
- Tout endpoint vérifie le tenant context
- Tout Celery task accepte `tenant_id` arg

### Money
- `BigInteger centimes` (pas float)
- `Numeric(5,4)` pour pourcentages
- `tva_rate_snapshot` capturé sur ligne facturable
- `PricingEngine.quote()` source unique

---

## 5. Stack & versions

```yaml
backend:
  python: 3.12
  framework: FastAPI 0.110+
  orm: SQLAlchemy 2.0 async
  validation: Pydantic 2.x
  db: PostgreSQL 16 (avec RLS)
  cache: Redis 7
  broker: RabbitMQ 3.13 (post-Bloc 6.S7) — Redis avant
  worker: Celery 5.4

frontend:
  framework: React 18 + TypeScript 5
  router: TanStack Router v1
  query: TanStack Query
  state: Zustand
  test: Vitest + Testing Library

infra:
  container: Docker Compose (dev) → Kubernetes (prod horizon Bloc 6.S6)
  observability: Prometheus + Grafana + Loki + Tempo (OTLP)
  email: Postmark prod, SMTP dev
  storage: S3-compatible (MinIO local, AWS S3 prod)
```

---

## 6. Comment trouver la friction Fxxx ou TR-yy

Chaque story sprint référence des frictions :
- **F1-F1139** : audit modules détaillés Phase 1 (`docs/architecture-audit-2026-04-26/01-vue-densemble.md` à `35-health-metrics.md`)
- **TR-1 à TR-90** : refacto patterns transverses (`architecture-cible.md` §2.1, §3.1, §4.1, §5.1, §6.1, §7.1)

```bash
grep -rn "F532\b" docs/architecture-audit-2026-04-26/
grep -rn "TR-14\b" docs/architecture-audit-2026-04-26/
```

---

## 7. Première contribution — checklist

Pour ta toute première PR :

- [ ] Choisir un ticket P1 ou P2 (pas P0 critique)
- [ ] Lire la story complète (Contexte + Solution + DoD)
- [ ] `mcp__context-engine__prepare(file_path=...)` avant édition
- [ ] Coder en respectant `02-conventions.md`
- [ ] Tests passent localement
- [ ] CI green
- [ ] DoD checklist cochée à 100%
- [ ] PR description liste les frictions résolues (Fxxx, TR-yy)
- [ ] 1 reviewer assigné

---

## 8. Aide

- **Slack #dev-devup** : questions techniques temps réel
- **Slack #ops-devup** : incidents prod
- **Confluence "DEVUP Refonte 2026"** : décisions architecturales
- **Linear "DEVUP-REFACTOR"** : tickets sprints

---

**Bon démarrage. Commit small, test often, ship safe.**
