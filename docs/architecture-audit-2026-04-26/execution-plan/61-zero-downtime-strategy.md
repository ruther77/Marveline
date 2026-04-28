# Zero-Downtime Strategy

> **Objectif** : déployer les 36 sprints sans aucune fenêtre de maintenance > 5 min.
> **Principe** : pattern 4 étapes pour migrations data + double-write/read pour bascules.

---

## 1. Pattern 4 étapes (référence canonique)

Pour toute migration data **destructive** (drop column, change type, NOT NULL, etc.) :

### Étape 1 — Add (compatible legacy code)
- Ajouter la nouvelle colonne/structure **nullable**
- Code lit/écrit **les deux** (old + new)
- Aucun risque rollback

### Étape 2 — Backfill
- Script Celery batch 1000 lignes
- Idempotent (re-run sans effet)
- Progress logged + monitoring

### Étape 3 — Switch read+write
- Code lit **new only**, écrit **les deux**
- Si bug : rollback étape 4, garder les deux écritures
- Validation : 24h+ sans erreur

### Étape 4 — Drop legacy
- Code écrit **new only**
- DROP colonne legacy
- **Point de non-retour** — rollback = restore backup DB

---

## 2. Migrations identifiées comme zero-downtime

### Drop colonnes denormalized (B4.S2.T4)

```
Étape 1 : créer product_stock_view materialized
Étape 2 : refresh view + endpoints lisent stock_view
Étape 3 : services écrivent stock_items only (pas Product.available_quantity)
Étape 4 : DROP Product.available_quantity, ProductVariant.available_quantity
         + DROP function sync_available_from_variants
```

**Fenêtre risque** : aucune si ordre respecté.

### FK NOT NULL backfill (B4.S3.T1, B5.S5.T1)

```
Étape 1 : ADD COLUMN category_id INT NULL + FK
Étape 2 : UPDATE products SET category_id = (lookup) — script Celery
Étape 3 : SET NOT NULL après orphans count = 0
Étape 4 : DROP COLUMN category String
```

**Fenêtre risque** : si orphans détectés en étape 3 → backfill complémentaire avant SET NOT NULL.

### tenant_id NOT NULL ETL (B5.S2.T1)

```
Étape 1 : ADD tenant_id NULL + FK + RLS désactivé
Étape 2 : Backfill via EtlImport.target_tenant_id
Étape 3 : SET NOT NULL + ENABLE RLS + UNIQUE per-tenant
Étape 4 : DROP indexes globaux
```

**Risque** : si ETL en cours pendant migration → mauvais tenant_id assigné. **Mitigation** : maintenance ETL (1h) pendant étapes 2-3.

### PII encryption (B4.S5.T4)

```
Étape 1 : Ajouter EncryptedField au modèle (lecture transparente clear text fallback)
Étape 2 : Celery task migrate_pii_encryption batch 1000
Étape 3 : Audit raw SQL — 0 clear text restant
Étape 4 : Rien à drop (réécriture in-place)
```

**Fenêtre risque** : aucune (lecture transparente pendant migration).

### Drop brand_code (B7.S2)

```
Étape 1 : Vue legacy `products_with_legacy_brand` pour code transition
Étape 2 : Refacto code Python pour lire via tenant_id seul
Étape 3 : Audit grep — 0 ref brand_code dans Python
Étape 4 : DROP COLUMN brand_code (4 tables) + DROP VIEW
```

**Fenêtre risque** : aucune.

---

## 3. Migrations qui RÉCLAMENT maintenance window

### mTLS bascule `/metrics` (B6.S6.T1)

**Pourquoi** : Prometheus scrapers doivent obtenir cert avant que mTLS soit enforced.
**Fenêtre** : 30 min, samedi 03:00-03:30.

```
T-30  : déployer cert-manager + générer client certs scrapers
T-10  : Prometheus reload avec cert + scrape via HTTPS
T0    : nginx-ingress switch mTLS required
T+10  : verify scrape success
T+20  : si fail → rollback nginx config
```

### RabbitMQ migration broker (B6.S7)

**Pourquoi** : switch CELERY_BROKER_URL = restart workers.
**Fenêtre** : 1h, samedi 02:00-03:00.

```
T-1h  : déploiement RabbitMQ parallèle Redis
T-30  : nouveaux workers AMQP en parallèle workers Redis
T0    : drain Redis queues (~LLEN celery → 0)
T+30  : restart workers en mode AMQP only
T+45  : cleanup Redis broker keys
T+60  : monitoring 24h
```

Cf. `64-rabbitmq-migration.md` pour le détail.

---

## 4. Pattern double-write/double-read (pour rollback safe)

Pour les bascules sensibles (auth, money), pattern :

```python
# 1. Phase double-write (étape 3 ou flag)
async def update_user(user_id, **changes):
    if FF.is_enabled("user_v2_double_write"):
        await user_v1_repo.update(user_id, **changes)  # legacy
        await user_v2_repo.update(user_id, **changes)  # new
    else:
        await user_v1_repo.update(user_id, **changes)

# 2. Phase double-read avec verify
async def get_user(user_id):
    v1 = await user_v1_repo.get(user_id)
    if FF.is_enabled("user_v2_verify_read"):
        v2 = await user_v2_repo.get(user_id)
        if v1 != v2:
            logger.warning("user_drift", user_id=user_id, v1=v1, v2=v2)
    return v1  # ou v2 selon flag

# 3. Phase v2 only
# Drop v1 code après 7j sans drift
```

Application typique : `auth_factors` unifié (B2.S5) pendant migration.

---

## 5. Procédure de déploiement standard

```bash
# 1. CI green obligatoire
gh pr checks <PR>

# 2. Backup DB pre-deploy
pg_dump prod > backup_pre_$(date +%Y%m%d_%H%M).sql.gz

# 3. Deploy backend + run migrations alembic
kubectl apply -f manifests/api-deployment.yaml
alembic upgrade head

# 4. Health check
curl https://api.devup.fr/health/live
curl https://api.devup.fr/health/ready  # checks DB + Redis + RabbitMQ

# 5. Smoke tests E2E
pytest tests/smoke/

# 6. Activate feature flag (si flag impliqué)
psql -c "UPDATE feature_flags SET enabled=true WHERE name='xyz_v2'"

# 7. Monitor 30 min
# Grafana panel + AlertManager
```

---

## 6. Critères "go/no-go" pré-deploy

Checklist obligatoire avant chaque deploy :

- [ ] CI verte (incl. invariants CI)
- [ ] PR review approved par 1+ reviewer
- [ ] Backup DB < 24h
- [ ] Runbook rollback identifié (`62-rollback-plans.md`)
- [ ] AlertManager rules à jour
- [ ] Communication ops sur Slack `#deploys`
- [ ] Maintenance window communiquée client si applicable

---

## 7. Anti-patterns à éviter

❌ **DROP colonne directement** sans pattern 4 étapes
❌ **ALTER TABLE NOT NULL sans backfill préalable**
❌ **Rename column / table** en 1 PR (faire 2 PR : add + drop)
❌ **Migration non idempotente** (re-run doit être no-op)
❌ **Deploy vendredi 17h** (sauf P0 critique)
❌ **Skip backup** sur migration data
❌ **Activer flag à 100% sans canary** (sauf P0 sécurité)

---

**Fin du document — 61-zero-downtime-strategy.md**
