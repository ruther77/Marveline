# CONTRIBUTING — DEVUP Refactor 2026

> **Refonte architecturale** lancée 2026-04-28. Objectif : transformer la base monolithique mono-tenant Marveline en plateforme SaaS multi-tenant N verticals (location, épicerie, restaurant, autour_de_table).
>
> Plan complet : `docs/architecture-audit-2026-04-26/execution-plan/`

---

## ⛔ Règle absolue : NE JAMAIS pousser sur `main`

`main` représente l'**état figé pré-refonte** (snapshot 2026-04-28). Aucun push, aucun merge sur `main` n'est autorisé pendant les 3 mois de refonte.

`main` ne sera mis à jour qu'**à la fin de la refonte complète**, après validation Lead, en mergeant les 2 branches `Page` et `Torvalds` ensemble dans un commit final consolidé.

```bash
# Si tu vois ce warning au push, STOP :
remote: error: GH006: Protected branch update failed
```

→ Tu pousses sur la mauvaise branche. Vérifie avec `git branch --show-current`.

---

## Branches

| Branche | Owner | Périmètre | Document plan |
|---|---|---|---|
| `main` | (intouchable) | Snapshot pré-refonte 2026-04-28 | — |
| `Page` | Dev "Page" | Foundation + Money + Catalog (Bloc 1, 3, 4) | [PLAN_PAGE.md](./PLAN_PAGE.md) |
| `Torvalds` | Dev "Torvalds" | Auth + ETL/Restaurant + Ops + Frontend (Bloc 2, 5, 6, 7) | [PLAN_TORVALDS.md](./PLAN_TORVALDS.md) |

---

## Workflow individuel

### Setup initial (une fois)

```bash
git clone https://github.com/ruther77/devup.git
cd devup
git checkout Page    # ou Torvalds selon l'assignation
```

### Cycle de travail quotidien

```bash
# 1. Avant de coder, sync avec ton remote (jamais avec main)
git pull origin Page

# 2. Lire le sprint courant (cf. PLAN_PAGE.md ou PLAN_TORVALDS.md)
# 3. Suivre le protocole senior (cf. ~/.claude/skills/senior-protocol)
#    - CHECK_BUGS()
#    - CITE_SPEC(component, section_ref) avant tout code
#    - prepare(file_path) avant Edit Python
#    - WRITE_TESTS(phase) dans la même session
#    - MARK_PHASE_DONE(phase) avec preuve pytest

# 4. Commits granulaires (1 sprint = ≥1 commit, idéalement 1 par story)
git add <fichiers>
git commit -m "feat(B1.S2.T1): RLS helper set_tenant_context (TR-X)"

# 5. Push UNIQUEMENT sur ta branche
git push origin Page    # ou Torvalds
```

### Convention messages de commit

```
<type>(<sprint>.<story>): <description courte>

<corps optionnel — why, decisions, refs spec>
<résolution friction(s) — Closes TR-X, Fxxx>
```

Types : `feat`, `fix`, `refactor`, `test`, `docs`, `migration`, `chore`.

Exemples :
- `feat(B1.S2.T2): enable RLS on 80 tenant tables (TR-9, TR-27)`
- `fix(S1.T1): MARMITE-QPP-01 quantite_par_batch × ratio (TR-57)`
- `migration(B4.S3): drop Product.tva_rate float, add Category.tva_rate (TR-3, TR-18)`

---

## Zones de fichiers : éviter les conflits

Cf. [ZONES.md](./ZONES.md) — table fichiers réservés par dev.

**4 zones de chevauchement coordonnées** (PR review obligatoire) :

| Fichier | Dev A (Page) | Dev B (Torvalds) | Coordination |
|---|---|---|---|
| `app/services/notification.py` | B3.S5 (gateway transactionnel) | B6.S1 (Postmark refactor) | Page touche en premier (Bloc 3 < Bloc 6 ordre topologique). Torvalds rebase sur le travail de Page. |
| `app/middleware/audit.py` | (consommateur) | B6.S2 (HMAC chain) | Torvalds owner ; Page consomme via `@audit_action` decorator. |
| `app/permissions/scope.py` | (consommateur scopes B3/B4) | B2.S3 (catalog scopes) | Torvalds définit ; Page importe `Scope.X`. Coordination = ajouter ses scopes en début de Bloc 2. |
| `app/services/customer.py` | B4.S4 (RFM) | B4.S5 (PII KMS) | Coordination : Page **finit B4.S4 avant** que Torvalds ne touche customer pour B4.S5. Annoncé en daily. |

---

## Communication

- **Daily standup** : Slack `#devup-refactor` (15 min, 09:30)
  - Hier / Aujourd'hui / Blockers
  - Annoncer entrée dans une zone partagée 24h avant
- **Weekly sync** : 60 min, vendredi 14h
  - Démo des sprints livrés
  - Re-priorisation roadmap si besoin
- **PR review croisée** : chaque dev review les PRs de l'autre sur les zones partagées

---

## Definition of Done par sprint

Source : `docs/architecture-audit-2026-04-26/execution-plan/<sprint>.md` section "DoD".

Avant de passer au sprint suivant :
- [ ] Code conforme spec citée verbatim
- [ ] Tests passés (preuve pytest collée dans le commit ou PR)
- [ ] Schemas Pydantic / types TS / `__init__.py` cohérents
- [ ] Auth + RBAC + tenant isolation vérifiés
- [ ] Migration non-destructive (4-step backward-compatible si schema change)
- [ ] Pas de stub silencieux, pas de `TODO` sans ticket
- [ ] CI verte sur ta branche
- [ ] Section DoD du sprint cochée

---

## Outils

- **Senior protocol** : `~/.claude/skills/senior-protocol`
- **Backend rules** : `~/.claude/skills/backend-rules`
- **Frontend rules** : `~/.claude/skills/frontend-rules`
- **Test rules** : `~/.claude/skills/test-rules`
- **Auth docs CaroCorp** : `~/.claude/carocorp/00-INDEX.md`
- **Context engine** : `mcp__context-engine__prepare(file_path)` avant Edit Python

---

## En cas de doute

1. Lis le sprint complet (`docs/architecture-audit-2026-04-26/execution-plan/<sprint>.md`)
2. Lis l'architecture-cible.md section correspondante (Q1-Q45 verrouillés)
3. Si conflit code réel ↔ spec : **spec gagne** (cf. invariant I7 du senior protocol)
4. Si conflit avec l'autre dev : daily ou Slack `#devup-refactor`
5. Si bloqué >2h : ping Lead

---

**Date de gel main** : 2026-04-28  
**Date cible fin refonte** : 2026-07-28 (3 mois)  
**Date révision si dérive** : 2026-06-28 (mid-point)
