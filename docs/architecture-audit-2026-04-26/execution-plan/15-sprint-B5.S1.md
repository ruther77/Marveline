# Sprint B5.S1 — Hotfixes multi-app (marmite F906 + check_stock F870 + cancel cascade resto + Invoice resto)

> **STATUT** : ⏳ À démarrer après Bloc 2
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev3
> **BLOQUE** : B5.S2 (tenant_id ETL stabilisé), B5.S3 (FSM cascade s'appuie sur cancel cascade)
> **DÉPEND DE** : Sprint 1 (T1 F906/F870 patches déjà appliqués hotfix tactique → cette story livre la version structurelle)
> **OBJECTIF** : Corriger les bugs P0 production multi-app résiduels post-Sprint 1 : F906 (marmite `quantite_par_batch` + formule), F870 (`check_stock=True` default), F908+F909 (cancel ligne/commande resto avec réintégration stock + REINTEGRATION_ANNULATION movement), F910 (`FinanceInvoice CLIENT_RESTAURANT` à `payer`), F911 (validation total fractions == total).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S1.T1** | F906 — Marmite `quantite_par_batch` + formule consommation correcte | P0 | 1 j | aucun |
| **B5.S1.T2** | F870 — Encaisser épicerie `check_stock=True` default + 409 propre | P0 | 0.5 j | aucun |
| **B5.S1.T3** | F908 — `LigneCommande.cancel` réintègre stock (portions marmite + protéine + side) | P0 | 1 j | T4 |
| **B5.S1.T4** | F909 — `CommandeService.annuler` cascade lignes + REINTEGRATION_ANNULATION movement | P0 | 1 j | aucun |
| **B5.S1.T5** | F910 — `CommandeRestaurant.payer` crée `FinanceInvoice CLIENT_RESTAURANT` + Outbox | P0 | 1.5 j | aucun |
| **B5.S1.T6** | F911 — Validation `total_fractions == sum(fraction_lines)` au paiement | P1 | 0.5 j | aucun |

**Total effort** : 5.5 jours-homme.

---

# Story B5.S1.T1 — Marmite `quantite_par_batch` + formule (F906)

## Contexte

**Friction** : F906, MARMITE-QPP-01 (cf. `architecture-cible.md TR-57`)
**Sévérité** : P0 — production bloquée : `_verifier_et_consommer_recette` accède `ligne.quantite_par_portion` inexistant → AttributeError 500 sur lancement marmite avec recette
**Code source** : `app/services/restaurant/instance_preparation.py:118`

### Description

Sprint 1 a appliqué un patch tactique. Cette story livre la version structurelle :
1. Champ correct dans `RecetteTypePreparation.quantite_par_batch` (qty d'ingrédient pour 1 batch entier, pas par portion)
2. Formule consommation : `qty_consumed = quantite_par_batch * (portions_demandees / portions_par_batch)`
3. Hardcoded `quantite_par_portion` historique → migration drop ou rename

## Solution

### Migration

```python
# alembic/versions/i1a2b3c4d5fe_recette_quantite_par_batch.py
def upgrade() -> None:
    # Si la colonne s'appelle quantite_par_portion (legacy) → rename
    with contextlib.suppress(Exception):
        op.alter_column(
            "recettes_type_preparation",
            "quantite_par_portion",
            new_column_name="quantite_par_batch",
        )
    # Si la colonne n'existe pas → add
    op.add_column(
        "recettes_type_preparation",
        sa.Column("quantite_par_batch", sa.Numeric(10, 3), nullable=True),
    )
    # Si TypePreparation a portions_par_batch column manquante → add
    op.add_column(
        "type_preparations",
        sa.Column("portions_par_batch", sa.Integer, nullable=False, server_default="10"),
    )
```

### Service

```python
# app/services/restaurant/instance_preparation.py
class InstancePreparationService:
    async def _verifier_et_consommer_recette(
        self,
        type_preparation_id: int,
        portions_demandees: int,
        tenant_id: int,
    ):
        type_prep = await self.db.get(TypePreparation, type_preparation_id, options=[selectinload(TypePreparation.recette_lignes)])
        if not type_prep.recette_lignes:
            return  # Plat sans recette (composé directement)

        # Formule : qty_consumed_per_ingredient = quantite_par_batch * (portions_demandees / portions_par_batch)
        ratio = Decimal(portions_demandees) / Decimal(type_prep.portions_par_batch)

        for ligne in type_prep.recette_lignes:
            qty_consumed = (ligne.quantite_par_batch * ratio).quantize(Decimal("0.001"))
            await self._consommer_ingredient(
                ingredient_id=ligne.ingredient_id,
                qty_consumed=qty_consumed,
                tenant_id=tenant_id,
            )
```

### Tests

```python
async def test_marmite_lance_avec_recette_consomme_correct(db, tenant, type_prep_carry_poulet):
    # Recette : poulet 5kg pour 10 portions ; lancement 20 portions → consomme 10kg
    type_prep_carry_poulet.portions_par_batch = 10
    recette_ligne_poulet = type_prep_carry_poulet.recette_lignes[0]
    recette_ligne_poulet.quantite_par_batch = Decimal("5.0")
    
    instance = await service.lancer_marmite(type_prep_carry_poulet.id, portions=20, tenant_id=tenant.id)
    
    movement = await db.scalar(
        select(MouvementStockRestaurant).where(
            MouvementStockRestaurant.ingredient_id == recette_ligne_poulet.ingredient_id,
            MouvementStockRestaurant.type == "consommation_marmite",
        )
    )
    assert movement.quantite == Decimal("10.0")  # 5 × (20/10) = 10
```

## DoD

- [ ] Migration colonnes `quantite_par_batch` + `portions_par_batch`
- [ ] Service utilise formule `qty * portions_demandees / portions_par_batch`
- [ ] Test : lancement marmite avec recette → consommation correcte
- [ ] Aucune régression `AttributeError` sur lancement

---

# Story B5.S1.T2 — Encaisser `check_stock=True` default (F870)

## Contexte

**Friction** : F870, EPI-CHECKSTK-01
**Sévérité** : P0 — vente passe → IntegrityError 500 (CHECK `stock_apres>=0`) au lieu de 409 propre
**Code source** : `app/services/epicerie/vente.py:encaisser`

### Description

Cible :
1. Default `check_stock=True` (sécurité par défaut)
2. Si stock insuffisant → 409 Conflict avec détail `{product_id, available, requested}` au lieu de 500
3. Endpoint admin `?force=true` pour bypass (scope `epicerie:override_stock`)

## Solution

```python
# app/services/epicerie/vente.py
class EpicerieVenteService:
    async def encaisser(
        self,
        vente_id: UUID,
        check_stock: bool = True,  # default True (vs False historique)
        tenant_id: int,
    ):
        async with self.db.begin():
            vente = await self.db.get(EpicerieVente, vente_id, with_for_update=True)
            
            if check_stock:
                # Pre-validation
                missing = []
                for line in vente.lignes:
                    stock = await self.db.scalar(
                        select(EpicerieStockManagement.qty_available)
                        .where(EpicerieStockManagement.produit_id == line.produit_id)
                    )
                    if (stock or 0) < line.qty:
                        missing.append({
                            "produit_id": line.produit_id,
                            "available": stock or 0,
                            "requested": line.qty,
                        })
                if missing:
                    raise InsufficientStock(missing=missing)  # → 409 via exception_handler
            
            # ... encaissement logic
```

```python
# app/middleware/exception_handler.py
@app.exception_handler(InsufficientStock)
async def insufficient_stock_handler(request, exc):
    return JSONResponse(status_code=409, content={
        "error": "INSUFFICIENT_STOCK",
        "missing": exc.missing,
    })
```

### Test

```python
async def test_encaisser_default_checks_stock(client, tenant, vente_with_unstocked_line):
    response = await client.post(f"/api/v1/epicerie/ventes/{vente.id}/encaisser")
    assert response.status_code == 409
    assert response.json()["error"] == "INSUFFICIENT_STOCK"

async def test_encaisser_with_override_scope(client_with_override, vente):
    response = await client_with_override.post(f"/api/v1/epicerie/ventes/{vente.id}/encaisser?force=true")
    assert response.status_code == 200
```

## DoD

- [ ] `check_stock=True` default
- [ ] `InsufficientStock` exception → 409 propre
- [ ] Override admin via scope `epicerie:override_stock` + query `?force=true`
- [ ] Test : 409 par défaut ; 200 avec override

---

# Story B5.S1.T3 — `LigneCommande.cancel` réintègre stock (F908)

## Contexte

**Friction** : F908 (cf. `architecture-cible.md TR-42`)
**Sévérité** : P0 — `LigneCommande.delete` ne restitue ni portions marmite ni protéine ni side ; stock définitivement perdu
**Code source** : `app/services/restaurant/ligne_commande.py:cancel`

### Description

Cible : annulation ligne ENVOYEE/EN_PREPARATION/PRETE → réintégration :
1. Portions marmite : `instance.portions_restantes += line.portions`
2. Mouvement REINTEGRATION_ANNULATION sur stock_restaurant + epicerie selon side
3. Audit Outbox event `LigneCommandeCancelled`

## Solution

```python
# app/services/restaurant/ligne_commande.py
class LigneCommandeService:
    async def cancel(
        self,
        ligne_id: UUID,
        actor_id: UUID,
        tenant_id: int,
        reason: str,
    ):
        async with self.db.begin():
            ligne = await self.db.get(LigneCommande, ligne_id, with_for_update=True)
            await fsm.assert_transition(self.db, "ligne_commande", ligne.id, ligne.status, "ANNULEE", actor_id=actor_id)

            # 1. Réintégration portions marmite (instance preparation)
            if ligne.instance_preparation_id:
                instance = await self.db.get(InstancePreparation, ligne.instance_preparation_id, with_for_update=True)
                instance.portions_restantes += ligne.portions

            # 2. Réintégration sides (epicerie + restaurant) si la ligne avait des sides
            for side in ligne.sides:
                if side.source == "epicerie":
                    await self._reintegrer_epicerie(side.produit_id, side.qty, tenant_id, ligne_id=ligne.id)
                elif side.source == "restaurant":
                    await self._reintegrer_restaurant(side.ingredient_id, side.qty, tenant_id, ligne_id=ligne.id)

            ligne.status = "ANNULEE"
            ligne.cancelled_at = datetime.now(UTC)
            ligne.cancelled_reason = reason

            # 3. Outbox audit
            self.db.add(OutboxEvent(
                event_type="LigneCommandeCancelled",
                aggregate_id=ligne.id,
                tenant_id=tenant_id,
                payload={"ligne_id": str(ligne.id), "portions_returned": ligne.portions, "reason": reason},
            ))

    async def _reintegrer_epicerie(self, produit_id, qty, tenant_id, ligne_id):
        await self.db.execute(
            update(EpicerieStockManagement)
            .where(EpicerieStockManagement.produit_id == produit_id)
            .values(qty_available=EpicerieStockManagement.qty_available + qty)
        )
        self.db.add(EpicerieStockMovement(
            produit_id=produit_id, qty=qty, type="REINTEGRATION_ANNULATION",
            source_type="ligne_commande", source_id=ligne_id, tenant_id=tenant_id,
        ))

    async def _reintegrer_restaurant(self, ingredient_id, qty, tenant_id, ligne_id):
        await self.db.execute(
            update(StockRestaurant)
            .where(StockRestaurant.ingredient_id == ingredient_id)
            .values(qty_available=StockRestaurant.qty_available + qty)
        )
        self.db.add(MouvementStockRestaurant(
            ingredient_id=ingredient_id, qty=qty, type="REINTEGRATION_ANNULATION",
            source_type="ligne_commande", source_id=ligne_id, tenant_id=tenant_id,
        ))
```

### Test

```python
async def test_cancel_ligne_returns_portions_to_marmite(db, tenant, ligne_envoyee):
    instance_id = ligne_envoyee.instance_preparation_id
    portions_avant = (await db.get(InstancePreparation, instance_id)).portions_restantes
    
    await service.cancel(ligne_envoyee.id, actor_id=user.id, tenant_id=tenant.id, reason="customer_request")
    
    portions_apres = (await db.get(InstancePreparation, instance_id)).portions_restantes
    assert portions_apres == portions_avant + ligne_envoyee.portions

async def test_cancel_ligne_creates_reintegration_movement(db, ligne_with_side):
    await service.cancel(ligne_with_side.id, actor_id=user.id, tenant_id=tenant.id, reason="ko")
    movement = await db.scalar(
        select(EpicerieStockMovement).where(
            EpicerieStockMovement.source_id == ligne_with_side.id,
            EpicerieStockMovement.type == "REINTEGRATION_ANNULATION",
        )
    )
    assert movement is not None
```

## DoD

- [ ] `LigneCommandeService.cancel` réintègre portions marmite + sides
- [ ] Movements `REINTEGRATION_ANNULATION` créés (resto + épicerie)
- [ ] Outbox event `LigneCommandeCancelled`
- [ ] Test : portions retournées au marmite ; movements créés

---

# Story B5.S1.T4 — `CommandeService.annuler` cascade lignes (F909)

## Contexte

**Friction** : F909 (TR-42 cont.)
**Sévérité** : P0 — annulation commande resto ne restitue rien

### Description

Cible : `CommandeService.annuler(commande_id)` boucle sur lignes et appelle `LigneCommandeService.cancel` pour chacune.

## Solution

```python
# app/services/restaurant/commande.py
class CommandeService:
    async def annuler(self, commande_id: UUID, actor_id: UUID, tenant_id: int, reason: str):
        async with self.db.begin():
            commande = await self.db.get(CommandeRestaurant, commande_id, options=[selectinload(CommandeRestaurant.lignes)], with_for_update=True)
            await fsm.assert_transition(self.db, "commande_restaurant", commande.id, commande.status, "ANNULEE", actor_id=actor_id)

            # Cascade cancel chaque ligne
            for ligne in commande.lignes:
                if ligne.status in ("ENVOYEE", "EN_PREPARATION", "PRETE"):
                    await ligne_service.cancel(ligne.id, actor_id, tenant_id, reason=f"cascade:{reason}")

            commande.status = "ANNULEE"
            self.db.add(OutboxEvent(
                event_type="CommandeRestaurantCancelled",
                aggregate_id=commande.id,
                tenant_id=tenant_id,
                payload={"commande_id": str(commande.id), "reason": reason, "lignes_count": len(commande.lignes)},
            ))
```

## DoD

- [ ] `CommandeService.annuler` cascade
- [ ] Test : commande avec 3 lignes ENVOYEE → 3 cancels + 3 movements REINTEGRATION
- [ ] Outbox event `CommandeRestaurantCancelled`

---

# Story B5.S1.T5 — `CommandeRestaurant.payer` crée Invoice (F910)

## Contexte

**Friction** : F910 (TR-43)
**Sévérité** : P0 — CA restaurant uniquement dans `restaurant_commandes` ; pas de livre comptable ; audit fiscal impossible

### Description

Cible : `payer()` crée `FinanceInvoice` avec `customer_type='CLIENT_RESTAURANT'` (anonymisé si pas customer_id) + Outbox event.

## Solution

```python
# app/services/restaurant/commande.py
class CommandeService:
    async def payer(
        self,
        commande_id: UUID,
        payment_method: VentePaymentMethod,
        actor_id: UUID,
        tenant_id: int,
    ) -> FinanceInvoice:
        async with self.db.begin():
            commande = await self.db.get(CommandeRestaurant, commande_id, options=[selectinload(CommandeRestaurant.lignes)], with_for_update=True)
            await fsm.assert_transition(self.db, "commande_restaurant", commande.id, commande.status, "PAYEE", actor_id=actor_id)

            # 1. Créer Invoice
            invoice = FinanceInvoice(
                tenant_id=tenant_id,
                customer_type="CLIENT_RESTAURANT",
                customer_id=commande.customer_id,  # NULL si client passant
                reference=await self._next_invoice_ref(tenant_id),
                emitted_at=datetime.now(UTC),
                status="emitted",
                total_ht_cents=commande.total_ht_cents,
                total_tva_cents=commande.total_tva_cents,
                total_ttc_cents=commande.total_ttc_cents,
                source_type="commande_restaurant",
                source_id=commande.id,
                lines=[
                    FinanceInvoiceLine(
                        description=f"{l.plat_name} × {l.portions}",
                        qty=l.portions,
                        unit_price_ht_cents=l.unit_price_ht_cents,
                        tva_rate_snapshot=l.tva_rate_snapshot,  # B3.S3.T1
                        line_total_ttc_cents=l.line_total_ttc_cents,
                    )
                    for l in commande.lignes if l.status != "ANNULEE"
                ],
                payment_method=payment_method,
            )
            self.db.add(invoice)

            commande.status = "PAYEE"
            commande.paid_at = datetime.now(UTC)

            self.db.add(OutboxEvent(
                event_type="CommandeRestaurantPaid",
                aggregate_id=commande.id,
                tenant_id=tenant_id,
                payload={"commande_id": str(commande.id), "invoice_id": str(invoice.id), "total_ttc": invoice.total_ttc_cents},
            ))
            return invoice
```

### Test

```python
async def test_commande_payer_creates_invoice(db, tenant, commande_envoyee):
    invoice = await service.payer(commande_envoyee.id, payment_method="card", actor_id=user.id, tenant_id=tenant.id)
    assert invoice.status == "emitted"
    assert invoice.customer_type == "CLIENT_RESTAURANT"
    assert invoice.total_ttc_cents == commande_envoyee.total_ttc_cents
    
    # Outbox event
    event = await db.scalar(select(OutboxEvent).where(OutboxEvent.event_type == "CommandeRestaurantPaid"))
    assert event is not None
```

## DoD

- [ ] `payer()` crée FinanceInvoice CLIENT_RESTAURANT
- [ ] Lignes Invoice avec `tva_rate_snapshot` (cohérent B3.S3)
- [ ] Outbox event publié
- [ ] Test : payer → Invoice + Outbox + commande.status=PAYEE
- [ ] Asymétrie résolue : épicerie vente → Invoice ✓ ; restaurant commande → Invoice ✓

---

# Story B5.S1.T6 — Validation `total_fractions == sum(fraction_lines)` (F911)

## Contexte

**Friction** : F911
**Sévérité** : P1 — paiement fractionné peut diverger du total commande

### Description

Cible : avant `payer`, valider que `sum(fraction_payments) == commande.total_ttc_cents`.

## Solution

```python
# app/services/restaurant/commande.py
async def payer_fractionne(self, commande_id, fractions: list[FractionPayment]):
    sum_fractions = sum(f.amount_cents for f in fractions)
    commande = await self.db.get(CommandeRestaurant, commande_id)
    if sum_fractions != commande.total_ttc_cents:
        raise FractionTotalMismatch(
            expected=commande.total_ttc_cents,
            received=sum_fractions,
        )
    # ... reste de payer logic
```

```python
# app/middleware/exception_handler.py
@app.exception_handler(FractionTotalMismatch)
async def fraction_mismatch_handler(request, exc):
    return JSONResponse(status_code=422, content={
        "error": "FRACTION_TOTAL_MISMATCH",
        "expected_cents": exc.expected, "received_cents": exc.received,
    })
```

## DoD

- [ ] Validation `sum == total` au paiement fractionné
- [ ] Exception `FractionTotalMismatch` → 422 propre
- [ ] Test : 2 fractions 30€+25€ pour total 60€ → 422

---

## Critères de succès Sprint B5.S1

- [ ] **F906 résolu structurellement** : `quantite_par_batch` + formule cohérente
- [ ] **F870 résolu** : `check_stock=True` default + 409 propre
- [ ] **F908 résolu** : cancel ligne réintègre stock (marmite + sides)
- [ ] **F909 résolu** : cancel commande cascade
- [ ] **F910 résolu** : Invoice CLIENT_RESTAURANT créée à `payer`
- [ ] **F911 résolu** : validation total fractions
- [ ] Test E2E : commande resto → payer → Invoice + audit ; cancel → réintégration

---

**Fin du document — 15-sprint-B5.S1.md**
