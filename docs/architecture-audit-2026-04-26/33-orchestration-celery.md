# Module 33 — Orchestration / Celery / Background tasks

> **Phase E — module 3/5.** Audit des 12 fichiers Celery (`app/tasks/`) : config Celery, beat schedule, queues, retry policy, sync vs async session DB.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/tasks/celery_app.py` | 139 |
| `app/tasks/invoicing.py` | 258 (parcours fonctions clés) |
| `app/tasks/loyalty.py` | 280 (parcours) |
| `app/tasks/notifications.py` | 250 (parcours mod. 27) |
| `app/tasks/etl_tasks.py` | 160 (déjà mod. 30) |
| `app/tasks/access_review.py` | 142 |
| `app/tasks/risk_detection.py` | 111 |
| `app/tasks/relances.py` | 93 |
| `app/tasks/restaurant_export.py` | 123 (parcours) |
| `app/tasks/printing.py` | 105 |
| `app/tasks/monitoring.py` | 57 |
| `app/tasks/__init__.py` | 4 |

**Volume total** : 1 722 LoC.

---

## 2. Architecture observée

```
celery_app.py
  broker = settings.CELERY_BROKER_URL (Redis)
  backend = settings.CELERY_RESULT_BACKEND
  task_serializer = json
  timezone = "Europe/Paris" (avec enable_utc=True)
  task_time_limit = 30min, soft = 25min
  worker_prefetch_multiplier = 4
  worker_max_tasks_per_child = 1000

QUEUES (task_routes) :
  reservations, invoicing, notifications, default, etl, exports
  loyalty (utilisée mais pas listée dans task_routes !)

AUTODISCOVER : invoicing, notifications, monitoring, access_review,
               etl_tasks, restaurant_export, relances, loyalty, risk_detection

BEAT SCHEDULE (15 tâches périodiques) :
  • check-overdue-invoices-daily          08:00 UTC
  • check-late-movements-hourly           every hour :00
  • check-low-stock-daily                 07:00 UTC
  • privileged-access-review-monthly      1er du mois 06:00
  • tenant-admin-review-quarterly         1er Jan/Avr/Jul/Oct 06:30
  • recertification-review-biannual       1er Jan/Jul 07:00
  • auto-suspend-uncertified-biannual     1er Fév/Aoû 07:30
  • expire-overdue-devis-daily            07:30
  • check-unreturned-deposits-daily       09:00
  • execute-relances-hourly               every hour :15
  • loyalty-expire-points-daily           03:00 UTC
  • loyalty-evaluate-tiers-daily          04:00 UTC
  • loyalty-expiration-warnings-daily     09:00 UTC
  • loyalty-birthday-rewards-daily        08:30 UTC
  • loyalty-activate/deactivate-flash-offers   every 5min
  • detect-reservation-risks-daily        09:00 UTC

SESSIONS DB :
  invoicing.py, relances.py    → sync (get_db_context)
  loyalty.py                   → sync (_get_sync_session = SessionLocal())
  access_review.py             → sync (SyncSessionLocal)
  risk_detection.py            → async (asyncio.run + AsyncSessionLocal)
  etl_tasks.py                 → async (event_loop persistant)
  printing.py                  → sync (SessionLocal)
  notifications.py             → sync probable (mod. 27)

PATTERN ASYNC HORS-CELERY :
  etl_tasks._WORKER_LOOP loop persistant pour asyncpg (mod. 30 F964)
```

---

## 3. Frictions identifiées — module 33

> Compteur cumulé (mod. 01-32) ≈ 1 052. Module 33 ouvre à **F1053**.

### 3.1 P0

#### F1053 — `task_routes` **liste 6 queues**, mais le code utilise aussi `loyalty`, `default` — drift queue mal orientée

`tasks/celery_app.py:33-40`. La règle dit :
```python
"app.tasks.notifications.*": {"queue": "notifications"}
```

Mais `tasks/loyalty.py:23` déclare `queue="loyalty"` directement sur `@celery_app.task`. Or **`loyalty` n'est PAS listé dans `task_routes`** ni dans la liste implicite de queues lancées par les workers. Si le worker pool ne consume pas `loyalty`, **les tâches loyalty s'empilent indéfiniment dans Redis**.

→ Bug de configuration latent. Aucune métrique d'alerte sur queue length.

**Action** : (1) ajouter `"app.tasks.loyalty.*": {"queue": "loyalty"}` dans `task_routes` ; (2) script de boot worker qui valide que toutes les queues déclarées sont effectivement consommées.

---

#### F1054 — `relances.py` et `invoicing.py` utilisent **session sync** (`get_db_context`, `db.query()`, ORM 1.x style) — mais l'app utilise SQLAlchemy 2.0 async partout

`tasks/relances.py:31`, `tasks/invoicing.py:29`. Les sessions sync attaquent la même DB que l'app async. Si la DB pool sync n'est pas séparé, contention. Plus important : pattern API `db.query(Tenant.id).filter(...).all()` est SQLAlchemy 1.4 legacy, fragile au passage 2.0 strict (déprécation prochaine).

→ Mix sync/async/legacy = dette technique massive. 4 patterns différents pour interagir avec la DB selon le worker.

**Action** : standardiser tout en async (`asyncio.run()` wrap pattern de `risk_detection.py`) ou tout en `select()` 2.0 style.

---

#### F1055 — `auto_suspend_uncertified` **NE FAIT RIEN** (skip avec log warning)

`tasks/access_review.py:131-142` : 
```python
logger.warning("auto_suspend_uncertified: table access_reviews not yet implemented — skipping suspensions")
return {"status": "skipped", ...}
```

Compliance §10 SOC2 promet la suspension automatique des users non recertifiés à J+30. La task est planifiée par beat schedule (mod. 33 ligne 83-87) **mais ne suspend personne**. Au prochain audit SOC2, faille critique.

→ Compliance théâtre.

**Action immédiate** : créer table `access_reviews` + implémenter la suspension réelle. Sinon retirer la task du beat (ne pas laisser un cron qui ment).

---

#### F1056 — `check_overdue_invoices` parcourt **tous les tenants en série** sans batch ni timeout per-tenant

`tasks/invoicing.py:40-64`. `for tid in tenant_ids: db.query(...).limit(200).all()` — 200 invoices par tenant, séquentiel. Pour 100 tenants × 200 invoices = 20k items en une seule task. Si la task `task_time_limit = 30 min` n'est pas atteint, OK ; mais en cas d'erreur sur tenant 50, les 50 derniers ne sont jamais traités → relances perdues.

**Action** : task fanout per-tenant (`group(check_tenant_overdue.s(tid) for tid in tids).apply_async()`).

---

#### F1057 — `expire_points_fifo` (loyalty.py) calcule `current_balance` **par scan ledger** sans `with_for_update`

`tasks/loyalty.py:60-80`. Pattern read-modify-write classique : lit `balance_after` du dernier entry, calcule `new_balance = current - amount`, INSERT. Si une transaction concurrente (achat client live générant credit_points) interfère pendant l'expiration nocturne, **le solde devient incohérent** (cf. F792 mod. 25).

→ Identique pattern race que F792-F794 mod. 25. La task d'expiration **ne corrige pas** la race ; elle **l'aggrave** car en concurrent avec credit_points production.

**Action** : `pg_advisory_xact_lock(member_id)` ou `with_for_update` + retry sur conflict. Idéalement : run l'expiration en heures creuses 03:00 UTC OK mais pas de garantie que le système de POS soit fermé.

---

#### F1058 — `relances.py:execute_scheduled_relances` exécute **les relances mais N'ENVOIE PAS l'email**

`tasks/relances.py:75-86` : marque `relance.status = "sent"` + log, **mais aucun appel `notification_service.send_email`** n'apparaît. Le code log "Relance %d sent" puis return. Le statut est mis à `sent` sans qu'aucun email ne soit envoyé !

→ Si on lit "Relance envoyée: invoice=X customer=Y" dans les logs et que le client ne reçoit jamais l'email, on a un faux signal massif.

**Action** : appel explicite `send_relance_email_task.delay(...)` (Celery sub-task) avant marquage sent. Garde idempotence avec `relance.email_sent_at`.

---

#### F1059 — `print_ticket_task` `_load_commerce_info` retourne `("", "", "", "")` silencieusement si erreur DB

`tasks/printing.py:81-105`. Si la DB est down, le ticket est imprimé avec **nom_commerce vide** = ticket non-conforme légalement (mention obligatoire). Aucun raise, aucune retry.

**Action** : raise explicite → triggers retry Celery (3 tentatives configurées).

---

### 3.2 P1

#### F1060 — `task_time_limit = 30 minutes` **trop court** pour gros imports ETL (NOUTAM 5000+ lignes possible)

`celery_app.py:26`. Hard kill à 30min. Si un import a 4000 lignes × 200ms classification = 13min OK, mais le pic peut atteindre 25-35min selon DB latency. SoftLimit 25min déclenche `SoftTimeLimitExceeded`. Pas de stratégie graceful (commit partiel, reprise).

---

#### F1061 — `worker_prefetch_multiplier = 4` peut bloquer queue si une task prend long

Worker prefetch 4 messages, exécute 1 à la fois. Si la première task prend 30min, les 3 autres attendent → task latence p99 = 90min.

**Action** : `worker_prefetch_multiplier = 1` pour tasks longues (etl, exports).

---

#### F1062 — Beat schedule **toutes en UTC mais `timezone = "Europe/Paris"`** dans config

`celery_app.py:23-24`. `enable_utc=True` mais `timezone="Europe/Paris"`. Les `crontab(hour=8, minute=0)` est-il interpretté en Paris ou UTC ? Comportement Celery selon version (TZ-aware si `enable_utc=True`). Drift potentiel.

À tester explicitement.

---

#### F1063 — `check_late_movements` cron horaire **sans dedup window** — task peut s'empiler en cas de lag worker

Si la task prend 65min (lag), à T+60 une nouvelle task lance avant la fin de la précédente → traitements doublons.

**Action** : Celery `task_unique` ou pattern `Singleton` via Redis lock.

---

#### F1064 — `loyalty.activate_flash_offers` toutes les 5 minutes → **288 invocations/jour**

Si 0 flash offer actifs, c'est gaspillé. Pas de back-off intelligent.

---

#### F1065 — `risk_detection.detect_reservation_risks_daily` `asyncio.run` à chaque call → recrée event loop

`tasks/risk_detection.py:25` `asyncio.run(_run_detection())`. Chaque appel ferme/ouvre l'event loop, recrée le pool asyncpg. Coûteux. Comparer à etl_tasks.py qui utilise `_WORKER_LOOP` persistant.

**Action** : appliquer le pattern `_get_worker_loop` partout.

---

#### F1066 — `access_review` log `[access_review] Privileged review: %d users to certify` — **mais ne crée AUCUN AuditLog**

Pas d'enregistrement persistant des reviews déclenchées. Le log applicatif est ephémère (Loki retention < 30j). Compliance demande historique 7 ans. Cf. F1015 audit module.

---

#### F1067 — `print_ticket_task` `autoretry_for=(ConnectionError, OSError)` **exclut `TimeoutError`**

Si l'imprimante répond mais lentement, TimeoutError → pas de retry → ticket perdu.

---

#### F1068 — Pas de **DLQ** (dead letter queue) sur aucune task

Après `max_retries=3` épuisés, la task disparaît silencieusement. Aucune visibilité ops.

---

#### F1069 — `check_overdue_invoices` `db.commit()` dans la boucle tenant — si tenant 75 plante, tenants 1-74 commités

Pattern partial commit non transactionnel, OK pour idempotence per-tenant mais complique le reporting "tâche réussie ou pas".

---

#### F1070 — Pas de **monitoring Celery beat schedule drift** (beat heartbeat)

Si Celery beat process meurt silencieusement, **toutes les tâches périodiques cessent** sans alerte. Pas de health check beat.

---

#### F1071 — `restaurant_export.py` (123 LoC) utilisé par cron biannuel ?

À vérifier — pas dans beat schedule. Si trigger manuel only, OK.

---

#### F1072 — `monitoring.py` 57 LoC très court — peut-être pas suffisant pour les 2 tasks check_late_movements + check_low_stock

À vérifier.

---

#### F1073 — `notifications.py` (250 LoC) appelé par `relances.py` (F1058) ? Si oui, le code semble manquer le wiring.

---

#### F1074 — Beat schedule **dur-codé dans Python** — pas configurable per env

Pour staging vs prod, mêmes timings. Une task qui doit ne pas tourner en staging (ex: send_birthday_rewards) est hardcoded.

---

#### F1075 — `task_track_started=True` ajoute `STARTED` state dans le backend Redis — bonne pratique mais consomme stockage

Redis backend grossit. Pas de TTL configuré sur `result_expires`.

---

#### F1076 — Aucune task **cleanup expired sessions** dans le beat schedule

Mod. 03 mentionnait `Session` model — sessions expirées doivent être purgées. Pas de cron visible.

---

#### F1077 — `_run_detection` (risk_detection.py:50) `for tid in tenant_ids: ... await db.commit()` séquentiel — pas de fanout per-tenant

---

### 3.3 P2

#### F1078 — `task_serializer = json` empêche d'envoyer dataclasses ou Pydantic — drift dict everywhere

#### F1079 — `worker_max_tasks_per_child = 1000` — recycle worker process tous 1k tasks. OK anti-leak mais cache asyncpg détruit fréquemment

#### F1080 — Pas de tag/labels Prometheus sur tasks (success/failure rate)

#### F1081 — `_DEFAULT_QUEUE` partout différent (`default`, `notifications`, `loyalty`...) — pas de doc/registry

#### F1082 — `crontab(minute="*/5")` sans description = mystère pour ops

#### F1083 — Beat schedule **n'utilise pas de jitter** — toutes les tasks 09:00 UTC s'empilent (cf. unreturned_deposits + expiration_warnings + risk_detection même heure)

#### F1084 — `task_routes` regex implicite `app.tasks.X.*` — pas testé

#### F1085 — `loyalty.expire_points_fifo` `LIMIT 1000` magic number sans constant

---

### 3.4 P3

#### F1086 — Comments accents perdus (`Détection`, `Reséaux`)

#### F1087 — `RELANCE_THRESHOLDS_DAYS = [7, 30, 60]` magic, non configurable per tenant

#### F1088 — `_QUEUE_ETL = "etl"` magic string redéclaré aussi dans etl_tasks (F997)

---

## 4. Synthèse module 33

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 7 | F1053 (queue loyalty mal routée), F1054 (mix sync/async), F1055 (auto_suspend no-op compliance fail), F1056 (séquentiel tenants), F1057 (race expire_points), F1058 (relance "sent" sans email), F1059 (ticket sans nom_commerce silent) |
| P1 | 18 | F1060 → F1077 |
| P2 | 8 | F1078 → F1085 |
| P3 | 3 | F1086 → F1088 |
| **Total** | **36** | F1053 → F1088 |

**Compteur cumulé après module 33** : ≈ 1 052 + 36 = **1 088 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) ajouter queue `loyalty` dans `task_routes` + script vérification (F1053) ; (2) implémenter `auto_suspend_uncertified` réel (F1055 — compliance) ; (3) fanout per-tenant invoicing (F1056) ; (4) advisory lock `expire_points_fifo` (F1057) ; (5) **wire l'email dans `execute_scheduled_relances`** (F1058 — bug critique production) ; (6) raise explicite `_load_commerce_info` (F1059) ; (7) standardiser sessions DB async (F1054).
>
> **Refactor** : DLQ Redis (F1068) ; beat heartbeat health check (F1070) ; Prometheus metrics tasks (F1080) ; jitter beat schedule (F1083) ; cleanup_expired_sessions task (F1076).

---

# Module 34 (suivant) — Printer ESC/POS / VPN
