# Module 24 — Évenements / Incidents (Marveline)

> **Phase C.** Audit du domaine événement métier (≠ réservation) : Evenement (FSM 8 statuts), EventIncident, IncidentAction, plan d'action, reporting.

---

## 1. Inventaire — lecture intégrale

| Fichier | LoC |
|---|---|
| `app/models/evenements.py` | 90 |
| `app/services/evenements.py` | 440 (parcours fonctions clés) |
| `app/repositories/evenements.py` | 328 (parcours) |
| `app/api/v1/endpoints/evenements.py` | 196 (parcours) |
| `app/schemas/evenements.py` | 179 (parcours) |

**Volume total** : 1 233 LoC.

---

## 2. Architecture observée

```
Evenement (FSM 8 statuts via EVENT_TRANSITIONS)
  planned → risk | in_progress | cancelled
  risk → in_progress | cancelled
  in_progress → incident | returned | cancelled
  incident → in_progress | damage | cancelled
  returned → damage | closed
  damage → closed
  closed/cancelled : terminal

EventIncident (cascade)
  declared_by FK accounts RESTRICT, owner_id SET NULL
  sla_hours default 24
  affected_items JSON

IncidentAction (cascade)
  status: todo → done (pas de matrice formelle)
  assignee_id FK accounts RESTRICT
  deadline Date
```

---

## 3. Frictions identifiées — module 24

> Compteur cumulé (mod. 01-23) ≈ 766. Module 24 ouvre à **F767**.

### 3.1 P0

#### F767 — `Evenement.reference String(50)` **sans UNIQUE constraint**

`models/evenements.py:13`. Aucun `unique=True` ni `UniqueConstraint(tenant_id, reference)`. Duplicates possibles si génération buggée.

---

#### F768 — `Evenement.status` String(30) sans CHECK enum

8 valeurs dans `EVENT_TRANSITIONS` Python (`planned, risk, in_progress, incident, damage, returned, closed, cancelled`) mais aucun CHECK SQL. Insertion `status="actif"` (typo) acceptée silencieusement → matrice Python ne match jamais → événement bloqué.

---

#### F769 — `create_incident` auto-transit `in_progress → incident` **en bypass** `_transition`

**Constat.** `services/evenements.py:197-198` :
```python
if ev.status == "in_progress":
    ev.status = "incident"
```

Pas d'appel à `_transition`. La transition est valide selon la matrice (`in_progress: [..., incident, ...]`) mais le code utilise une affectation directe. Si quelqu'un modifie la matrice plus tard, ce code ne suit pas.

---

#### F770 — `IncidentAction.status` String(20) sans CHECK enum (todo/in_progress/done)

`models/evenements.py:76`. Default `"todo"`. `close_action` (l. 237) écrit `"done"` directement. Aucun gardien transition ; aucun CHECK SQL.

---

### 3.2 P1

#### F771 — `EventIncident.declared_at: Mapped[str]` typé `str` mais TIMESTAMP

Pattern récurrent (cf. F648). `IncidentAction.created_at`/`updated_at` aussi `Mapped[str]`.

---

#### F772 — `affected_items JSON nullable=True default=list`

Le `default=list` (Python callable) appelé à chaque insert sans `server_default`. Si insertion via SQL direct sans valeur → NULL au lieu de `[]`. Drift `iter()` côté code.

---

#### F773 — `EventIncident.sla_hours` server_default `"24"` hardcoded

Pas configurable per tenant. Marveline 24h, mais Splendid B2B premium pourrait vouloir 4h.

---

#### F774 — Pas d'audit log sur `mark_returned`, `close_evenement`, `flag_risk`, `cancel_evenement`

---

#### F775 — `TenantMembership.status == "active"` string hardcoded

`services/evenements.py:80`. Pas de constante.

---

#### F776 — `EventIncident.declared_by FK accounts ondelete=RESTRICT`

Bloque suppression d'un account ayant déclaré des incidents — historique préservé OK mais offboarding employé devient impossible sans soft-delete strict.

---

#### F777 — `IncidentAction.assignee_id FK accounts ondelete=RESTRICT` (même problème)

---

#### F778 — Pas de notification à l'assignee à la création d'IncidentAction

---

#### F779 — `Evenement.notes` Text non chiffré (PII)

---

#### F780 — `IncidentAction.deadline Date` sans timezone (date locale ambiguë)

---

#### F781 — Pas d'index `(tenant_id, status, event_date)` sur Evenement (dashboard)

---

#### F782 — `_RESCHEDULE_ALLOWED` liste de statuts non listée explicitement dans le grep — à confirmer

---

#### F783 — `EventIncident.severity String(20)` libre, pas de CHECK

---

#### F784 — Pas de soft-delete sur EventIncident / IncidentAction

`SoftDeleteMixin` absent. Suppression = cascade hard delete.

---

#### F785 — `sla_hours` aucune auto-escalation si dépassé (pas de Celery task)

---

#### F786 — `EventIncident.description Text NOT NULL` peut contenir PII non chiffré

---

### 3.3 P2

#### F787 — Format `reference` Evenement non documenté (vs RES-/INV-/VTE-/DEV-)

#### F788 — `IncidentAction.created_at`/`updated_at` `server_default="NOW()"` string

#### F789 — `affected_items JSON` sans schema validation Pydantic

#### F790 — Comments mix français/anglais

---

### 3.4 P3

#### F791 — `Evenement.location String(255)` au lieu de structuré

---

## 4. Synthèse module 24

| Sévérité | Nb | Frictions |
|---|---|---|
| P0 | 4 | F767 (no UNIQUE reference), F768 (no CHECK status), F769 (bypass FSM create_incident), F770 (action status no CHECK) |
| P1 | 16 | F771 → F786 |
| P2 | 4 | F787 → F790 |
| P3 | 1 | F791 |
| **Total** | **25** | F767 → F791 |

**Compteur cumulé après module 24** : ≈ 766 + 25 = **791 frictions**.

---

## 5. Décision architecturale

> **P0 immédiat** : (1) UNIQUE constraint reference (F767) ; (2) CHECK enum status (F768) ; (3) `_transition` partout (F769 + F770) ; (4) typing `Mapped[datetime]` (F771).
