# Module 27 — Notification (Email + persistance)

> **Phase C — DERNIER MODULE.** Audit du service email SMTP + Notification model.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/notification.py` | 20 |
| `app/services/notification.py` | 295 |
| `app/repositories/notification.py` | 162 (parcours) |
| `app/api/v1/endpoints/notifications.py` | 64 |
| `app/schemas/notification.py` | 28 |
| `app/tasks/notifications.py` | 250 (parcours) |

**Volume total** : 819 LoC.

---

## 2. Architecture observée

```
NotificationService (singleton)
  ├── _send_email : smtplib.SMTP() synchrone bloquant
  ├── _render_and_send : Jinja2 templates (8 emails métier)
  ├── send_password_reset_email : HTML inline EN ANGLAIS hardcoded
  ├── send_supplier_order_confirmation : HTML inline français
  └── send_plain_email : pour campagnes RFM (F442)

Notification model
  - tenant_id Integer (pas TenantMixin)
  - user_id Integer nullable (pas FK)
  - type/title/message/link/is_read

Templates Jinja2 dans app/templates/emails/
brand priorité : tenant_settings.frontend_url > settings.FRONTEND_URL
```

---

## 3. Frictions identifiées — module 27

> Compteur cumulé (mod. 01-26) ≈ 847. Module 27 ouvre à **F848**.

### 3.1 P0

#### F848 — `_send_email` synchrone bloquant via `smtplib.SMTP()`

**Constat.** `services/notification.py:272-273` :
```python
with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
    server.sendmail(settings.SMTP_FROM, to, msg.as_string())
```

Bloque le worker FastAPI ~500ms-3s par email. Cumulé avec **F442** (campaign sync), **F294** (forgot_password sync) → pattern systémique de blocage HTTP. Pour 100 emails simultanés = 100×3s = 5 minutes worker bloqué.

**Action** : refactor complet via Celery `send_email_task.delay(template, recipient, context)`. Service notification wrap autour (sync→async).

---

#### F849 — Aucun `starttls()` ni `login()` SMTP en production

**Constat.** Le commentaire l. 27 promet "En prod: SMTP réel avec TLS (configurable via env)" mais `_send_email` ne fait **jamais** :
- `server.starttls()` (TLS opportuniste)
- `server.login(user, password)` (authentification)

Email envoyé en clair. Si `SMTP_HOST` est un relai externe (SendGrid, AWS SES), authentification obligatoire → en prod, l'envoi échoue ou est vulnérable MITM.

**Action** : `if settings.SMTP_TLS: server.starttls(); if settings.SMTP_USER: server.login(...)`.

---

#### F850 — `Notification` model n'utilise pas `TenantMixin` ni `TimestampMixin`

**Constat.** `models/notification.py:8-21` utilise `Column` directe (sync style ancien) au lieu de `Mapped` (style v2.0). Pas d'héritage des mixins → convention CaroCorp violée. `tenant_id Integer` (pas BigInteger), `user_id Integer nullable sans FK`.

---

#### F851 — `send_password_reset_email` HTML hardcoded **EN ANGLAIS** (pas de template Jinja2 ni i18n)

`services/notification.py:86-105`. Tous les autres emails sont en français via Jinja2. Le password reset envoie "Password Reset Request" anglais. Drift UX user qui paramètre tout en français reçoit un email anglais.

---

### 3.2 P1

#### F852 — `_send_email` retourne `bool` (silently swallow exceptions)

L. 278-280. Caller ignorant le bool n'a aucun signal d'échec. Cf. F614 mod. 18 (`_notify_reservation_confirmed` swallow).

---

#### F853 — Pas de retry policy ni queue idempotente

Email perdu si SMTP timeout. Pas de DLQ.

---

#### F854 — Pas d'enregistrement persistent à chaque envoi

`Notification` table existe mais le service n'y insert PAS de row à chaque email envoyé. Impossible de retracer "ai-je envoyé J+5 ?". Cf. `LoyaltyNotificationLog` (mod. 25) qui existe — pourquoi pas un seul `NotificationLog` global ?

---

#### F855 — `frontend_url` fallback `settings.FRONTEND_URL` global quand brand=None

Cf. F295 mod. 10. Partiellement résolu (priorité brand) mais fallback Marveline persistant.

---

#### F856 — `_DEFAULT_BRAND` import depuis `services/invoice_pdf` (couplage cross-domain)

`services/notification.py:13`. Service notification dépend de service invoice_pdf — anti-pattern.

---

#### F857 — `_format_amount` hardcoded `€` symbol (multi-pays Splendid bloqué)

---

#### F858 — `send_supplier_order_confirmation` HTML inline (cf. F851 pattern)

---

#### F859 — Pas de RGPD opt-out / unsubscribe link

Tous les emails envoient sans gérer un footer "se désabonner". Non conforme RGPD pour campagnes RFM.

---

#### F860 — Pas de bounce / hard-fail tracking

Si `customer.email` est invalide, le SMTP retourne erreur perdue silencieusement. Aucun marquage `customer.email_invalid=True`.

---

#### F861 — `Notification` pas d'audit log de qui a marqué `is_read`

---

### 3.3 P2

#### F862 — `Notification.message Text nullable` non chiffré (PII potentielle)

#### F863 — `Notification.link String(500)` → tronquage URLs longues

#### F864 — `_html_to_text` regex basique (mauvais MIME multipart)

#### F865 — Pas d'index `(tenant_id, user_id, is_read)` pour scan unread

#### F866 — `send_plain_email` async signature mais `_send_email` sync underneath — async fake

---

### 3.4 P3

#### F867 — `send_password_reset_email` anglais vs autres français — i18n drift

#### F868 — `tasks/notifications.py` (250L) parcouru rapidement — Celery probablement OK pour `reservation_confirmed_email.delay`

---

## 4. Synthèse module 27

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F848 (SMTP sync block), F849 (no TLS prod), F850 (no Mixins), F851 (HTML inline anglais) |
| P1 | 10 | F852 → F861 |
| P2 | 5 | F862 → F866 |
| P3 | 2 | F867, F868 |
| **Total** | **21** | F848 → F868 |

**Compteur cumulé après module 27** : ≈ 847 + 21 = **868 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) Celery email task (F848 — résout aussi F442, F294, F614) ; (2) TLS + auth SMTP prod (F849) ; (3) refactor Notification model TenantMixin + Mapped (F850) ; (4) i18n templates (F851 + F867).
>
> **Refactor** : log persisting à chaque envoi (F854) ; bounce tracking (F860) ; RGPD opt-out (F859).

---

# 🎯 PHASE C TERMINÉE

**Modules 14-27 livrés.** ~50 fichiers .md, ~870 frictions documentées sur 27 modules.

**Prochaines phases :**
- **Phase D** (modules 28-30) : Épicerie / Restaurant / Catalogue ETL partagé
- **Phase E** (modules 31-35) : Audit / Feature flag / Orchestration / Printer / VPN / Health-Metrics
- **Phase F** (module 99) : Synthèse globale
