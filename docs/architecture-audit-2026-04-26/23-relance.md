# Module 23 — Relance (Marveline)

> **Phase C.** Audit du domaine relances de paiement : modèle Relance (FSM 3 statuts), Celery task `execute_scheduled_relances`.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/relance.py` | 96 |
| `app/tasks/relances.py` | 93 |
| `app/api/v1/endpoints/relances.py` | 177 (parcours) |
| `app/schemas/relance.py` | 38 |

**Volume total** : 404 LoC.

---

## 2. Architecture observée

```
Relance (FSM 3 statuts)
  scheduled → sent | cancelled
  channel : email | sms | push (CHECK)
  invoice_id FK CASCADE

execute_scheduled_relances (Celery task, beat schedule horaire)
  for each tenant.status == "active" :
    SELECT relances WHERE status='scheduled' AND scheduled_at <= now LIMIT 100
    for each :
      if invoice paid/cancelled → cancel
      if no customer email → skip
      else → mark sent + update invoice timestamps
```

---

## 3. Frictions identifiées — module 23

> Compteur cumulé (mod. 01-22) ≈ 749. Module 23 ouvre à **F750**.

### 3.1 P0

#### F750 — `execute_scheduled_relances` ne fait **PAS** l'envoi email réel

**Constat.** `app/tasks/relances.py:75-87` :
```python
relance.status = "sent"
relance.sent_at = now

if not invoice.first_reminder_sent_at:
    invoice.first_reminder_sent_at = now
invoice.last_reminder_sent_at = now

total_sent += 1
logger.info("Relance %d sent: invoice=%s customer=%s ...")
```

**Aucune ligne d'envoi email**. Pas de `notification_service.send_email()`, pas de `send_template_email.delay()`. La relance est marquée `sent` dans la DB mais **rien n'est jamais envoyé au client**.

**Conséquence** : le système croit avoir relancé, le client n'a rien reçu, factures restent impayées sans rappel effectif. Bug critique métier silencieux.

**Action** : appeler `notification_service.send_relance_email(customer.email, invoice, ...)` avant de marquer `sent`. Si exception → ne pas marquer sent, retry au cycle suivant.

---

#### F751 — Pas de retry policy ni DLQ pour relances échouées

**Constat.** `tasks/relances.py:88-89` :
```python
except Exception:
    logger.exception("Relance %d failed — will retry next cycle", relance.id)
```

Le commentaire dit "retry next cycle" mais aucun `max_retries` ni alerte Slack/email à `> 3 échecs`. Une relance buggée peut échouer indéfiniment, dilapidant CPU.

**Action** : compteur `Relance.attempt_count`, après seuil → status `failed` + alerte ops.

---

### 3.2 P1

#### F752 — `Relance.created_at` Mapped sans `server_default=func.now()`

`models/relance.py:71-74`. Doit être set manuellement à la création — un appel direct sans `created_at` raise IntegrityError.

---

#### F753 — Pas d'audit log à la création de Relance (manuel ou auto)

---

#### F754 — `relance.scheduled_at <= now` comparison sans timezone normalize

Si `scheduled_at` stocké naive et `now` aware, drift UTC.

---

#### F755 — `db.query(Tenant).filter(Tenant.status == "active")` string hardcoded

Pas de constante Tenant.STATUS_ACTIVE.

---

#### F756 — `LIMIT 100` arbitraire par tenant

Pour 1 000 relances dues sur un tenant, 10 cycles d'1h = 10h pour tout traiter. Si la cron tourne toutes les heures et qu'il y a > 100 nouvelles relances/heure, on accumule.

**Action** : `LIMIT` configurable + alerte si `total_pending > LIMIT × N`.

---

#### F757 — `tenant_ids` chargé full en mémoire (acceptable mais pas scalable)

---

#### F758 — Pas de chiffrement email customer (PII partagée avec Celery worker)

---

#### F759 — `Relance` n'a pas de `attempt_count` ni `last_attempt_at` (cf. F751)

---

#### F760 — `message Optional[String]` sans Text/size limit explicite

`Mapped[Optional[str]]` sans `String(N)` ni `Text` → default SQLAlchemy = String / 1 char selon dialecte → tronquage potentiel selon migration.

---

### 3.3 P2

#### F761 — Endpoint `relances.py:177` non lu en détail (CRUD probable)

#### F762 — Pas de cohérence entre `Relance.channel='sms'` accepté en CHECK et envoi non implémenté

`channel='sms'` ou `'push'` autorisés en DB mais Celery task n'envoie qu'email implicitement (et même pas, cf. F750).

#### F763 — Pas de schemas Pydantic pour bulk planning

#### F764 — Index `(tenant_id, id)` redondant avec PK clustered

---

### 3.4 P3

#### F765 — Pas de scheduling adaptatif (J+7, J+14, J+30 hardcoded ailleurs probablement)

#### F766 — `total_processed > 100` possible (limite par tenant, multi-tenant cumule)

---

## 4. Synthèse module 23

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 2 | F750 (envoi email absent), F751 (no retry policy) |
| P1 | 9 | F752 → F760 |
| P2 | 4 | F761 → F764 |
| P3 | 2 | F765, F766 |
| **Total** | **17** | F750 → F766 |

**Compteur cumulé après module 23** : ≈ 749 + 17 = **766 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : appeler le service notification dans `execute_scheduled_relances` (F750) — la fonction est **purement cosmétique** sans cet appel.
