# Rollback Plans — Par migration data

> **Objectif** : pour chaque migration risquée, plan rollback documenté avec critères de fail + scripts inverse + point de non-retour.

---

## 1. Hiérarchie de rollback

| Niveau | Mécanisme | Délai | Reversibilité |
|---|---|---|---|
| **L1** | Feature flag à `false` | <30s | 100% |
| **L2** | Deploy commit précédent | <5min | 100% |
| **L3** | Revert migration Alembic | <15min | 90% (perte data écrites pendant fenêtre) |
| **L4** | Restore backup DB | 30min-2h | 100% mais perte data fenêtre |

**Toujours essayer L1 avant L2, etc.**

---

## 2. Plans rollback par sprint

### Sprint 1 PROD FIRE-DRILL — 12 P0

Tous les fixes Sprint 1 sont **patches sécurité critiques** :
- **L1 N/A** : pas de feature flag (urgence)
- **L2** : revert deploy précédent (re-introduire vulnérabilité — trade-off avec stabilité)
- **Critère rollback** : régression métier non sécurité (ex: F906 fix introduit un bug 500 marmite)

### B1.S2 — RLS PostgreSQL

**Risque** : RLS mal configuré → user voit data autre tenant ou user ne voit rien.
- **L1** : flag `rls_enforced=false` → désactive `SET LOCAL app.current_tenant_id` au middleware
- **L2** : `ALTER TABLE x DISABLE ROW LEVEL SECURITY` (script `tools/rollback_rls.sql`)
- **Critère** : 1 alerte cross-tenant leak OU spike 403 errors > 10/min

### B1.S3 — KMS encryption

**Risque** : key rotation rate ou KMS down → décryptage impossible.
- **L1** : flag `kms_encryption_active=false` → écriture clear text fallback (lecture compat)
- **L4** : restore backup pre-encryption si rows corrompues

**Point de non-retour** : aucun (EncryptedField gère lecture clear text + chiffré simultanément).

### B3.S2 — DB triggers immutability

**Risque** : trigger bloque legitimate update (ex: cascade cascade incomplete).
- **L1** : `DROP TRIGGER trg_X_immutable` via psql (script à pré-écrire)
- **L2** : revert migration → suppression du trigger
- **Critère** : > 5 IntegrityError/min sur table protégée

### B3.S3 — `tva_rate_snapshot` NOT NULL

**Risque** : backfill a manqué des rows → INSERT échoue.
- **L3** : revert NOT NULL → SET NULL temporairement, fix backfill, re-run
- **Critère** : INSERT DevisLine fail rate > 1%

```sql
-- Rollback script
ALTER TABLE devis_lines ALTER COLUMN tva_rate_snapshot DROP NOT NULL;
ALTER TABLE reservation_lines ALTER COLUMN tva_rate_snapshot DROP NOT NULL;
ALTER TABLE vente_lines ALTER COLUMN tva_rate_snapshot DROP NOT NULL;
ALTER TABLE invoice_lines ALTER COLUMN tva_rate_snapshot DROP NOT NULL;
```

### B3.S4 — Conversion Devis→Resa atomique

**Risque** : déclenchement trigger immutability bloque finalisation.
- **L1** : flag `devis_atomic_conversion=false` → fallback comportement legacy (3 endpoints séparés)
- **Critère** : > 1% conversion failure

### B3.S5 — EmailGateway Postmark

**Risque** : Postmark down → tous emails perdus.
- **L1** : flag `email_provider=smtp_fallback` → SMTP secondaire
- **L2** : settings `EMAIL_PROVIDER=smtp` + restart workers
- **Critère** : success_rate Postmark < 95% pendant 10 min

### B4.S2 — `product_stock_view` materialized

**Risque** : view refresh bloque sur lock long.
- **L1** : flag `stock_view_materialized=false` → endpoints lisent directement stock_items count
- **Critère** : view age > 10 min OR refresh duration > 30s

### B4.S3 — `Category.id` FK NOT NULL

**Risque** : produits orphelins post-backfill.
- **L3** : revert NOT NULL via Alembic
- **Pré-deploy** : audit `SELECT COUNT(*) FROM products WHERE category_id IS NULL` doit retourner 0

### B5.S2 — tenant_id NOT NULL ETL

**Risque** : référentiel ETL perdu cross-tenant pendant migration.
- **L4** : restore backup pre-migration (point de non-retour pour étape 4)
- **Pré-deploy** : maintenance ETL 1h pendant étapes 2-3 zero-downtime

### B6.S2 — Audit refondu service-level

**Risque** : audit perdu pendant migration middleware → service.
- **L1** : flag `audit_middleware_fallback=true` → réactive middleware mutations temporairement
- **Critère** : audit count drop > 30% par rapport à baseline

### B6.S6 — `/metrics` mTLS

**Risque** : Prometheus scrape down → blind ops.
- **L2** : nginx config revert HTTP basic auth
- **Critère** : `prometheus_scrape_failures` > 0 pendant 5 min

### B6.S7 — RabbitMQ broker

**Risque** : tasks lost pendant switch.
- **L1** : flag `celery_broker_rabbitmq=false` → switch CELERY_BROKER_URL=redis://...
- **L2** : restart workers Redis
- **Critère** : task ack rate < 95% pendant 10 min

### B7.S2 — Drop brand_code

**Risque** : ressources orphelines si tenant multi-brand pas split correctement.
- **L4** : restore backup pre-migration (point de non-retour)
- **Pré-deploy** : `tools/migrate_split_multi_brand_tenant.py --dry-run` doit confirmer 0 tenant multi-brand

---

## 3. Backup strategy

### Frequency

- **Daily** : snapshot DB complet, retention 30j
- **Weekly** : archive S3 long-term, retention 1 an
- **Pre-deploy** : snapshot manuel avant migration risquée

### Restore procedure

```bash
# 1. Stop application
kubectl scale deployment/api --replicas=0

# 2. Restore DB
pg_restore --clean --if-exists -d devup_prod backup_pre_X.sql

# 3. Restart application
kubectl scale deployment/api --replicas=3

# 4. Health check
curl https://api.devup.fr/health/ready

# 5. Re-run migrations si nécessaire
alembic upgrade head
```

**Test restore** : 1× par mois en staging.

---

## 4. Procédure d'incident rollback

### Détection

- AlertManager fires
- User report (Slack #incidents)
- Monitoring dashboard

### Décision (5 min max)

```
1. Quel sprint en cours ? (consulter calendrier rollout)
2. L1 disponible ? → activer flag immédiatement
3. Sinon L2 disponible ? → kubectl rollout undo
4. Sinon L3 ou L4 ? → escalade ops + maintenance window
```

### Communication

- Slack `#incidents` : annonce rollback
- Status page mise à jour (si client-facing)
- Post-mortem dans 48h (template `templates/post-mortem.md`)

### Post-rollback

- Bug ticket créé (Linear `DEVUP-INCIDENT`)
- Reproduction en staging
- Fix + test + nouveau deploy

---

## 5. Tests rollback

Pour chaque sprint, **tests rollback obligatoires** en staging avant deploy prod :

```bash
# Pattern test
1. Deploy migration en staging
2. Activer flag à 50%
3. Inject erreurs (chaos test)
4. Trigger rollback (flag → false)
5. Verify : app fonctionne sans la nouvelle capacité
6. Verify : 0 data corruption
```

---

## 6. Points de non-retour identifiés

⚠️ **Migrations sans rollback simple** (L4 obligatoire après) :

1. **B3.S6.T4** Drop final `app/models/finance/*` (déjà drop B3.S1.T3, juste CI invariant)
2. **B5.S2.T1** Étape 4 drop indexes globaux ETL
3. **B7.S2** Drop colonnes `brand_code` (étape 4)
4. **B4.S2.T4** Drop `Product.available_quantity` (étape 4)

Pour chaque : **24h+ canary à 100% avant l'étape 4**.

---

**Fin du document — 62-rollback-plans.md**
