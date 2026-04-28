# Sprint 1 — PROD FIRE-DRILL 🔥

> **STATUT** : ⚠️ **PRODUCTION CASSÉE + VULNÉRABILITÉS SÉCURITÉ EXPLOITABLES** — STOP all feature work jusqu'à livraison.
> **DURÉE MAX** : 1 semaine. **DÉPLOIEMENT IMMÉDIAT** une fois CI verte.
> **RAISON** : 12 bugs P0 confirmés en prod (audits cohérence Phase 1↔Phase 3 vagues 1-6) — 4 métier + 3 infra + 5 sécurité auth/RGPD.
> **BLOCKER COMMERCIAL** : F368 (WebAuthn RP_ID hardcodé Marveline) bloque la démo Splendid Events prévue le 28/04.

## Vue d'ensemble

### Bugs métier (livraison fonctionnelle)

| Story | Friction | Sévérité | Bug ID | Owner | Est. | Bloque |
|---|---|---|---|---|---|---|
| **S1.T1** | F906 marmite recette | P0 PROD | MARMITE-QPP-01 | Dev1 | 0.5 j | Restaurants ne peuvent PAS lancer marmite |
| **S1.T2** | F1058 relance fictive | P0 PROD | RELANCE-FAKE-SENT-01 | Dev1 | 1.5 j | Toutes les relances clients (trésorerie) |
| **S1.T3** | F870 vente check_stock | P1 | EPI-CHECKSTK-01 | Dev3 | 0.5 j | UX caissier (500 au lieu de 409 propre) |
| **S1.T4** | F1055 auto_suspend | P1 compliance | SOC2-AUTOSUSP-01 | Lead | 1.5 j | Compliance SOC2 §10 (théâtre actuel) |

### Bugs infra (HTTP 500 latents + DoS monitoring)

| Story | Friction | Sévérité | Bug ID | Owner | Est. | Bloque |
|---|---|---|---|---|---|---|
| **S1.T5** | F255 provisioning degraded await | P0 PROD | PROVISION-DEGRADED-AWAIT-01 | Dev1 | 0.25 j | Mode dégradé admin inopérant (500 latent) |
| **S1.T6** | F1002 audit login excluded | P0 PROD | AUDIT-LOGIN-EXCL-01 | Dev2 | 0.5 j | RGPD Art.30 — brute-force invisible |
| **S1.T12** | F1126 metrics path DoS | P0 PROD | METRICS-PATH-DOS-01 | Dev1 | 0.25 j | DoS Prometheus (OOM via paths random) |

### Bugs sécurité auth (vulnérabilités exploitables)

| Story | Friction | Sévérité | Bug ID | Owner | Est. | Exploit |
|---|---|---|---|---|---|---|
| **S1.T7** | F47 JWT audience bypass | P0 SEC | JWT-AUD-BYPASS-01 | Lead | 0.25 j | Cross-app escalation token sans `type` |
| **S1.T8** | F370 stepup WebAuthn cassé | P0 SEC | STEPUP-WEBAUTHN-01 | Dev2 | 0.5 j | 100% stepup WebAuthn échouent |
| **S1.T9** | F296 OAuth-only TypeError | P0 SEC | OAUTH-ONLY-TYPEERROR-01 | Dev2 | 0.25 j | 500 + user enumeration |
| **S1.T10** | F404 OAuth MFA bypass | P0 SEC | OAUTH-MFA-BYPASS-01 | Dev2 | 1 j | MFA contournée via Google/MS login |
| **S1.T11** | F368 WebAuthn RP_ID hardcodé | P0 SEC + COMMERCIAL | WEBAUTHN-RPID-MULTITENANT-01 | Dev2 + Lead | 1 j | **Bloque démo Splendid 28/04** |

**Total effort** : 7.5 jours-homme. **Parallélisable** : oui (T1-T12 indépendants).
- **Ligne 1** (Dev1) : T1+T2+T5+T12+T3 = 3 jours
- **Ligne 2** (Dev2) : T6+T8+T9+T10+T11 (collab) = 2.5 jours
- **Ligne 3** (Dev3) : T3 collaboration + Smoke tests = 0.5 jour
- **Ligne 4** (Lead) : T4+T7+T11 (collab) = 2.75 jours

**Livraison cible** : 3 jours avec 4 devs en parallèle.

**Channel Slack dédié** : `#devup-eng-fire-drill` (créé puis archivé après livraison).

---

# Story S1.T1 — F906 Fix marmite `quantite_par_portion` → `quantite_par_batch`

## Contexte

**Bug ID** : MARMITE-QPP-01
**Friction** : F906 (cf. `docs/architecture-audit-2026-04-26/29-restaurant.md` §3.1)
**Module Bloc** : 5 (avancée prioritaire dans Sprint 1)
**Sévérité** : P0 PROD — restaurant ne peut PAS lancer une marmite avec recette définie.
**Détecté** : 2026-04-27 audit cohérence
**Confirmé en code** : `app/services/restaurant/instance_preparation.py:118`

### Description

Le service `_verifier_et_consommer_recette` (`InstancePreparationService`) lit l'attribut `ligne.quantite_par_portion` qui **n'existe pas** dans le modèle `RecetteTypePreparation`. Le model déclare uniquement `quantite_par_batch` (cf. `app/models/restaurant/recette_type_preparation.py:49`).

**Code bugué actuel** (`app/services/restaurant/instance_preparation.py:111-138`) :
```python
async def _verifier_et_consommer_recette(
    self, tp_id: int, nb_portions: int
) -> None:
    """Vérifie et consomme les stocks de la recette (SELECT FOR UPDATE par ingrédient)."""
    recette = await self._recette_repo.list_by_type_preparation(tp_id)
    now = datetime.now(timezone.utc)
    for ligne in recette:
        qtite_requise = Decimal(str(ligne.quantite_par_portion)) * nb_portions  # ❌ AttributeError
        ing = await self._ing_repo.get_by_id_lock(ligne.ingredient_id)
        # ...
```

**Conséquence runtime** : tout `POST /instances` (lancement marmite) avec une recette ≥1 ligne lève `AttributeError: 'RecetteTypePreparation' object has no attribute 'quantite_par_portion'` → propagée en `500 Internal Server Error` au caissier cuistot.

**Pourquoi ce n'est pas détecté en CI** : aucun test E2E `POST /instances` avec recette définie. Probablement les recettes sont vides en pré-prod, ou la fonctionnalité n'est utilisée qu'en prod réelle.

### Sémantique correcte

Le commentaire ligne 50 du model dit : *"Quantité de l'ingrédient pour un batch complet (en unité de l'ingrédient)"*.

Le service multiplie par `nb_portions`. **Si l'attribut existait avec ce nom, la formule serait fausse aussi** :
- `quantite_par_batch` = quantité pour 1 batch complet (= `tp.portions_par_batch` portions)
- `nb_portions` = portions effectivement lancées (peut être < `portions_par_batch` si on cuit moins qu'un batch)
- Quantité réelle requise = `quantite_par_batch × (nb_portions / tp.portions_par_batch)`

## Solution

### Code corrigé

```python
# app/services/restaurant/instance_preparation.py:111-140 (ligne 118 modifiée)
async def _verifier_et_consommer_recette(
    self, tp_id: int, nb_portions: int
) -> None:
    """Vérifie et consomme les stocks de la recette (SELECT FOR UPDATE par ingrédient).
    
    Formule de consommation :
        qte_requise = quantite_par_batch × (nb_portions / portions_par_batch)
    
    Exemple : recette "Carry poulet" avec quantite_par_batch=5kg poulet pour
    portions_par_batch=20. Si on cuit nb_portions=15, on consomme 5×(15/20)=3.75kg.
    """
    # Charger le TypePreparation pour avoir portions_par_batch
    tp = await self._tp_repo.get_by_id(tp_id)
    if tp is None:
        raise NotFound("TypePreparation", tp_id)
    if tp.portions_par_batch <= 0:
        raise ValueError(f"TypePreparation {tp_id} a portions_par_batch <= 0")
    
    recette = await self._recette_repo.list_by_type_preparation(tp_id)
    now = datetime.now(timezone.utc)
    ratio = Decimal(nb_portions) / Decimal(tp.portions_par_batch)
    
    for ligne in recette:
        qtite_requise = Decimal(str(ligne.quantite_par_batch)) * ratio
        ing = await self._ing_repo.get_by_id_lock(ligne.ingredient_id)
        if ing is None:
            raise NotFound("IngredientRestaurant", ligne.ingredient_id)
        stock_actuel = Decimal(str(ing.stock_actuel))
        if stock_actuel < qtite_requise:
            raise StockRequisInsuffisant(
                f"Ingrédient {ing.nom} : {stock_actuel} dispo, {qtite_requise} requis"
            )
        nouveau_stock = stock_actuel - qtite_requise
        ing.stock_actuel = nouveau_stock
        await self._mouv_repo.create(
            ingredient_id=ing.id,
            type_mouvement="consommation",
            quantite=-qtite_requise,
            stock_apres=nouveau_stock,
            date_mouvement=now,
        )
        await self._db.flush()
        stock_alerte = Decimal(str(ing.stock_alerte))
        await self._gerer_alertes_ingredient(ing.id, nouveau_stock, stock_alerte)
```

### Diff exact

```diff
--- a/app/services/restaurant/instance_preparation.py
+++ b/app/services/restaurant/instance_preparation.py
@@ -111,12 +111,29 @@ async def _verifier_et_consommer_recette(
     async def _verifier_et_consommer_recette(
         self, tp_id: int, nb_portions: int
     ) -> None:
-        """Vérifie et consomme les stocks de la recette (SELECT FOR UPDATE par ingrédient)."""
+        """Vérifie et consomme les stocks de la recette (SELECT FOR UPDATE par ingrédient).
+
+        Formule de consommation :
+            qte_requise = quantite_par_batch × (nb_portions / portions_par_batch)
+        """
+        tp = await self._tp_repo.get_by_id(tp_id)
+        if tp is None:
+            raise NotFound("TypePreparation", tp_id)
+        if tp.portions_par_batch <= 0:
+            raise ValueError(f"TypePreparation {tp_id} a portions_par_batch <= 0")
+
         recette = await self._recette_repo.list_by_type_preparation(tp_id)
         now = datetime.now(timezone.utc)
+        ratio = Decimal(nb_portions) / Decimal(tp.portions_par_batch)
+
         for ligne in recette:
-            qtite_requise = Decimal(str(ligne.quantite_par_portion)) * nb_portions
+            qtite_requise = Decimal(str(ligne.quantite_par_batch)) * ratio
             ing = await self._ing_repo.get_by_id_lock(ligne.ingredient_id)
             if ing is None:
                 raise NotFound("IngredientRestaurant", ligne.ingredient_id)
```

## Fichiers à modifier (liste exhaustive)

| Fichier | Type modif | Lignes |
|---|---|---|
| `app/services/restaurant/instance_preparation.py` | Edit (fix) | L. 111-140 (~12 lignes ajoutées/modifiées) |
| `tests/integration/restaurant/test_instance_preparation.py` | New ou Edit | +1 nouveau test E2E |
| `tests/unit/restaurant/test_instance_preparation_service.py` | Edit | +2 tests unitaires |

**Aucune migration DB nécessaire** (model `RecetteTypePreparation` déjà correct, c'est le service qui ment).

**Aucun changement schema Pydantic** (l'API publique `POST /instances` ne change pas).

## Tests à écrire

### Test E2E (integration)

```python
# tests/integration/restaurant/test_instance_preparation.py
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.restaurant.type_preparation import TypePreparation
from app.models.restaurant.recette_type_preparation import RecetteTypePreparation
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from tests.factories import TenantFactory, AccountFactory


@pytest.mark.asyncio
async def test_post_instances_with_recette_consumes_stock_correctly(
    async_client, async_db: AsyncSession, restaurant_tenant
):
    """F906 regression test : POST /instances avec recette doit consommer le stock
    selon la formule quantite_par_batch × (nb_portions / portions_par_batch).
    """
    # Setup : ingredient avec stock 10kg
    ingredient = IngredientRestaurant(
        tenant_id=restaurant_tenant.id,
        nom="Poulet",
        unite_stock="kg",
        stock_actuel=Decimal("10.000"),
        stock_alerte=Decimal("0"),
    )
    async_db.add(ingredient)
    await async_db.flush()
    
    # TypePreparation : Carry poulet, 20 portions par batch
    tp = TypePreparation(
        tenant_id=restaurant_tenant.id,
        nom="Carry poulet",
        portions_par_batch=20,
        seuil_alerte_portions=5,
        actif=True,
    )
    async_db.add(tp)
    await async_db.flush()
    
    # Recette : 5kg de poulet par batch (= 0.25kg par portion)
    recette = RecetteTypePreparation(
        tenant_id=restaurant_tenant.id,
        type_preparation_id=tp.id,
        ingredient_id=ingredient.id,
        quantite_par_batch=Decimal("5.000"),
    )
    async_db.add(recette)
    await async_db.commit()
    
    # POST /instances : lance 15 portions
    response = await async_client.post(
        "/api/v1/restaurant/instances",
        json={
            "type_preparation_id": tp.id,
            "portions_initiales": 15,
            "date_cuisine": "2026-04-28",
        },
        headers={"X-Tenant-ID": str(restaurant_tenant.id)},
    )
    
    # Assertions
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["portions_restantes"] == 15
    
    # Stock ingrédient : 10 - 5×(15/20) = 10 - 3.75 = 6.25 kg
    await async_db.refresh(ingredient)
    assert ingredient.stock_actuel == Decimal("6.250")


@pytest.mark.asyncio
async def test_post_instances_with_recette_insufficient_stock_returns_409(
    async_client, async_db, restaurant_tenant
):
    """Si le stock est insuffisant, l'API doit retourner 409 (pas 500)."""
    ingredient = IngredientRestaurant(
        tenant_id=restaurant_tenant.id,
        nom="Poulet",
        stock_actuel=Decimal("1.000"),  # 1kg, insuffisant
    )
    async_db.add(ingredient)
    tp = TypePreparation(tenant_id=restaurant_tenant.id, nom="Carry", portions_par_batch=20, actif=True)
    async_db.add(tp)
    await async_db.flush()
    recette = RecetteTypePreparation(
        tenant_id=restaurant_tenant.id,
        type_preparation_id=tp.id,
        ingredient_id=ingredient.id,
        quantite_par_batch=Decimal("5.000"),
    )
    async_db.add(recette)
    await async_db.commit()
    
    response = await async_client.post(
        "/api/v1/restaurant/instances",
        json={"type_preparation_id": tp.id, "portions_initiales": 15, "date_cuisine": "2026-04-28"},
        headers={"X-Tenant-ID": str(restaurant_tenant.id)},
    )
    
    assert response.status_code == 409
    assert "STOCK" in response.json().get("error_code", "").upper() or "stock" in response.json().get("detail", "").lower()
```

### Tests unitaires

```python
# tests/unit/restaurant/test_instance_preparation_service.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

from app.services.restaurant.instance_preparation import InstancePreparationService


@pytest.mark.asyncio
async def test_verifier_et_consommer_recette_formule_correcte():
    """F906 unit test : formule qte = quantite_par_batch × (nb_portions / portions_par_batch)."""
    # Mocks
    db = AsyncMock()
    tp_repo = AsyncMock()
    recette_repo = AsyncMock()
    ing_repo = AsyncMock()
    mouv_repo = AsyncMock()
    alerte_repo = AsyncMock()
    
    tp_repo.get_by_id.return_value = type("TP", (), {"id": 1, "portions_par_batch": 20})
    
    ligne_recette = type("Ligne", (), {
        "ingredient_id": 10,
        "quantite_par_batch": Decimal("5.000"),
    })
    recette_repo.list_by_type_preparation.return_value = [ligne_recette]
    
    ing = type("Ing", (), {
        "id": 10, "nom": "Poulet",
        "stock_actuel": Decimal("10.000"),
        "stock_alerte": Decimal("0"),
    })
    ing_repo.get_by_id_lock.return_value = ing
    
    service = InstancePreparationService(
        db=db, tp_repo=tp_repo, recette_repo=recette_repo,
        ing_repo=ing_repo, mouv_repo=mouv_repo, alerte_repo=alerte_repo,
    )
    
    # Act : 15 portions, batch=20, qty_per_batch=5kg
    await service._verifier_et_consommer_recette(tp_id=1, nb_portions=15)
    
    # Assert : 5 × (15/20) = 3.75 kg consommés
    assert ing.stock_actuel == Decimal("6.250")
    mouv_repo.create.assert_called_once()
    call_kwargs = mouv_repo.create.call_args.kwargs
    assert call_kwargs["quantite"] == Decimal("-3.750")
    assert call_kwargs["stock_apres"] == Decimal("6.250")


@pytest.mark.asyncio
async def test_verifier_recette_no_attributeerror_quantite_par_portion():
    """F906 unit test : régression — l'attribut quantite_par_portion ne doit JAMAIS être lu."""
    db = AsyncMock()
    tp_repo = AsyncMock()
    recette_repo = AsyncMock()
    ing_repo = AsyncMock()
    mouv_repo = AsyncMock()
    alerte_repo = AsyncMock()
    
    tp_repo.get_by_id.return_value = type("TP", (), {"id": 1, "portions_par_batch": 10})
    
    # Ligne sans attribut quantite_par_portion (vrai modèle)
    ligne = type("Ligne", (), {
        "ingredient_id": 1,
        "quantite_par_batch": Decimal("1.0"),
    })
    recette_repo.list_by_type_preparation.return_value = [ligne]
    ing_repo.get_by_id_lock.return_value = type("Ing", (), {
        "id": 1, "nom": "X",
        "stock_actuel": Decimal("100"),
        "stock_alerte": Decimal("0"),
    })
    
    service = InstancePreparationService(db=db, tp_repo=tp_repo, recette_repo=recette_repo, ing_repo=ing_repo, mouv_repo=mouv_repo, alerte_repo=alerte_repo)
    
    # Doit pas raise AttributeError
    await service._verifier_et_consommer_recette(tp_id=1, nb_portions=5)
```

## Definition of Done

- [ ] Code modifié dans `app/services/restaurant/instance_preparation.py` (diff vu en review)
- [ ] Test E2E `test_post_instances_with_recette_consumes_stock_correctly` écrit et passe
- [ ] Test E2E `test_post_instances_with_recette_insufficient_stock_returns_409` écrit et passe
- [ ] Test unitaire `test_verifier_et_consommer_recette_formule_correcte` écrit et passe
- [ ] Test unitaire `test_verifier_recette_no_attributeerror_quantite_par_portion` écrit et passe
- [ ] `pytest tests/` complet vert (régression 1782 tests existants)
- [ ] Code review approved par 1 peer + Lead
- [ ] Déploiement prod confirmé via curl smoke test : `POST /api/v1/restaurant/instances` avec recette → 200
- [ ] Memory MEMORY.md mise à jour : `bug-marmite-quantite-par-portion.md` marqué **résolu** avec date
- [ ] Commit message format : `fix(B5.S1): F906 marmite — quantite_par_portion → quantite_par_batch + formule (Closes MARMITE-QPP-01)`

## Risques

| Risque | P × I | Mitigation |
|---|---|---|
| Donnée existante en DB avec `quantite_par_batch` mal saisie (admin a saisi par portion au lieu de par batch) | 2×3=6 | Audit data avant fix : `SELECT * FROM restaurant_recettes_type_preparation WHERE quantite_par_batch < 0.1` (suspicieux). Communication client si valeurs aberrantes détectées. |
| Régression sur autres callers de `_verifier_et_consommer_recette` | 1×2=2 | Grep `_verifier_et_consommer_recette` montre 1 seul call site (`InstancePreparationService.create`). Faible. |

## Rollback

Si le fix introduit régression en prod (improbable, mais procédure) :
1. `git revert <commit_sha>` sur main.
2. Push + déploiement immédiat.
3. Le bug F906 redevient actif → escalade L1 immédiate.
4. Investigation root cause + nouveau fix.

---

# Story S1.T2 — F1058 Fix relance email réel via EmailGateway minimal

## Contexte

**Bug ID** : RELANCE-FAKE-SENT-01
**Friction** : F1058 (cf. `docs/architecture-audit-2026-04-26/33-orchestration-celery.md` §3.1)
**Module Bloc** : 6 (avancée prioritaire dans Sprint 1)
**Sévérité** : P0 PROD CRITIQUE — clients ne reçoivent jamais leurs relances de paiement, faux signal massif logs.
**Détecté** : 2026-04-27 audit cohérence
**Confirmé en code** : `app/tasks/relances.py:75-87`

### Description

La task Celery `execute_scheduled_relances` (cron `:15` chaque heure, queue `notifications`) parcourt les `Relance(status='scheduled')` et marque `status='sent'` + log "Relance %d sent" — **mais n'envoie AUCUN email**.

**Code bugué actuel** (`app/tasks/relances.py:75-87`) :
```python
# ... (charge invoice, customer, etc.)
relance.status = "sent"
relance.sent_at = now

if not invoice.first_reminder_sent_at:
    invoice.first_reminder_sent_at = now
invoice.last_reminder_sent_at = now

total_sent += 1
logger.info(
    "Relance %d sent: invoice=%s customer=%s channel=%s tenant=%d",
    relance.id, invoice.invoice_number, customer.email,
    relance.channel, tid,
)
# ❌ AUCUN appel à notification_service.send_email()
```

**Conséquences** :
1. **Trésorerie Marveline impactée** : factures impayées s'accumulent sans relance réelle.
2. **Faux signal massif logs** : `logger.info("Relance %d sent...")` apparaît dans Loki mais l'email n'a pas été envoyé.
3. **Compteurs `invoice.first_reminder_sent_at`/`last_reminder_sent_at` mis à jour** : workflow progresse vers J+30/J+60 sans aucun envoi.

### Pourquoi ce n'est pas détecté en CI

Aucun test E2E qui vérifie l'envoi réel email. Le test `test_relance_status_sent` (s'il existe) vérifie probablement le statut `sent` mais pas l'appel gateway.

## Solution

Hotfix minimal Sprint 1 : appeler `notification_service.send_relance_email()` AVANT le marquage `status='sent'`. Pattern complet `EmailGateway` Postmark sera implémenté Bloc 6.S1 (~B6 plus tard). Ici, on utilise le `notification_service` existant en mode "best effort" et on track les échecs via `relance.email_send_error`.

### Code corrigé

```python
# app/tasks/relances.py — version hotfix Sprint 1
"""Celery task — exécution des relances planifiées."""
import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.relances.execute_scheduled_relances",
    queue="notifications",
    bind=True,
    max_retries=2,
    default_retry_delay=300,  # 5 min entre retries
)
def execute_scheduled_relances(self):
    """Execute les relances dont scheduled_at <= now et status = 'scheduled'.

    Pour chaque relance :
    1. Charger facture + reservation + customer
    2. Skip si invoice.status in ('paid', 'cancelled')
    3. Skip si customer.email manquant
    4. **APPELER notification_service.send_relance_email()** — F1058 fix
    5. Si gateway succès (return True) → relance.status='sent', sent_at=now()
    6. Si gateway échec → relance.status='failed', email_send_error=<msg>, retry next cycle

    Beat schedule : toutes les heures à :15.
    """
    from app.core.database import get_db_context
    from app.models.relance import Relance
    from app.models.invoice import Invoice
    from app.models.reservation import Reservation
    from app.models.customer import Customer
    from app.models.tenant import Tenant
    from app.services.notification import notification_service

    now = datetime.now(timezone.utc)
    total_sent = 0
    total_failed = 0
    total_skipped = 0
    total_processed = 0

    with get_db_context() as db:
        tenant_ids = [
            r[0]
            for r in db.query(Tenant.id).filter(Tenant.status == "active").all()
        ]

        for tid in tenant_ids:
            relances = (
                db.query(Relance)
                .filter(
                    Relance.tenant_id == tid,
                    Relance.status == "scheduled",
                    Relance.scheduled_at <= now,
                )
                .limit(100)
                .all()
            )

            for relance in relances:
                total_processed += 1
                try:
                    invoice = db.get(Invoice, relance.invoice_id)
                    if not invoice:
                        logger.warning("Relance %d skip: invoice %d not found", relance.id, relance.invoice_id)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    if invoice.status in ("paid", "cancelled"):
                        logger.info("Relance %d skip: invoice %s already %s",
                                    relance.id, invoice.invoice_number, invoice.status)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    reservation = db.get(Reservation, invoice.reservation_id) if invoice.reservation_id else None
                    customer = db.get(Customer, reservation.customer_id) if reservation else None

                    if not customer or not customer.email:
                        logger.warning("Relance %d skip: no customer email (invoice=%s)",
                                       relance.id, invoice.invoice_number)
                        relance.status = "cancelled"
                        relance.cancelled_at = now
                        total_skipped += 1
                        continue

                    # === F1058 FIX : ENVOI EMAIL RÉEL ===
                    tenant = db.get(Tenant, tid)
                    try:
                        sent_ok = notification_service.send_relance_email(
                            email=customer.email,
                            customer_name=f"{customer.first_name or ''} {customer.last_name or ''}".strip()
                                          or customer.company_name or "Client",
                            invoice_number=invoice.invoice_number,
                            invoice_total_cts=invoice.total_ttc_cents,
                            invoice_due_date=invoice.due_date.isoformat() if invoice.due_date else "",
                            relance_level=relance.level,
                            tenant_brand_name=tenant.brand_display_name if hasattr(tenant, "brand_display_name") else "Marveline",
                        )
                    except Exception as email_exc:
                        logger.exception("Relance %d email gateway error: %s", relance.id, email_exc)
                        sent_ok = False
                        email_error = str(email_exc)[:500]

                    if sent_ok:
                        # Marquage 'sent' UNIQUEMENT après confirmation gateway
                        relance.status = "sent"
                        relance.sent_at = now
                        relance.email_send_error = None
                        if not invoice.first_reminder_sent_at:
                            invoice.first_reminder_sent_at = now
                        invoice.last_reminder_sent_at = now

                        total_sent += 1
                        logger.info(
                            "Relance %d sent OK: invoice=%s customer=%s channel=%s tenant=%d",
                            relance.id, invoice.invoice_number, customer.email,
                            relance.channel, tid,
                        )
                    else:
                        # Échec → marquer 'failed', retry next cycle
                        relance.status = "failed"
                        relance.email_send_error = locals().get("email_error", "gateway returned False")
                        total_failed += 1
                        logger.error(
                            "Relance %d FAILED: invoice=%s customer=%s error=%s",
                            relance.id, invoice.invoice_number, customer.email,
                            relance.email_send_error,
                        )

                except Exception:
                    logger.exception("Relance %d unexpected failure — will retry next cycle", relance.id)
                    total_failed += 1

        db.commit()
        logger.info(
            "[relances] Executed: sent=%d failed=%d skipped=%d total=%d across %d tenants",
            total_sent, total_failed, total_skipped, total_processed, len(tenant_ids),
        )
        return {
            "sent": total_sent,
            "failed": total_failed,
            "skipped": total_skipped,
            "total": total_processed,
        }
```

### Ajout `notification_service.send_relance_email()`

Le `NotificationService` actuel a déjà des méthodes Jinja2 pour password reset, supplier order. On ajoute une méthode `send_relance_email` dédiée :

```python
# app/services/notification.py — ajout en fin de classe
def send_relance_email(
    self,
    *,
    email: str,
    customer_name: str,
    invoice_number: str,
    invoice_total_cts: int,
    invoice_due_date: str,
    relance_level: int,
    tenant_brand_name: str,
) -> bool:
    """Envoie email de relance impayé.
    
    F1058 fix Sprint 1 : utilise SMTP direct via _render_and_send.
    Migration vers EmailGateway Postmark async = Bloc 6 §6.2.1 (B6.S1).
    
    Returns:
        True si envoi succès (gateway 200), False sinon.
    """
    subject = f"Relance facture {invoice_number} — Niveau {relance_level}"
    total_eur = invoice_total_cts / 100
    
    # Template inline minimal (templates Jinja2 complets = B6.S1)
    body_html = f"""
    <html><body style="font-family: Arial, sans-serif;">
    <p>Bonjour {customer_name},</p>
    <p>Sauf erreur de notre part, votre facture <strong>{invoice_number}</strong>
    d'un montant de <strong>{total_eur:.2f} €</strong> (échéance {invoice_due_date})
    n'a pas encore été réglée.</p>
    <p>Niveau de relance : {relance_level} (sur 3).</p>
    <p>Merci de procéder au règlement dans les meilleurs délais.</p>
    <p>Cordialement,<br>L'équipe {tenant_brand_name}</p>
    </body></html>
    """
    
    try:
        return self._send_email(to=email, subject=subject, body_html=body_html)
    except Exception as exc:
        logger.exception("send_relance_email failed for %s: %s", email, exc)
        return False
```

### Migration Alembic — colonne `email_send_error`

```python
# alembic/versions/2026_04_28_1430_add_relance_email_send_error.py
"""Add relance.email_send_error for F1058 fix tracking

Revision ID: a1b2c3d4e5f6
Revises: <previous>
Create Date: 2026-04-28 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "<previous_revision>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "relances",
        sa.Column("email_send_error", sa.String(length=500), nullable=True,
                  comment="F1058 — message d'erreur si l'envoi gateway a échoué"),
    )


def downgrade() -> None:
    op.drop_column("relances", "email_send_error")
```

### Ajout statut `'failed'` dans `Relance.status` enum

Vérifier que `Relance.status` accepte `'failed'`. Si CHECK enum strict :

```python
# alembic/versions/2026_04_28_1431_relance_status_add_failed.py
def upgrade():
    # Drop old CHECK + add new
    op.drop_constraint("ck_relances_status", "relances", type_="check")
    op.create_check_constraint(
        "ck_relances_status",
        "relances",
        "status IN ('scheduled', 'sent', 'cancelled', 'failed')"
    )

def downgrade():
    op.drop_constraint("ck_relances_status", "relances", type_="check")
    op.create_check_constraint(
        "ck_relances_status",
        "relances",
        "status IN ('scheduled', 'sent', 'cancelled')"
    )
```

## Fichiers à modifier

| Fichier | Type | Lignes |
|---|---|---|
| `app/tasks/relances.py` | Edit (refactor complet de la task) | ~80 lignes modifiées |
| `app/services/notification.py` | Edit (ajout `send_relance_email`) | +30 lignes |
| `app/models/relance.py` | Edit (ajout `email_send_error: Mapped[str \| None]`) | +5 lignes |
| `alembic/versions/2026_04_28_1430_add_relance_email_send_error.py` | New | ~25 lignes |
| `alembic/versions/2026_04_28_1431_relance_status_add_failed.py` | New | ~20 lignes |
| `tests/integration/tasks/test_relances.py` | New ou Edit | +3 nouveaux tests |
| `tests/unit/services/test_notification.py` | Edit | +2 tests |

## Tests à écrire

```python
# tests/integration/tasks/test_relances.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from app.tasks.relances import execute_scheduled_relances
from tests.factories import TenantFactory, CustomerFactory, ReservationFactory, InvoiceFactory, RelanceFactory


@pytest.mark.integration
def test_execute_scheduled_relances_sends_email_real(sync_db, tenant_marveline):
    """F1058 regression : la task doit appeler notification_service.send_relance_email()."""
    customer = CustomerFactory(tenant_id=tenant_marveline.id, email="client@example.com")
    reservation = ReservationFactory(tenant_id=tenant_marveline.id, customer=customer)
    invoice = InvoiceFactory(tenant_id=tenant_marveline.id, reservation=reservation, status="emitted",
                              invoice_number="INV-2026-001", total_ttc_cents=15000,
                              due_date=datetime.now(timezone.utc) - timedelta(days=10))
    relance = RelanceFactory(tenant_id=tenant_marveline.id, invoice=invoice,
                              status="scheduled", level=1,
                              scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1))
    sync_db.commit()
    
    with patch("app.services.notification.notification_service.send_relance_email", return_value=True) as mock_send:
        result = execute_scheduled_relances()
    
    # Assert : gateway appelé
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["email"] == "client@example.com"
    assert call_kwargs["invoice_number"] == "INV-2026-001"
    assert call_kwargs["invoice_total_cts"] == 15000
    
    # Assert : statut 'sent' uniquement après succès
    sync_db.refresh(relance)
    assert relance.status == "sent"
    assert relance.sent_at is not None
    
    assert result["sent"] == 1
    assert result["failed"] == 0


@pytest.mark.integration
def test_execute_scheduled_relances_failed_gateway_marks_failed(sync_db, tenant_marveline):
    """Si gateway retourne False, la relance doit être 'failed', pas 'sent'."""
    # ... (setup similaire)
    
    with patch("app.services.notification.notification_service.send_relance_email", return_value=False):
        result = execute_scheduled_relances()
    
    sync_db.refresh(relance)
    assert relance.status == "failed"
    assert relance.email_send_error is not None
    assert relance.sent_at is None
    
    assert result["sent"] == 0
    assert result["failed"] == 1


@pytest.mark.integration
def test_execute_scheduled_relances_gateway_exception_marks_failed(sync_db, tenant_marveline):
    """Si gateway raise exception, la relance doit être 'failed', pas 'sent'."""
    with patch("app.services.notification.notification_service.send_relance_email",
               side_effect=Exception("Postmark API timeout")):
        result = execute_scheduled_relances()
    
    sync_db.refresh(relance)
    assert relance.status == "failed"
    assert "Postmark" in relance.email_send_error
    assert result["failed"] == 1
```

## Definition of Done

- [ ] Migration Alembic `2026_04_28_1430_add_relance_email_send_error` testée upgrade/downgrade
- [ ] Migration Alembic `2026_04_28_1431_relance_status_add_failed` testée upgrade/downgrade
- [ ] Code `app/tasks/relances.py` modifié + revu
- [ ] Méthode `notification_service.send_relance_email()` ajoutée
- [ ] 3 tests integration écrits et passent (success / fail / exception)
- [ ] 2 tests unit `notification_service.send_relance_email` (templating + sender)
- [ ] `pytest tests/` complet vert
- [ ] Validation manuelle staging : déclencher manuellement la task → vérifier email reçu sur boîte test
- [ ] Code review approved par 1 peer + Lead
- [ ] Déploiement prod confirmé
- [ ] Monitoring 24h post-deploy : Loki query `task=execute_scheduled_relances result=*` montre `sent>0` ET `failed=0` sur 1 cycle complet
- [ ] Memory MEMORY.md mise à jour : `bug-relance-sent-sans-email.md` marqué **résolu**
- [ ] Communication trésorerie Marveline : "les relances reprennent à partir du <date>"
- [ ] Commit message : `fix(B6.S1): F1058 relance email réel via notification_service (Closes RELANCE-FAKE-SENT-01)`

## Risques

| Risque | P × I | Mitigation |
|---|---|---|
| SMTP server down → toutes les relances en `failed` jusqu'à fix infra | 2×4=8 | Monitoring AlertManager `relances_failed_count > 10` en 1h. Procédure d'escalade ops. |
| Burst d'emails à la première exécution post-fix (relances accumulées) | 4×2=8 | Limite `LIMIT 100` par tenant. Si beaucoup de relances en attente → plusieurs cycles d'1h. Communication clients pour contextualiser. |
| Templates HTML mal rendus dans certains clients mail | 2×2=4 | Test manuel sur Gmail, Outlook, Apple Mail avant déploiement. Templates Jinja2 complets en B6.S1. |
| Backward-compat : statut `'failed'` jamais vu avant → frontend ne sait pas l'afficher | 3×2=6 | Communication frontend dev pour ajouter le statut. Default UI = "En erreur, retry au prochain cycle". |

## Rollback

Si nouveau bug introduit :
1. **Désactiver task** : feature flag `relances_email_enabled=False` (à créer dans `feature_flags`) → la task skip l'envoi mais ne casse rien.
2. **Revert migration `email_send_error`** si nécessaire (downgrade).
3. **Revert task** : git revert + déploiement.

---

# Story S1.T3 — F870 Fix vente épicerie `check_stock=True` par défaut

## Contexte

**Bug ID** : EPI-CHECKSTK-01
**Friction** : F870 (cf. `docs/architecture-audit-2026-04-26/28-epicerie-catalogue-etl.md` §3.1)
**Module Bloc** : 5 (avancée prioritaire dans Sprint 1)
**Sévérité** : P1 — UX caissier dégradée (500 au lieu de 409 propre).
**Confirmé en code** : `app/schemas/epicerie/vente.py:24` + `app/services/epicerie/vente.py:107-116`

### Description

Le schema `EncaissementRequest` déclare `check_stock: bool = False` par défaut. Si l'admin/caissier oublie de passer `check_stock=True`, la vente passe le check service-level, atteint la phase 7 (création mouvement stock), et **PostgreSQL bloque via CHECK `stock_apres >= 0`** → `IntegrityError 500` au lieu d'un `409 STOCK_INSUFFISANT` propre.

UX caissier : message générique "Erreur serveur 500" alors que le vrai problème = stock négatif.

### Code actuel

```python
# app/schemas/epicerie/vente.py:24
check_stock: bool = False  # ❌ défaut dangereux
```

```python
# app/services/epicerie/vente.py:107-116
# Phase 5 — vérification stock (optionnelle, check_stock=False par défaut)
if payload.check_stock:
    for lc in lignes_calculees:
        stock = await stock_repo.get_by_produit(lc["produit"].id, tenant_id)
        dispo = float(stock.quantite) if stock else 0.0
        if dispo < lc["ligne"].quantite:
            raise HTTPException(
                status_code=409,
                detail=f"STOCK_INSUFFISANT:{lc['produit'].designation_clean}",
            )
```

## Solution

### Code corrigé

```python
# app/schemas/epicerie/vente.py:24 (AVANT) → (APRÈS)
check_stock: bool = True  # ✅ défaut sûr
```

```python
# app/services/epicerie/vente.py:107-118 (modifié)
# Phase 5 — vérification stock (par défaut True, F870)
# IMPORTANT : ne pas désactiver check_stock sauf cas exceptionnel admin
# (ex: vente force-validate avec backfill stock manuel ultérieur).
if payload.check_stock:
    for lc in lignes_calculees:
        stock = await stock_repo.get_by_produit(lc["produit"].id, tenant_id)
        dispo = float(stock.quantite) if stock else 0.0
        if dispo < lc["ligne"].quantite:
            raise HTTPException(
                status_code=409,
                detail=f"STOCK_INSUFFISANT:{lc['produit'].designation_clean}",
            )
```

### Diff

```diff
--- a/app/schemas/epicerie/vente.py
+++ b/app/schemas/epicerie/vente.py
@@ -21,7 +21,7 @@ class EncaissementRequest(BaseModel):
     remise_centimes: int = Field(default=0, ge=0)
     remise_motif: Optional[str] = None
     client_nom: Optional[str] = None
-    check_stock: bool = False
+    check_stock: bool = True
```

## Fichiers à modifier

| Fichier | Type | Lignes |
|---|---|---|
| `app/schemas/epicerie/vente.py` | Edit | 1 ligne |
| `app/services/epicerie/vente.py` | Edit (commentaire) | 2 lignes |
| `tests/integration/epicerie/test_encaissement.py` | New ou Edit | +2 tests |

**Aucune migration DB** (changement default schema Pydantic seul).

## Tests à écrire

```python
# tests/integration/epicerie/test_encaissement.py
@pytest.mark.asyncio
async def test_encaisser_default_check_stock_true(async_client, async_db, epicerie_tenant):
    """F870 regression : par défaut check_stock=True, stock insuffisant → 409 propre."""
    produit = EpicerieProduitFactory(tenant_id=epicerie_tenant.id)
    EpicerieStockFactory(tenant_id=epicerie_tenant.id, produit_id=produit.id, quantite=Decimal("2.0"))
    await async_db.commit()
    
    # Pas de check_stock dans le payload → utilise default
    response = await async_client.post(
        "/api/v1/epicerie/ventes/encaisser",
        json={
            "lignes": [{"produit_id": produit.id, "quantite": 5.0, "prix_unitaire_cts": 100}],
            "mode_paiement": "ESPECES",
            "montant_especes": 500,
        },
        headers={"X-Tenant-ID": str(epicerie_tenant.id)},
    )
    
    # Doit être 409 propre, pas 500
    assert response.status_code == 409
    assert "STOCK_INSUFFISANT" in response.json()["detail"]


@pytest.mark.asyncio
async def test_encaisser_explicit_check_stock_false_still_allows_force(...):
    """Si admin passe explicitement check_stock=False, le service ne vérifie pas (cas admin).
    Mais alors PostgreSQL CHECK stock_apres>=0 lève IntegrityError → 500 (logique existante).
    """
    response = await async_client.post(
        "/api/v1/epicerie/ventes/encaisser",
        json={
            ...
            "check_stock": False,  # explicit override admin
        },
        ...
    )
    # 500 attendu (admin a fait un override conscient)
    assert response.status_code == 500
```

## Definition of Done

- [ ] Schema `EncaissementRequest.check_stock` default = `True`
- [ ] Service commentaire mis à jour
- [ ] 2 tests integration ajoutés (default → 409, override admin → 500)
- [ ] `pytest tests/` complet vert
- [ ] Code review approved
- [ ] Déploiement prod (impact frontend si payload omet `check_stock` → comportement change vers safe default)
- [ ] Communication frontend : `check_stock` est maintenant `True` par défaut, retirer si payload l'envoie explicitement à `False`
- [ ] Commit : `fix(B5.S1): F870 epicerie vente check_stock=True par defaut (Closes EPI-CHECKSTK-01)`

## Risques

| Risque | P × I | Mitigation |
|---|---|---|
| Frontend envoie explicitement `check_stock=False` → comportement inchangé pour eux | 2×1=2 | Audit frontend : pas d'usage explicit `false` repéré. Communication frontend dev. |
| Tests existants reposaient sur le default `False` | 2×2=4 | Lancer `pytest tests/` complet, fixer les cas qui échouent (probablement tests qui faisaient des ventes sans set up de stock). |

## Rollback

Trivial : revert PR (1 ligne).

---

# Story S1.T4 — F1055 Décision auto_suspend_uncertified (compliance honnête)

## Contexte

**Bug ID** : SOC2-AUTOSUSP-01
**Friction** : F1055 (cf. `docs/architecture-audit-2026-04-26/33-orchestration-celery.md` §3.1)
**Module Bloc** : 6
**Sévérité** : P1 compliance — SOC2 §10 promet la suspension automatique des users non-recertifiés à J+30. Actuellement la task **ne fait rien** (no-op).
**Confirmé en code** : `app/tasks/access_review.py:131-142`

### Description

La task Celery `run_auto_suspend_uncertified` est planifiée par beat schedule (cf. `celery_app.py:83-87`, cron `1er fév + 1er août à 07:30`) mais ne suspend **personne** :

```python
# app/tasks/access_review.py:131-142
@celery_app.task(name="app.tasks.access_review.run_auto_suspend_uncertified")
def run_auto_suspend_uncertified():
    """Suspension automatique des users non-recertifiés à J+30 — 1er fév + 1er août (§10).

    Note : en l'absence d'une table access_reviews dédiée, cette tâche loggue
    uniquement. L'implémentation complète nécessite la table access_reviews.
    """
    logger.info("[access_review] Running auto-suspend for uncertified users: %s", ...)
    logger.warning(
        "[access_review] auto_suspend_uncertified: table access_reviews not yet implemented — skipping suspensions"
    )
```

**Conséquence** : compliance théâtre. Au prochain audit SOC2, faille critique. Engagement client (Marveline, MassaCorp) potentiellement compromis.

### Décision Q39=A

**Q39=A verrouillée** dans `architecture-cible.md` §6.6 : implémenter réel (pas retirer du beat).

## Solution

### Schema SQL — table `access_reviews`

```sql
CREATE TABLE access_reviews (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    membership_id BIGINT REFERENCES tenant_memberships(id) ON DELETE SET NULL,
    review_type VARCHAR(30) NOT NULL CHECK (review_type IN ('privileged', 'tenant_admin', 'recertification')),
    review_campaign_id VARCHAR(50) NOT NULL,
    initiated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewer_id BIGINT REFERENCES accounts(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    decision VARCHAR(20) CHECK (decision IN ('certified', 'rejected', 'pending')),
    notes TEXT,
    deadline TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_access_reviews_account_campaign ON access_reviews(account_id, review_campaign_id);
CREATE INDEX idx_access_reviews_deadline_decision ON access_reviews(deadline, decision) WHERE decision = 'pending';
CREATE INDEX idx_access_reviews_tenant_type ON access_reviews(tenant_id, review_type);
```

### Migration Alembic

```python
# alembic/versions/2026_04_28_1500_create_access_reviews.py
"""Create access_reviews table for SOC2 §10 compliance (F1055)

Revision ID: b1c2d3e4f5g6
Revises: a1b2c3d4e5f6
Create Date: 2026-04-28 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5g6"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_reviews",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.BigInteger, sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.BigInteger, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("membership_id", sa.BigInteger, sa.ForeignKey("tenant_memberships.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_type", sa.String(30), nullable=False),
        sa.Column("review_campaign_id", sa.String(50), nullable=False),
        sa.Column("initiated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger, sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.CheckConstraint("review_type IN ('privileged', 'tenant_admin', 'recertification')", name="ck_access_reviews_type"),
        sa.CheckConstraint("decision IS NULL OR decision IN ('certified', 'rejected', 'pending')", name="ck_access_reviews_decision"),
    )
    op.create_index("idx_access_reviews_account_campaign", "access_reviews", ["account_id", "review_campaign_id"])
    op.create_index("idx_access_reviews_deadline_decision", "access_reviews", ["deadline", "decision"],
                    postgresql_where=sa.text("decision = 'pending'"))
    op.create_index("idx_access_reviews_tenant_type", "access_reviews", ["tenant_id", "review_type"])


def downgrade() -> None:
    op.drop_index("idx_access_reviews_tenant_type", table_name="access_reviews")
    op.drop_index("idx_access_reviews_deadline_decision", table_name="access_reviews")
    op.drop_index("idx_access_reviews_account_campaign", table_name="access_reviews")
    op.drop_table("access_reviews")
```

### Modèle SQLAlchemy

```python
# app/models/access_review.py (NEW)
"""AccessReview — review de droits d'accès SOC2 §10."""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AccessReview(Base, TimestampMixin):
    __tablename__ = "access_reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("tenant_memberships.id", ondelete="SET NULL"), nullable=True
    )
    review_type: Mapped[str] = mapped_column(String(30), nullable=False)
    review_campaign_id: Mapped[str] = mapped_column(String(50), nullable=False)
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "review_type IN ('privileged', 'tenant_admin', 'recertification')",
            name="ck_access_reviews_type",
        ),
        CheckConstraint(
            "decision IS NULL OR decision IN ('certified', 'rejected', 'pending')",
            name="ck_access_reviews_decision",
        ),
        Index("idx_access_reviews_account_campaign", "account_id", "review_campaign_id"),
    )
```

### Implémentation `run_auto_suspend_uncertified`

```python
# app/tasks/access_review.py (l. 131-180 modifiée)
@celery_app.task(name="app.tasks.access_review.run_auto_suspend_uncertified")
def run_auto_suspend_uncertified():
    """Suspension automatique des users non-recertifiés à J+30 — 1er fév + 1er août (§10).
    
    Pour chaque AccessReview avec decision='pending' AND deadline < now() :
    1. account.is_active = False
    2. revoke toutes les AccountSession actives (cascade revoke)
    3. AuditLog 'USER_SUSPENDED_UNCERTIFIED'
    4. Notification email Compliance Officer
    """
    from app.core.database import SyncSessionLocal
    from app.models.access_review import AccessReview
    from app.models.account import Account
    from app.models.account_session import AccountSession
    from app.services.audit import audit_service_sync
    from sqlalchemy import select, and_, update
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    suspended_count = 0
    error_count = 0
    
    try:
        with SyncSessionLocal() as db:
            # 1. Trouve les reviews 'pending' avec deadline dépassée
            uncertified_reviews = db.execute(
                select(AccessReview).where(
                    and_(
                        AccessReview.decision == "pending",
                        AccessReview.deadline < now,
                    )
                )
            ).scalars().all()
            
            for review in uncertified_reviews:
                try:
                    account = db.get(Account, review.account_id)
                    if account is None or not account.is_active:
                        continue
                    
                    # 2. Suspend account
                    account.is_active = False
                    account.suspended_at = now
                    account.suspended_reason = f"SOC2 §10: not recertified in campaign {review.review_campaign_id}"
                    
                    # 3. Revoke active sessions
                    db.execute(
                        update(AccountSession)
                        .where(
                            AccountSession.account_id == account.id,
                            AccountSession.revoked_at.is_(None),
                        )
                        .values(revoked_at=now, revoke_reason="auto_suspend_uncertified")
                    )
                    
                    # 4. Audit log
                    audit_service_sync.log_action(
                        db=db,
                        action="USER_SUSPENDED_UNCERTIFIED",
                        entity_type="Account",
                        entity_id=account.id,
                        tenant_id=review.tenant_id,
                        actor_type="system",
                        description=f"Auto-suspension SOC2 §10 — campaign {review.review_campaign_id}, deadline {review.deadline.isoformat()}",
                    )
                    
                    suspended_count += 1
                    logger.warning(
                        "[access_review] Suspended account %d (tenant=%d) — uncertified campaign %s",
                        account.id, review.tenant_id, review.review_campaign_id,
                    )
                except Exception:
                    logger.exception("[access_review] Failed to suspend account %d", review.account_id)
                    error_count += 1
            
            db.commit()
            logger.info(
                "[access_review] auto_suspend_uncertified completed: suspended=%d errors=%d",
                suspended_count, error_count,
            )
            return {
                "status": "ok",
                "suspended_count": suspended_count,
                "error_count": error_count,
                "executed_at": now.isoformat(),
            }
    except Exception as exc:
        logger.exception("[access_review] auto_suspend_uncertified failed: %s", exc)
        return {"status": "error", "error": str(exc)}
```

## Fichiers à modifier

| Fichier | Type | Lignes |
|---|---|---|
| `alembic/versions/2026_04_28_1500_create_access_reviews.py` | New | ~50 lignes |
| `app/models/access_review.py` | New | ~50 lignes |
| `app/models/__init__.py` | Edit (export) | +1 ligne |
| `app/tasks/access_review.py` | Edit (l. 131-180) | ~70 lignes refactor |
| `app/services/audit.py` | Possible Edit (méthode `log_action_sync` si pas existante) | +20 lignes |
| `tests/integration/tasks/test_auto_suspend.py` | New | ~150 lignes |

## Tests à écrire

```python
# tests/integration/tasks/test_auto_suspend.py
@pytest.mark.integration
def test_auto_suspend_pending_review_with_passed_deadline_suspends_account(sync_db):
    """F1055 : review pending + deadline passée → account suspended + sessions revoked + audit logged."""
    account = AccountFactory(is_active=True)
    tenant = TenantFactory()
    membership = TenantMembershipFactory(account=account, tenant=tenant, role="admin")
    
    review = AccessReview(
        account_id=account.id,
        tenant_id=tenant.id,
        membership_id=membership.id,
        review_type="recertification",
        review_campaign_id="2026-Q3-recert",
        deadline=datetime.now(timezone.utc) - timedelta(days=1),  # passé hier
        decision="pending",
    )
    sync_db.add(review)
    
    session_active = AccountSessionFactory(account_id=account.id, revoked_at=None)
    sync_db.commit()
    
    # Act
    result = run_auto_suspend_uncertified()
    
    # Assert
    assert result["status"] == "ok"
    assert result["suspended_count"] == 1
    
    sync_db.refresh(account)
    assert account.is_active is False
    assert account.suspended_at is not None
    assert "SOC2" in (account.suspended_reason or "")
    
    sync_db.refresh(session_active)
    assert session_active.revoked_at is not None
    
    audit_log = sync_db.query(AuditLog).filter_by(action="USER_SUSPENDED_UNCERTIFIED", entity_id=account.id).first()
    assert audit_log is not None


@pytest.mark.integration
def test_auto_suspend_certified_review_skipped(sync_db):
    """Review déjà certified → pas de suspension."""
    review = AccessReviewFactory(decision="certified", deadline=datetime.now(timezone.utc) - timedelta(days=10))
    result = run_auto_suspend_uncertified()
    assert result["suspended_count"] == 0
    
    sync_db.refresh(review)
    account = sync_db.get(Account, review.account_id)
    assert account.is_active is True


@pytest.mark.integration
def test_auto_suspend_pending_but_deadline_future_skipped(sync_db):
    """Review pending mais deadline pas encore passée → pas de suspension."""
    review = AccessReviewFactory(decision="pending", deadline=datetime.now(timezone.utc) + timedelta(days=10))
    result = run_auto_suspend_uncertified()
    assert result["suspended_count"] == 0
```

## Definition of Done

- [ ] Migration Alembic `2026_04_28_1500_create_access_reviews` testée upgrade/downgrade
- [ ] Modèle `app/models/access_review.py` créé + exporté
- [ ] Task `run_auto_suspend_uncertified` réimplémentée (drop le no-op + logger.warning)
- [ ] 3 tests integration écrits et passent
- [ ] `pytest tests/` complet vert
- [ ] Validation Compliance Officer (procédure SOC2 §10 documentée)
- [ ] Communication DEVUP : nouveaux endpoints admin nécessaires Bloc 2 pour gérer reviews (initialisation campagnes, certification reviewer)
- [ ] Code review approved par 1 peer + Lead + Compliance
- [ ] Déploiement prod
- [ ] Memory MEMORY.md créé : `bug-soc2-autosuspend.md` marqué résolu
- [ ] Commit : `feat(B6.S1): F1055 implement auto_suspend_uncertified for SOC2 §10 compliance (Closes SOC2-AUTOSUSP-01)`

## Risques

| Risque | P × I | Mitigation |
|---|---|---|
| Suspension prématurée d'un user actif (review oubliée par Compliance Officer) | 2×4=8 | (1) Notifications email aux admins tenant 7j et 1j avant deadline ; (2) Compliance Officer alerté via AlertManager si >5 suspensions en 1 cycle ; (3) Procédure de re-activation rapide via endpoint admin. |
| Endpoint admin pour gérer AccessReviews pas dispo Sprint 1 | 4×3=12 | Sprint 1 livre uniquement la table + task. Endpoints admin (`POST /admin/access-reviews/{id}/certify`, `GET /admin/access-reviews/pending`) = Bloc 2 (B2.S4 ou similaire). En attendant, gestion via SQL direct par Compliance Officer (procédure documentée). |
| Beat schedule `1er fév + 1er août` pourrait suspendre en plein milieu d'un week-end | 1×2=2 | Cron `07:30 UTC` = heure ouvrée FR. AlertManager notifie ops si suspensions >0. |

## Rollback

1. **Désactiver task** : feature flag `auto_suspend_enabled=False` (à créer) → la task skip immédiatement.
2. **Reactivate accounts suspendus erronément** : SQL direct `UPDATE accounts SET is_active=True, suspended_at=NULL WHERE suspended_at > '<sprint_deploy>' AND suspended_reason LIKE 'SOC2%';`
3. **Revert migration** : downgrade Alembic + revert task code.

---

# Coordination Sprint 1

## Timeline (1 semaine)

```
Jour 1 (Lundi)
  AM : Stand-up + assignation owners (Lead)
  AM : T1 + T2 + T3 + T4 démarrés en parallèle (4 devs si dispo)
  PM : T1 fini (0.5j) → review + merge
  PM : T3 fini (0.5j) → review + merge
  
Jour 2 (Mardi)
  AM : T2 fini (1.5j cumulé) → review
  PM : T2 merge + déploiement staging
  PM : T4 en cours
  
Jour 3 (Mercredi)
  AM : T4 fini (1.5j cumulé) → review + Compliance approval
  PM : T4 merge + déploiement staging
  PM : Validation manuelle staging (SMTP test, marmite test, vente test, suspend test)
  
Jour 4 (Jeudi)
  AM : Smoke tests prod (déploiement progressif)
  AM : Monitoring 4h post-deploy
  PM : Communication clients (Marveline, MassaCorp) — emails resync OK
  
Jour 5 (Vendredi)
  AM : Retrospective fire-drill
  PM : Reprise feature work — début Bloc 1.S1 ou suite Bloc 2
```

---

# Story S1.T5 — F255 Fix `provisioning.py` async sans await

## Contexte

**Bug ID** : PROVISION-DEGRADED-AWAIT-01
**Friction** : F255 (cf. `docs/architecture-audit-2026-04-26/09-tenant-multi-app-brand.md` §F255 ligne 227)
**Module Bloc** : 9 (avancée prioritaire dans Sprint 1)
**Sévérité** : P0 PROD — mode dégradé admin inopérant (HTTP 500 latent + 3 endpoints no-op silencieux)
**Détecté** : 2026-04-27 audit cohérence vague 3
**Confirmé en code** : `app/api/v1/endpoints/provisioning.py:140, 159, 179, 180`

### Description

3 endpoints `degraded` appellent les méthodes async `redis_sec.get_degradation_level()` / `set_degraded_flag()` / `clear_degraded_flag()` **sans `await`**. Conséquences :

1. `GET /admin/provision/degraded/status` → ligne 140 retourne `{"degradation_level": <coroutine>}` → JSON serialization error 500.
2. `POST /admin/provision/degraded/enable` → ligne 159 crée la coroutine `set_degraded_flag()` puis la perd → flag jamais activé en Redis-SEC.
3. `POST /admin/provision/degraded/disable` → lignes 179 + 180 idem.

Le système de dégradation 4 niveaux (`NOMINAL`/`READ_ONLY`/`AUTH_DOWN`/`EMERGENCY_BYPASS`) est **inopérant côté API admin** : si Redis-SEC tombe partiellement, les ops ne peuvent pas basculer en mode dégradé via l'API → bypass manuel CLI Redis requis.

## Solution

```diff
 @router.get("/degraded/status", status_code=status.HTTP_200_OK)
 async def get_degradation_status(current_user: UserManagerScope):
     from app.core.redis import redis_sec
-    return {"degradation_level": redis_sec.get_degradation_level()}
+    return {"degradation_level": await redis_sec.get_degradation_level()}

 @router.post("/degraded/enable", ...)
 async def enable_degraded_mode(...):
     ...
-    redis_sec.set_degraded_flag(flag_map[level], ttl_seconds=ttl_seconds)
+    await redis_sec.set_degraded_flag(flag_map[level], ttl_seconds=ttl_seconds)
     ...

 @router.post("/degraded/disable", ...)
 async def disable_degraded_mode(...):
     ...
-    redis_sec.clear_degraded_flag(flag_map[level])
-    new_level = redis_sec.get_degradation_level()
+    await redis_sec.clear_degraded_flag(flag_map[level])
+    new_level = await redis_sec.get_degradation_level()
     ...
```

## Fichiers à modifier

- `app/api/v1/endpoints/provisioning.py` (4 lignes : 140, 159, 179, 180)
- `tests/integration/api/test_provisioning_degraded.py` (à créer — 3 tests E2E enable/disable/status)

## Tests

```python
# tests/integration/api/test_provisioning_degraded.py
@pytest.mark.asyncio
async def test_enable_degraded_actually_sets_flag(authenticated_client, redis_client):
    response = await authenticated_client.post(
        "/api/v1/admin/provision/degraded/enable",
        json={"level": "READ_ONLY", "ttl_seconds": 300}
    )
    assert response.status_code == 200
    # Vérification effective côté Redis-SEC
    assert await redis_client.exists("degraded:read_only") == 1


@pytest.mark.asyncio
async def test_status_returns_string_not_coroutine(authenticated_client):
    response = await authenticated_client.get("/api/v1/admin/provision/degraded/status")
    assert response.status_code == 200
    assert isinstance(response.json()["degradation_level"], str)
    assert response.json()["degradation_level"] in ("NOMINAL", "READ_ONLY", "AUTH_DOWN", "EMERGENCY_BYPASS")
```

## Definition of Done

- [ ] 4 `await` ajoutés
- [ ] 3 tests intégration verts
- [ ] Test manuel staging : `curl POST /admin/provision/degraded/enable READ_ONLY` → flag effectif en Redis
- [ ] Invariant CI à venir (B1.S1) : `check_no_unawaited_async.py` détectera ce pattern à l'avenir

## Risque

- **Probabilité** : 1 (3 lignes triviales, aucune logique métier touchée)
- **Impact** : 5 (mode dégradé = outil incident-response)
- **Score** : 5 — LOW
- **Rollback** : git revert (1 commit)

---

# Story S1.T6 — F1002 Fix audit login échec

## Contexte

**Bug ID** : AUDIT-LOGIN-EXCL-01
**Friction** : F1002 (cf. `docs/architecture-audit-2026-04-26/31-audit-log.md` §F1002 ligne 104)
**Module Bloc** : 6 (avancée prioritaire dans Sprint 1)
**Sévérité** : P0 PROD — non-conformité RGPD Article 30 (traçabilité des accès)
**Confirmé en code** : `app/middleware/audit.py:34, 63-72` (`EXCLUDED_PATHS` contient `/auth/login`)

### Description

Le middleware `AuditMiddleware` exclut systématiquement `/auth/login` de son périmètre via `EXCLUDED_PATHS`. La promesse "log_login_failed" repose sur l'endpoint qui appelle explicitement `audit_service.log_login(success=False)`. Si un dev oublie cet appel ou si une exception interrompt l'endpoint avant cet appel, **les tentatives de connexion échouées ne sont pas tracées**. Conséquence opérationnelle : aucun signal pour détecter du brute-force credential stuffing en prod.

## Solution

Approche en deux temps (Sprint 1 = patch tactique, B6.S2 = refonte complète audit) :

### Sprint 1 — Patch tactique
Audit explicite dans le gestionnaire d'exception de `auth/login.py`, **avant** propagation 401 :

```python
# app/api/v1/endpoints/auth.py — endpoint POST /login
@router.post("/login")
async def login(payload: LoginIn, request: Request, ...):
    try:
        account = await auth_service.authenticate(payload.email, payload.password)
        ...
        await audit_service.log("auth.login.success", account_id=account.id, ip=request.client.host)
        return TokenOut(...)
    except (InvalidCredentials, AccountLocked, AccountSuspended) as e:
        # F1002 fix : audit explicite échec — masquer le password (jamais dans le payload)
        await audit_service.log(
            action="auth.login.failed",
            actor_email=payload.email,   # email seul, pas password
            ip=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            metadata={"reason": e.__class__.__name__},  # InvalidCredentials | AccountLocked | etc
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
```

### B6.S2 — Refonte
Retirer `/auth/login` de `EXCLUDED_PATHS`, faire passer la trace par le middleware avec masquage automatique des champs sensibles (`password`, `pin`, `totp_code`).

## Fichiers à modifier

- `app/api/v1/endpoints/auth.py` (try/except wrapping de l'authentification)
- `app/services/audit/service.py` (vérifier que `log()` accepte `actor_email` quand `account_id` est inconnu)
- `tests/integration/api/test_auth_login_audit.py` (à créer)

## Tests

```python
@pytest.mark.asyncio
async def test_login_failed_wrong_password__creates_audit_log(client, db, account):
    response = await client.post("/api/v1/auth/login", json={
        "email": account.email,
        "password": "wrong-password"
    })
    assert response.status_code == 401

    # Vérifier audit log créé avec action='auth.login.failed'
    from sqlalchemy import select
    from app.models import AuditLog
    result = await db.execute(
        select(AuditLog)
        .filter_by(action="auth.login.failed")
        .order_by(AuditLog.timestamp.desc())
    )
    log = result.scalar_one()
    assert log.metadata["reason"] == "InvalidCredentials"
    # Critique : le password ne doit JAMAIS apparaître dans le log
    assert "wrong-password" not in str(log.metadata)


@pytest.mark.asyncio
async def test_login_failed_unknown_email__creates_audit_log_without_account_id(client, db):
    response = await client.post("/api/v1/auth/login", json={
        "email": "ghost@nobody.fr",
        "password": "anything"
    })
    assert response.status_code == 401

    from sqlalchemy import select
    from app.models import AuditLog
    result = await db.execute(
        select(AuditLog).filter_by(action="auth.login.failed")
    )
    log = result.scalar_one()
    assert log.actor_account_id is None
    assert log.metadata["actor_email"] == "ghost@nobody.fr"
```

## Definition of Done

- [ ] Try/except dans `auth.py` avec audit explicite sur 3 exceptions (InvalidCredentials, AccountLocked, AccountSuspended)
- [ ] Password masqué (jamais dans payload audit)
- [ ] 2 tests intégration verts
- [ ] Validation prod : tester avec compte canary, vérifier `SELECT * FROM audit_logs WHERE action='auth.login.failed' ORDER BY timestamp DESC LIMIT 5`
- [ ] Ticket B6.S2 référence cette story comme dette à finaliser (drop EXCLUDED_PATHS)

## Risque

- **Probabilité** : 2 (try/except simple, exceptions déjà toutes définies)
- **Impact** : 4 (compliance + détection brute-force)
- **Score** : 8 — MEDIUM
- **Rollback** : git revert + redéploiement (audit failures non auditées = retour état actuel)

---

---

# Story S1.T7 — F47 JWT audience bypass cross-app

## Contexte

**Bug ID** : JWT-AUD-BYPASS-01
**Friction** : F47 (cf. `docs/architecture-audit-2026-04-26/02-core-security.md`)
**Sévérité** : P0 SEC — élévation de privilège cross-app
**Confirmé en code** : `app/core/security.py:246-262`

### Description

Le décodeur JWT contient une logique défensive incomplète :
```python
actual_type = payload.get("type")
if actual_type == TokenType.ACCESS:
    # validation aud
elif actual_type == TokenType.REFRESH:
    # validation aud
return payload   # ← ligne 262 : tombe ici si type ∉ {ACCESS, REFRESH}
```

Si `actual_type` est absent, `None`, ou contient une valeur inconnue (ex: token forgé avec `type="internal"` ou claim absent), **le payload est retourné sans validation d'audience**. Conséquence : un token destiné à `marveline` peut être accepté sur `epicerie`/`restaurant`/`splendid` → cross-app escalation.

## Solution

```diff
 actual_type = payload.get("type")
 actual_aud = payload.get("aud")
 valid_access_auds = set(settings.JWT_AUDIENCES.values()) | {settings.JWT_AUDIENCE}
 valid_refresh_auds = {f"{a}:refresh" for a in valid_access_auds}
+# F47 fix : refuser tout token sans claim `type` valide (fail-closed)
+if actual_type not in (TokenType.ACCESS.value, TokenType.REFRESH.value):
+    raise TokenInvalid(f"Invalid token type: {actual_type!r}")
 if actual_type == TokenType.ACCESS:
     if expected_audience is not None:
         if actual_aud != expected_audience:
             raise TokenInvalid("Access token audience mismatch")
     elif actual_aud not in valid_access_auds:
         raise TokenInvalid("Access token audience mismatch")
 elif actual_type == TokenType.REFRESH:
     if expected_audience is not None:
         if actual_aud != f"{expected_audience}:refresh":
             raise TokenInvalid("Refresh token audience mismatch")
     elif actual_aud not in valid_refresh_auds:
         raise TokenInvalid("Refresh token audience mismatch")
 return payload
```

## Fichiers à modifier

- `app/core/security.py` (1 ligne ajoutée + commentaire)
- `tests/integration/test_jwt_audience_validation.py` (à créer — tests anti-régression)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_jwt__no_type_claim__rejected_on_all_audiences():
    """F47 fix : token sans claim 'type' doit être rejeté (cross-app escalation)."""
    payload_no_type = {"sub": "1", "aud": "marveline", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload_no_type, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenInvalid, match="Invalid token type"):
        decode_token(token, expected_audience="marveline")


@pytest.mark.asyncio
async def test_jwt__type_internal__rejected():
    """Token forgé avec type inconnu (ex: 'internal', 'service') doit être rejeté."""
    payload = {"sub": "1", "type": "internal", "aud": "marveline", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenInvalid):
        decode_token(token, expected_audience="marveline")


@pytest.mark.asyncio
async def test_jwt__valid_access_token__still_works():
    """Régression : tokens ACCESS valides continuent de passer."""
    token = create_access_token(sub="1", tenant_id="1", scopes=[], audience="marveline")
    payload = decode_token(token, expected_audience="marveline")
    assert payload["type"] == TokenType.ACCESS.value
```

## Definition of Done

- [ ] 1 ligne ajoutée dans `security.py:248`
- [ ] 3 tests intégration verts (no type, type inconnu, type ACCESS valide)
- [ ] CI invariant `check_token_creator_passes_db.py` ne lève pas de régression
- [ ] Validation manuelle staging : forger un token sans `type` via script → 401 attendu
- [ ] MEMORY.md : F47 marqué résolu

## Risque

- **Probabilité** : 1 (1 ligne défensive triviale)
- **Impact** : 5 (cross-app escalation = compromission inter-tenant)
- **Score** : 5 — LOW
- **Rollback** : git revert (1 commit)

---

# Story S1.T8 — F370 Stepup WebAuthn cassé (Redis key vide)

## Contexte

**Bug ID** : STEPUP-WEBAUTHN-01
**Friction** : F370 (cf. `docs/architecture-audit-2026-04-26/12-mfa-webauthn-pin.md`)
**Sévérité** : P0 SEC — fonctionnalité MFA forte 100% cassée
**Confirmé en code** : `app/api/v1/endpoints/webauthn.py:85-86`

### Description

```python
# webauthn.py:85
device_id = getattr(current_user, '_device_id', '') or ''
# current_user.User n'a JAMAIS d'attribut _device_id → device_id = ''
stepup_key = f"stepup:{current_user.id}:{device_id}"
# Clé écrite : "stepup:42:" (device_id vide)
# Clé recherchée par le guard require_step_up : "stepup:42:{device_id_extracted_from_request}"
```

Les deux clés ne matchent jamais → tout endpoint protégé par `require_step_up()` refuse même après vérification WebAuthn réussie. Le user est en boucle infinie de stepup.

## Solution

Injecter le `device_fingerprint` depuis le header `X-Device-ID` (déjà extrait par `RequestContextMiddleware`) :

```diff
+from app.services.session import generate_device_id
+
 @router.post("/stepup/verify")
 async def verify_stepup(
     request: Request,
     payload: WebAuthnVerifyIn,
     current_user: User = Depends(get_current_user),
     redis: Redis = Depends(get_redis),
 ):
     # ... vérification WebAuthn ...

-    device_id = getattr(current_user, '_device_id', '') or ''
+    # F370 fix : extraire device_id depuis le request context
+    user_agent = request.headers.get("user-agent", "")
+    ip_address = request.client.host if request.client else ""
+    device_id = generate_device_id(user_agent, ip_address)
+
     stepup_key = f"stepup:{current_user.id}:{device_id}"
     await redis.setex(stepup_key, MFAConfig.STEPUP_TTL, "verified")
```

Le guard `require_step_up()` doit utiliser **exactement la même** logique de `device_id` (factoriser dans `app/services/session.py:generate_device_id`).

## Fichiers à modifier

- `app/api/v1/endpoints/webauthn.py` (5 lignes)
- `app/core/deps.py` ou `app/services/session.py` (factorisation `require_step_up` lookup avec même `generate_device_id`)
- `tests/integration/test_webauthn_stepup.py` (à créer)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_webauthn__stepup_verify_then_guard__same_device_id__success(
    authenticated_client, redis_client
):
    """F370 fix : la clé Redis écrite par /stepup/verify doit matcher celle lue par require_step_up."""
    # Étape 1 : verify WebAuthn (mocké)
    headers = {"X-Device-ID": "abc123-fingerprint", "User-Agent": "Mozilla/5.0"}
    response = await authenticated_client.post(
        "/api/v1/auth/webauthn/stepup/verify",
        json={"credential_id": "...", "client_data_json": "..."},
        headers=headers,
    )
    assert response.status_code == 200

    # Étape 2 : appel endpoint sensible avec require_step_up
    response = await authenticated_client.post(
        "/api/v1/admin/sensitive-action",
        headers=headers,
    )
    assert response.status_code == 200, "Stepup verifié mais guard refuse → F370 régression"
```

## Definition of Done

- [ ] `device_id` calculé identique en write (verify) et read (guard)
- [ ] Test E2E : verify → action sensible → 200
- [ ] Test E2E : verify avec device A, action avec device B → 403 (correct, isolation device)
- [ ] Validation staging : compte test enrôle WebAuthn → action sensible → succès

## Risque

- **Probabilité** : 2
- **Impact** : 4 (MFA forte inopérante)
- **Score** : 8 — MEDIUM
- **Rollback** : git revert

---

# Story S1.T9 — F296 OAuth-only login TypeError

## Contexte

**Bug ID** : OAUTH-ONLY-TYPEERROR-01
**Friction** : F296 (cf. `docs/architecture-audit-2026-04-26/10-account-session-membership.md`)
**Sévérité** : P0 SEC — HTTP 500 + user enumeration
**Confirmé en code** : `app/services/account.py:70`

### Description

```python
# account.py:55-72
async def verify_credentials(self, db, email, password):
    account = await self.repo.get_by_email(db, email)
    if not account:
        return None
    if not verify_password(password, account.hashed_password):  # ← ligne 70
        return None
    return account
```

Si l'account a été créé via OAuth uniquement (Google, Microsoft), `account.hashed_password` est `None`. `verify_password(password, None)` lève `TypeError: argument should be str, not None` → réponse HTTP 500.

**Exploitation** : un attaquant peut distinguer les comptes OAuth-only des comptes password en observant le code de retour (500 vs 401) → user enumeration.

## Solution

Pattern timing-safe (hash dummy systématique) :

```diff
+# Hash Argon2 d'une chaîne dummy — utilisé pour timing-safe sur comptes sans password
+_DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22 + "$" + "B" * 43
+
 async def verify_credentials(self, db, email, password):
     account = await self.repo.get_by_email(db, email)
-    if not account:
-        return None
-    if not verify_password(password, account.hashed_password):
+    # F296 fix : timing-safe — toujours appeler verify_password même si pas de hash
+    hash_to_verify = account.hashed_password if account and account.hashed_password else _DUMMY_HASH
+    is_valid = verify_password(password, hash_to_verify)
+
+    if not account:
+        return None
+    if not account.hashed_password:
+        # Compte OAuth-only — pas de login email/password possible
+        return None
+    if not is_valid:
         return None
     return account
```

## Fichiers à modifier

- `app/services/account.py` (5 lignes + constante `_DUMMY_HASH`)
- `app/services/auth_v2.py` (vérifier appelants — propagation cohérente)
- `tests/integration/test_login_oauth_only.py` (à créer)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_login__oauth_only_account__returns_401_not_500(client, db):
    """F296 fix : compte OAuth-only avec login password → 401 propre, pas TypeError 500."""
    from app.models import Account
    account = Account(email="oauth@test.fr", hashed_password=None, is_active=True)
    db.add(account)
    await db.flush()

    response = await client.post("/api/v1/auth/login", json={
        "email": "oauth@test.fr",
        "password": "anything"
    })
    # Critique : 401 (pas 500) — pas de fuite d'info OAuth-only
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login__timing_consistent_oauth_vs_unknown(client, db):
    """User enumeration prevention : durée 401 ~identique pour OAuth-only et email inconnu."""
    import time
    # OAuth-only account
    account = Account(email="oauth@test.fr", hashed_password=None, is_active=True)
    db.add(account)
    await db.flush()

    t1 = time.perf_counter()
    await client.post("/api/v1/auth/login", json={"email": "oauth@test.fr", "password": "x"})
    duration_oauth = time.perf_counter() - t1

    t2 = time.perf_counter()
    await client.post("/api/v1/auth/login", json={"email": "ghost@test.fr", "password": "x"})
    duration_unknown = time.perf_counter() - t2

    # Tolérance : 50% (Argon2 ~100ms, donc écart max ~50ms)
    assert abs(duration_oauth - duration_unknown) / max(duration_oauth, duration_unknown) < 0.5
```

## Definition of Done

- [ ] `_DUMMY_HASH` constante définie + utilisée timing-safe
- [ ] 2 tests anti-régression verts
- [ ] Test perf : 401 OAuth-only vs 401 email-inconnu ~même durée (anti user-enum)
- [ ] Validation staging : compte test OAuth-only → POST /auth/login → 401, pas 500

## Risque

- **Probabilité** : 2
- **Impact** : 4 (user enum + 500 visibles externes)
- **Score** : 8 — MEDIUM

---

# Story S1.T10 — F404 OAuth callback MFA bypass

## Contexte

**Bug ID** : OAUTH-MFA-BYPASS-01
**Friction** : F404 (cf. `docs/architecture-audit-2026-04-26/13-apikey-oauth-passwordreset.md`)
**Sévérité** : P0 SEC — MFA contournée via Google/Microsoft login
**Confirmé en code** : `app/api/v1/endpoints/oauth.py:296`

### Description

```python
# oauth.py:269-310 (_issue_oauth_tokens)
async def _issue_oauth_tokens(db, user, ip_address, user_agent, response):
    ...
    session = await session_service.create_session(
        db, user_id=user.id, ip_address=ip_address, user_agent=user_agent,
        mfa_verified=False,   # ← ligne 296 : hardcodé False, jamais updated
    )
    return TokenOut(...)
```

Un user qui a configuré TOTP / WebAuthn et se connecte via Google **bypass complètement le challenge MFA** : la session est créée avec `mfa_verified=False`, mais l'access token est émis directement → tous les endpoints non gardés par `require_step_up()` accessibles sans MFA.

**Vecteur principal** : compromission de compte Google → contrôle total compte CaroCorp/Marveline avec MFA enrôlée mais inopérante.

## Solution

Avant l'émission des tokens, vérifier si le compte a un MFA enrôlé. Si oui → émettre `mfa_pending_token` + retourner `MFARequiredResult`.

```diff
+from app.services.mfa import mfa_service
+
 async def _issue_oauth_tokens(db, user, ip_address, user_agent, response):
+    # F404 fix : vérifier MFA enrolement avant émission tokens
+    has_mfa = await mfa_service.is_enrolled(db, account_id=user.id)
+    if has_mfa:
+        # Émettre mfa_pending_token (TTL 5min) au lieu des tokens d'accès
+        pending_token = await mfa_service.create_pending_token(db, user.id)
+        return MFARequiredResponse(
+            mfa_required=True,
+            pending_token=pending_token,
+            challenge_url="/api/v1/auth/mfa/verify"
+        )
+
+    # Pas de MFA → émission directe (compte sans MFA enrôlée)
     session = await session_service.create_session(
         db, user_id=user.id, ip_address=ip_address, user_agent=user_agent,
-        mfa_verified=False,
+        mfa_verified=False,  # MFA non requise (pas enrôlée)
     )
     return TokenOut(...)
```

Côté `OAuthV2Service._open_session_and_issue` (autre flow OAuth) : appliquer le même fix.

## Fichiers à modifier

- `app/api/v1/endpoints/oauth.py` (10 lignes — fonction `_issue_oauth_tokens`)
- `app/services/oauth_v2.py` (10 lignes — méthode `_open_session_and_issue`)
- `app/services/mfa.py` (vérifier que `is_enrolled` + `create_pending_token` existent ; sinon implémenter)
- `app/schemas/auth.py` (`MFARequiredResponse` schema si absent)
- `tests/integration/test_oauth_mfa_gate.py` (à créer)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_oauth_callback__user_with_totp_enrolled__returns_mfa_required(
    client, db, mocked_oauth_provider
):
    """F404 fix : user avec MFA enrôlée + login Google → mfa_required=True, pas tokens."""
    # Setup : account + auth_factor TOTP actif
    account = Account(email="user@test.fr", is_active=True)
    db.add(account)
    await db.flush()
    factor = AuthFactor(membership_id=membership.id, type="TOTP", is_active=True, ...)
    db.add(factor)
    await db.flush()

    # Simule callback OAuth (mock provider)
    response = await client.get("/api/v1/auth/oauth/google/callback?code=valid_code&state=...")

    assert response.status_code == 200
    body = response.json()
    assert body["mfa_required"] is True
    assert "pending_token" in body
    assert "access_token" not in body  # Critique : pas de token avant MFA


@pytest.mark.asyncio
async def test_oauth_callback__user_without_mfa__returns_tokens_directly(
    client, db, mocked_oauth_provider
):
    """Régression : user sans MFA enrôlée → tokens émis directement (comportement nominal)."""
    account = Account(email="nomfa@test.fr", is_active=True)
    db.add(account)
    await db.flush()

    response = await client.get("/api/v1/auth/oauth/google/callback?code=valid&state=...")
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body.get("mfa_required") is not True
```

## Definition of Done

- [ ] Les 2 flows OAuth (`oauth.py` legacy + `oauth_v2.py` v2) appellent `mfa_service.is_enrolled()`
- [ ] 4 tests intégration : MFA enrolée + Google → mfa_required ; sans MFA + Google → tokens ; idem MS ; régression password login intact
- [ ] CI invariant à venir (B6.S2) : `check_no_mfa_bypass_oauth.py`
- [ ] Validation staging : compte canary avec TOTP → login Google → challenge MFA présenté

## Risque

- **Probabilité** : 2 (3 méthodes à modifier — risque de manquer un flow)
- **Impact** : 5 (compromission compte admin via Google compromis)
- **Score** : 10 — HIGH
- **Rollback** : git revert (re-bypass MFA OAuth)

---

# Story S1.T11 — F368 WebAuthn RP_ID multi-tenant (BLOCKER Splendid 28/04)

## Contexte

**Bug ID** : WEBAUTHN-RPID-MULTITENANT-01
**Friction** : F368/F369 (cf. `docs/architecture-audit-2026-04-26/12-mfa-webauthn-pin.md`)
**Sévérité** : P0 SEC + **BLOCKER COMMERCIAL** — bloque démo Splendid 28/04
**Confirmé en code** : `app/services/webauthn.py:22, 66, 126, 163, 218, 219`

### Description

```python
# webauthn.py:22
RP_ID = settings.JWT_ISSUER.replace("www.", "")  # = "marveline.com" hardcodé
RP_NAME = settings.APP_NAME  # = "Marveline" global

# Toutes les opérations WebAuthn utilisent RP_ID global :
# - register_options (l.66) : "rp": {"id": RP_ID, "name": RP_NAME}
# - register_verify (l.126) : expected_rp_id=RP_ID, expected_origin=settings.FRONTEND_URL
# - authenticate_options (l.163) : "rpId": RP_ID
# - authenticate_verify (l.218-219) : expected_rp_id=RP_ID, expected_origin=settings.FRONTEND_URL
```

WebAuthn FIDO2 lie cryptographiquement la credential au domaine (RP_ID). Une credential enrôlée avec `RP_ID="marveline.com"` ne peut pas être utilisée sur `splendid.events` ni sur `epicerie.carocorp.fr` — la vérification échoue avec `InvalidRpIdError`.

**Conséquence directe** :
- Splendid Events (prospect avec RDV 28/04) **ne peut pas faire de démo MFA WebAuthn** sur son frontend `splendid.events`
- L'app Épicerie sur `epicerie.carocorp.fr` ne peut pas utiliser WebAuthn même pour les comptes Marveline (seul Marveline.com fonctionne)

## Solution

Ajouter colonnes `rp_id` + `frontend_url` per-tenant et les lire via le request context :

### DDL (sera repris dans `50-sql-schema.md` §3 mais ajouté ici en hotfix Sprint 1)

```sql
-- Hotfix Sprint 1 : WebAuthn multi-tenant
ALTER TABLE tenants ADD COLUMN rp_id VARCHAR(253);
ALTER TABLE tenants ADD COLUMN frontend_url VARCHAR(512);

COMMENT ON COLUMN tenants.rp_id IS
    'WebAuthn Relying Party ID (domaine sans protocole, ex: marveline.com, splendid.events). NULL = fallback settings.JWT_ISSUER.';
COMMENT ON COLUMN tenants.frontend_url IS
    'URL frontend per-tenant pour emails transactionnels et expected_origin WebAuthn. NULL = fallback settings.FRONTEND_URL.';

-- Backfill tenants existants
UPDATE tenants SET rp_id = 'marveline.com', frontend_url = 'https://marveline.com' WHERE app_code = 'marveline';
UPDATE tenants SET rp_id = 'epicerie.carocorp.fr', frontend_url = 'https://epicerie.carocorp.fr' WHERE app_code = 'epicerie';
UPDATE tenants SET rp_id = 'restaurant.carocorp.fr', frontend_url = 'https://restaurant.carocorp.fr' WHERE app_code = 'restaurant';
-- Splendid Events : à créer + UPDATE rp_id='splendid.events', frontend_url='https://splendid.events' lors du provisioning
```

### Code

```python
# app/services/webauthn.py
class WebAuthnService:
    def __init__(self, db: AsyncSession, tenant: Tenant):
        self.db = db
        self.tenant = tenant
        # F368 fix : RP_ID + origin per-tenant
        self.rp_id = tenant.rp_id or settings.JWT_ISSUER.replace("www.", "")
        self.rp_name = tenant.brand_display_name or settings.APP_NAME
        self.expected_origin = tenant.frontend_url or settings.FRONTEND_URL

    async def register_options(self, account: Account, ...):
        return {
            "rp": {"id": self.rp_id, "name": self.rp_name},
            ...
        }

    async def register_verify(self, ..., credential):
        return verify_registration_response(
            credential=credential,
            expected_rp_id=self.rp_id,
            expected_origin=self.expected_origin,
            ...
        )
    # idem authenticate_options, authenticate_verify
```

```python
# app/api/v1/endpoints/webauthn.py
@router.post("/register/options")
async def register_options(
    request: Request,
    current_user: Account = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    tenant = request.state.tenant  # injecté par RequestContextMiddleware
    service = WebAuthnService(db, tenant)
    return await service.register_options(current_user, ...)
```

## Fichiers à modifier

- `alembic/versions/{rev}_tenants_rp_id_frontend_url.py` (migration data + DDL)
- `app/models/tenant.py` (ajout `rp_id: Mapped[Optional[str]]`, `frontend_url: Mapped[Optional[str]]`)
- `app/services/webauthn.py` (refacto class avec tenant context)
- `app/api/v1/endpoints/webauthn.py` (4 endpoints — passer tenant en arg)
- `tests/integration/test_webauthn_multitenant.py` (à créer)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_webauthn__register_options__uses_tenant_rp_id(authenticated_client, db, tenant):
    """F368 fix : register options renvoie le rp_id du tenant, pas le global Marveline."""
    tenant.rp_id = "splendid.events"
    tenant.frontend_url = "https://splendid.events"
    await db.flush()

    response = await authenticated_client.post("/api/v1/auth/webauthn/register/options")
    assert response.status_code == 200
    body = response.json()
    assert body["rp"]["id"] == "splendid.events"
    assert body["rp"]["id"] != "marveline.com"  # Critique


@pytest.mark.asyncio
async def test_webauthn__register__credential_bound_to_tenant_rp_id(
    authenticated_client, db, tenant, mocked_webauthn_attestation
):
    """Credential enrôlée avec rp_id Splendid → utilisable uniquement sur Splendid."""
    tenant.rp_id = "splendid.events"
    await db.flush()
    # Enrôlement
    await authenticated_client.post("/api/v1/auth/webauthn/register/verify", json={...})

    # Vérification ultérieure avec mauvais rp_id → échoue
    tenant_marveline = await create_other_tenant(db, app_code="marveline", rp_id="marveline.com")
    # Auth du même account sur tenant Marveline → InvalidRpIdError attendu
```

## Definition of Done

- [ ] DDL `tenants.rp_id` + `frontend_url` migré + backfill tenants existants
- [ ] `WebAuthnService` instancié avec `tenant` context
- [ ] 4 tests E2E : register Splendid, authenticate Splendid, register Marveline, cross-tenant rejet
- [ ] **Démo Splendid 28/04** : compte test sur `splendid.events` enrôle YubiKey → authentifie avec succès
- [ ] Documentation onboarding tenant : checklist `rp_id` + `frontend_url` à configurer au provisioning

## Risque

- **Probabilité** : 3 (refacto multiple endpoints + migration data)
- **Impact** : 5 (deal Splendid + sécurité MFA)
- **Score** : 15 — CRITICAL
- **Rollback** : revert migration + revert code → retour mono-brand Marveline

---

# Story S1.T12 — F1126 Prometheus path normalization DoS

## Contexte

**Bug ID** : METRICS-PATH-DOS-01
**Friction** : F1126 (cf. `docs/architecture-audit-2026-04-26/35-health-metrics.md`)
**Sévérité** : P0 PROD — DoS Prometheus / OOM kill
**Confirmé en code** : `app/middleware/metrics.py:55-77` + `app/constants/limits.py` `PATH_NORMALIZATION_PATTERNS`

### Description

```python
# metrics.py:55-77
def _normalize_path(self, path: str) -> str:
    for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
        if re.match(pattern, path):
            return replacement
    return path  # ← fallback : retourne le path original si aucun match
```

Un attaquant qui spam `/api/v1/foo/{random_uuid_1}`, `/api/v1/foo/{random_uuid_2}`, etc., génère une nouvelle série temporelle Prometheus à chaque appel → cardinality explosion → OOM Prometheus en quelques minutes → perte du monitoring au moment précis d'un incident.

## Solution

```diff
 def _normalize_path(self, path: str) -> str:
     for pattern, replacement in PATH_NORMALIZATION_PATTERNS:
         if re.match(pattern, path):
             return replacement
-    return path
+    # F1126 fix : fallback vers "other" si aucun pattern match (anti-cardinality DoS)
+    return "other"
```

Et étendre `PATH_NORMALIZATION_PATTERNS` pour couvrir tous les endpoints documentés dans `52-api-contracts.openapi.yml` (audit one-shot).

## Fichiers à modifier

- `app/middleware/metrics.py` (1 ligne)
- `app/constants/limits.py` (`PATH_NORMALIZATION_PATTERNS` étendu — audit OpenAPI)
- `tests/integration/test_metrics_cardinality.py` (à créer)

## Tests anti-régression

```python
@pytest.mark.asyncio
async def test_metrics__random_paths__generates_single_other_label(client, redis_client):
    """F1126 fix : 100 requêtes sur paths inconnus → 1 seule série label='other'."""
    import uuid
    for _ in range(100):
        await client.get(f"/api/v1/random/{uuid.uuid4()}")  # path inexistant

    metrics_response = await client.get("/metrics")
    metrics_text = metrics_response.text
    # Compter les séries http_requests_total avec path différent
    other_count = metrics_text.count('path="other"')
    assert other_count >= 1, "Pattern fallback 'other' attendu"
    # Aucune série ne doit contenir un UUID (cardinality leak)
    assert "/api/v1/random/" not in metrics_text


@pytest.mark.asyncio
async def test_metrics__known_paths__still_normalized(client):
    """Régression : les paths connus continuent d'être normalisés (ex: /products/{id} → /products/{id})."""
    await client.get("/api/v1/products/42")
    metrics_response = await client.get("/metrics")
    assert 'path="/api/v1/products/{id}"' in metrics_response.text
```

## Definition of Done

- [ ] 1 ligne fix dans `_normalize_path`
- [ ] `PATH_NORMALIZATION_PATTERNS` audité contre OpenAPI (`52-api-contracts.openapi.yml`) — couverture 100% des endpoints documentés
- [ ] 2 tests intégration verts
- [ ] Validation staging : 1000 requêtes paths random → cardinality `/metrics` stable

## Risque

- **Probabilité** : 1 (1 ligne triviale + audit patterns)
- **Impact** : 4 (DoS monitoring = blind spot incident)
- **Score** : 4 — LOW
- **Rollback** : git revert

---

## Critères de succès Sprint 1

### Fonctionnel
- [ ] **Aucune AttributeError** sur `POST /instances` avec recette en prod (Loki query confirme F906)
- [ ] **>0 emails de relance reçus** par clients tests sur boîte mail (validation manuelle + bounce monitoring F1058)
- [ ] **Aucun 500** sur `/api/v1/epicerie/ventes/encaisser` avec stock insuffisant (409 propre F870)
- [ ] **Table `access_reviews` existe** + task `run_auto_suspend_uncertified` retourne `status='ok'` sans warning skip (F1055)

### Infra
- [ ] **`GET /admin/provision/degraded/status` retourne string** (pas coroutine sérialisée) + flags effectifs Redis vérifiés (F255)
- [ ] **Audit logs `auth.login.failed`** présents pour tentatives échouées en staging (F1002)
- [ ] **`/metrics` cardinalité stable** sous 1000 requêtes paths random — label `path="other"` (F1126)

### Sécurité
- [ ] **JWT sans claim `type` rejeté** (test E2E + manuel staging) (F47)
- [ ] **Stepup WebAuthn fonctionnel** : verify → action sensible → 200 (F370)
- [ ] **OAuth-only login retourne 401** (pas 500) + timing-safe vs email inconnu (F296)
- [ ] **OAuth callback détecte MFA** : compte avec TOTP + login Google → mfa_required=true (F404)
- [ ] **Démo Splendid Events 28/04** : enrôlement WebAuthn sur splendid.events fonctionnel (F368)

### Global
- [ ] **CI 100% verte** sur `main` (1782 tests existants + ~30 nouveaux tests anti-régression Sprint 1)
- [ ] **0 régression** signalée par les clients
- [ ] **MEMORY.md à jour** : F906/F1058/F870/F1055/F255/F1002/F47/F370/F296/F404/F368/F1126 marqués résolus
- [ ] **Risk register `05-risk-register.md`** : ajout R24 (Splendid blocker WebAuthn pré-Sprint 1, mitigé), R25 (placebo B2.S3 RBAC), R26 (PII partial B4.S5)

## Communication post-Sprint 1

### Email DEVUP à clients existants (Marveline + MassaCorp)

> Maintenance technique livrée le `<date>`. **12 corrections livrées** :
>
> **Améliorations fonctionnelles**
> - Cuisine : marmites avec recettes → fonctionnel (F906)
> - Trésorerie : relances de paiement → reprise des envois automatiques (F1058)
> - Caisse épicerie : message d'erreur propre si stock insuffisant (F870)
> - Sécurité : recertification automatique des accès, compliance SOC2 (F1055)
>
> **Renforcements sécurité authentification**
> - Validation cross-app des tokens d'accès renforcée (F47)
> - Authentification forte WebAuthn (clé physique) à nouveau opérationnelle (F370)
> - Connexion OAuth (Google/Microsoft) : intégration MFA (F404)
> - Stabilité : élimination de plusieurs causes d'erreur 500 latentes (F255, F296, F1002, F1126)
>
> Aucune action requise de votre côté. Pour les utilisateurs WebAuthn (clés physiques), une réauthentification peut être demandée à la prochaine connexion.

### Email prospect Splendid Events

> Bonjour [contact Splendid],
>
> Suite à notre échange préparatoire pour la démo du 28/04, nous avons livré une mise à jour qui rend la plateforme **multi-marque native** : votre instance Splendid Events utilisera dorénavant `splendid.events` comme domaine d'authentification (au lieu d'un domaine partagé). Conséquence : authentification forte (clés FIDO2 / WebAuthn) entièrement opérationnelle sur votre marque.
>
> Cordialement,
> [DEVUP]

### Slack `#devup-stakeholders`

Lead poste un récap technique :
- Nombre de comptes ré-affectés (révocations sessions post-correctifs MFA)
- Nombre d'emails relance envoyés depuis le déploiement (F1058)
- Cardinalité Prometheus avant/après (F1126)
- Validation démo Splendid 28/04 (F368)

### Commit final

Tag `v<X.Y.Z>` sur main avec changelog ventilé en 3 sections (Fonctionnel / Infra / Sécurité). Référencer chaque story `S1.T1` à `S1.T12`.
