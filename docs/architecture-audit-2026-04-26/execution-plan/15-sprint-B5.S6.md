# Sprint B5.S6 — TransferRequest workflow + smart stock_alerte + Decimal end-to-end

> **STATUT** : ⏳ À démarrer après B5.S5
> **DURÉE MAX** : 1 semaine
> **OWNER** : Dev3
> **BLOQUE** : aucun (sprint final Bloc 5)
> **DÉPEND DE** : B5.S3 (TransferRequestFSM), B5.S5 (categorie_id FK)
> **OBJECTIF** : Compléter le workflow `TransferRequest` cassé en milieu (TR-54, F923) — `APPROVED → FULFILLED` côté code livré. Q32=A approval automatique par stock check + advisory lock anti double-approval. F912 conversion auto InternalTransfer. F871 `valider_transfert with_for_update` (TR-41 race condition). Decimal end-to-end (drop float `quantite × prix_cts`). TVA dérivée Category (cohérent B4.S3).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S6.T1** | TR-54 / F923 — `TransferRequest.fulfill` workflow complet (APPROVED → FULFILLED) | P0 | 1.5 j | aucun |
| **B5.S6.T2** | Q32=A — Approval automatique par stock check + advisory lock anti double-approval | P0 | 1 j | T1 |
| **B5.S6.T3** | F912 — Conversion auto InternalTransfer sur `TransferRequest.fulfill` | P0 | 1 j | T1 |
| **B5.S6.T4** | TR-41 / F871 — `valider_transfert` `with_for_update` (race condition stock épicerie) | P0 | 0.5 j | aucun |
| **B5.S6.T5** | TR-56 / F891 — Decimal end-to-end (drop `float × prix_cts`) + audit ETL | P1 | 1 j | aucun |
| **B5.S6.T6** | Validation finale Bloc 5 cohérence (audit checklist) | P1 | 0.5 j | aucun |

**Total effort** : 5.5 jours-homme.

---

# Story B5.S6.T1 — `TransferRequest.fulfill` workflow complet (TR-54 / F923)

## Contexte

**Friction** : TR-54, F923 (cf. `architecture-cible.md §5.1`)
**Sévérité** : P0 — `fulfilled_transfer_id` jamais setté, épicerie ne peut pas confirmer fulfillement
**Code source** : `app/services/transfer/request.py`

### Description

Aujourd'hui : `TransferRequest` arrive en `APPROVED` puis ne progresse plus. La transition `APPROVED → FULFILLED` est absente côté code (mais présente FSM matrix B5.S3.T1).

Cible : `TransferRequestService.fulfill(request_id)` orchestre :
1. Lock `TransferRequest with_for_update` + assert FSM `APPROVED → FULFILLED`
2. Crée `InternalTransfer` (T3) avec qty + source/dest tenants
3. Décrémente stock source (épicerie) — `with_for_update` (T4)
4. Set `TransferRequest.fulfilled_transfer_id = internal_transfer.id`
5. Outbox event `TransferRequestFulfilled`

## Solution

```python
# app/services/transfer/request.py
class TransferRequestService:
    async def fulfill(
        self,
        request_id: UUID,
        actor_id: UUID,
        tenant_id: int,
    ) -> InternalTransfer:
        async with self.db.begin():
            request = await self.db.get(TransferRequest, request_id, with_for_update=True)
            if request.target_tenant_id != tenant_id:
                # Le tenant qui fulfill = source (épicerie), le request.target_tenant_id = destinataire (resto)
                # Vérifier autorité
                source_match = request.source_tenant_id == tenant_id
                if not source_match:
                    raise Forbidden(f"Tenant {tenant_id} not authorized to fulfill request {request_id}")

            await fsm.assert_transition(self.db, "transfer_request", request.id, request.status, "FULFILLED", actor_id=actor_id)

            # 2. Décrément stock source avec lock
            await self.db.execute(
                update(EpicerieStockManagement)
                .where(
                    EpicerieStockManagement.produit_id == request.produit_id,
                    EpicerieStockManagement.tenant_id == request.source_tenant_id,
                )
                .values(qty_available=EpicerieStockManagement.qty_available - request.qty)
            )
            self.db.add(EpicerieStockMovement(
                produit_id=request.produit_id,
                tenant_id=request.source_tenant_id,
                qty=-request.qty,
                type="TRANSFER_OUT",
                source_type="transfer_request",
                source_id=request.id,
            ))

            # 3. Créer InternalTransfer (T3)
            internal_transfer = InternalTransfer(
                source_tenant_id=request.source_tenant_id,
                dest_tenant_id=request.target_tenant_id,
                produit_id=request.produit_id,
                qty=request.qty,
                status="IN_TRANSIT",
                source_request_id=request.id,
            )
            self.db.add(internal_transfer)
            await self.db.flush()

            # 4. Set fulfilled_transfer_id
            request.fulfilled_transfer_id = internal_transfer.id
            request.status = "FULFILLED"
            request.fulfilled_at = datetime.now(UTC)

            # 5. Outbox
            self.db.add(OutboxEvent(
                event_type="TransferRequestFulfilled",
                aggregate_id=request.id,
                tenant_id=tenant_id,
                payload={
                    "request_id": str(request.id),
                    "internal_transfer_id": str(internal_transfer.id),
                    "qty": request.qty,
                },
            ))
            return internal_transfer
```

### Endpoint

```python
@router.post("/transfer-requests/{request_id}/fulfill")
async def fulfill_transfer_request(
    request_id: UUID,
    user: User = Depends(require_scope(Scope.TRANSFERS_FULFILL)),
):
    transfer = await service.fulfill(request_id, actor_id=user.id, tenant_id=user.tenant_id)
    return TransferResponse(internal_transfer_id=transfer.id, status="IN_TRANSIT")
```

### Test

```python
async def test_fulfill_creates_internal_transfer(db, tenant_epi, tenant_resto, transfer_request_approved):
    transfer = await service.fulfill(transfer_request_approved.id, actor_id=user.id, tenant_id=tenant_epi.id)
    assert transfer.status == "IN_TRANSIT"
    
    await db.refresh(transfer_request_approved)
    assert transfer_request_approved.status == "FULFILLED"
    assert transfer_request_approved.fulfilled_transfer_id == transfer.id

async def test_fulfill_decrements_source_stock(db, transfer_request_approved):
    qty_avant = (await db.scalar(...)).qty_available
    await service.fulfill(transfer_request_approved.id, ...)
    qty_apres = (await db.scalar(...)).qty_available
    assert qty_apres == qty_avant - transfer_request_approved.qty
```

## DoD

- [ ] `fulfill()` orchestre 5 étapes en 1 TX
- [ ] `fulfilled_transfer_id` setté
- [ ] FSM transit APPROVED → FULFILLED
- [ ] Outbox event `TransferRequestFulfilled`
- [ ] Test E2E request → approve → fulfill → InternalTransfer IN_TRANSIT

---

# Story B5.S6.T2 — Approval automatique stock check + advisory lock (Q32=A)

## Contexte

**Décision** : Q32=A (verrouillée 2026-04-27) — approval automatique par stock check
**Sévérité** : P0 — sans lock, 2 requests simultanées sur même produit qui ensemble dépassent stock disponible → double-approval

### Description

Cible :
1. `TransferRequestService.approve(request_id)` automatique
2. `pg_advisory_xact_lock(produit_id)` au moment du check (anti race)
3. Si stock épicerie disponible >= qty → APPROVED, sinon REJECTED

## Solution

```python
class TransferRequestService:
    async def auto_approve(
        self,
        request_id: UUID,
        actor_id: UUID,
        tenant_id: int,
    ) -> str:
        """Q32=A — approval auto par stock check avec lock anti-race."""
        async with self.db.begin():
            request = await self.db.get(TransferRequest, request_id, with_for_update=True)
            
            # Advisory lock per produit (anti double-approval simultané)
            await self.db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('transfer_produit:' || :pid))"),
                {"pid": str(request.produit_id)},
            )
            
            stock = await self.db.scalar(
                select(EpicerieStockManagement.qty_available)
                .where(
                    EpicerieStockManagement.produit_id == request.produit_id,
                    EpicerieStockManagement.tenant_id == request.source_tenant_id,
                )
            )
            
            if (stock or 0) >= request.qty:
                request.status = "APPROVED"
                action = "APPROVED"
                # Réserver virtuellement le stock (déclaration intent)
                # Décrément effectif au fulfill (T1)
            else:
                request.status = "REJECTED"
                request.rejected_reason = f"Stock insuffisant: {stock or 0} < {request.qty}"
                action = "REJECTED"
            
            await fsm.assert_transition(self.db, "transfer_request", request.id, "PENDING", action, actor_id=actor_id)
            
            self.db.add(OutboxEvent(
                event_type=f"TransferRequest{action.title()}",
                aggregate_id=request.id,
                tenant_id=tenant_id,
                payload={"request_id": str(request.id), "stock_available": stock or 0},
            ))
            return action
```

### Test concurrence

```python
async def test_two_concurrent_requests_no_double_approve(db, tenant, produit):
    """Stock=10 ; 2 requests qty=8 simultanés → 1 APPROVED, 1 REJECTED."""
    await db.execute(
        update(EpicerieStockManagement)
        .where(EpicerieStockManagement.produit_id == produit.id)
        .values(qty_available=10)
    )
    
    req1 = TransferRequest(produit_id=produit.id, qty=8, source_tenant_id=tenant.id, ...)
    req2 = TransferRequest(produit_id=produit.id, qty=8, source_tenant_id=tenant.id, ...)
    db.add_all([req1, req2]); await db.commit()
    
    # Lance 2 approve en parallèle
    results = await asyncio.gather(
        service.auto_approve(req1.id, actor_id=user.id, tenant_id=tenant.id),
        service.auto_approve(req2.id, actor_id=user.id, tenant_id=tenant.id),
    )
    
    # 1 APPROVED, 1 REJECTED
    assert sorted(results) == ["APPROVED", "REJECTED"]
```

## DoD

- [ ] Auto-approve avec advisory lock per produit
- [ ] APPROVED si stock suffisant ; REJECTED sinon
- [ ] Test concurrence : 2 requests simultanés → 1 succès / 1 rejet (pas 2 succès)

---

# Story B5.S6.T3 — Conversion auto InternalTransfer (F912)

## Contexte

**Friction** : F912 — `TransferRequest.fulfill` doit créer un `InternalTransfer` (déjà couvert T1).

### Description

Cette story complète T1 : ajout du suivi `InternalTransfer.received` côté destinataire (resto) + bouclage cascade.

## Solution

```python
# app/services/transfer/internal.py
class InternalTransferService:
    async def receive(
        self,
        transfer_id: UUID,
        actor_id: UUID,
        tenant_id: int,
    ):
        """Resto reçoit le transfert → +stock_restaurant, FSM IN_TRANSIT → RECEIVED."""
        async with self.db.begin():
            transfer = await self.db.get(InternalTransfer, transfer_id, with_for_update=True)
            if transfer.dest_tenant_id != tenant_id:
                raise Forbidden(...)
            
            await fsm.assert_transition(self.db, "internal_transfer", transfer.id, transfer.status, "RECEIVED", actor_id=actor_id)
            
            # +stock_restaurant (mapping ingredient via IngredientEpicerieMapping)
            ingredient = await self.db.scalar(
                select(IngredientEpicerieMapping.ingredient_id)
                .where(
                    IngredientEpicerieMapping.produit_id == transfer.produit_id,
                    IngredientEpicerieMapping.tenant_id == tenant_id,
                )
            )
            await self.db.execute(
                update(StockRestaurant)
                .where(StockRestaurant.ingredient_id == ingredient)
                .values(qty_available=StockRestaurant.qty_available + transfer.qty)
            )
            self.db.add(MouvementStockRestaurant(
                ingredient_id=ingredient,
                qty=transfer.qty,
                type="TRANSFER_IN",
                source_type="internal_transfer",
                source_id=transfer.id,
                tenant_id=tenant_id,
            ))
            
            transfer.status = "RECEIVED"
            transfer.received_at = datetime.now(UTC)
            
            self.db.add(OutboxEvent(
                event_type="InternalTransferReceived",
                aggregate_id=transfer.id,
                tenant_id=tenant_id,
                payload={"transfer_id": str(transfer.id), "qty": transfer.qty},
            ))
```

## DoD

- [ ] `InternalTransferService.receive` opérationnel
- [ ] Mapping `IngredientEpicerieMapping` consulté (cohérent B5.S2.T2 cross-tenant FK validation)
- [ ] Movement TRANSFER_IN créé
- [ ] Test : transfer RECEIVED → ingredient stock_restaurant += qty

---

# Story B5.S6.T4 — `valider_transfert with_for_update` (TR-41 / F871)

## Contexte

**Friction** : TR-41, F871
**Sévérité** : P0 — race condition stock épicerie : 2 workers décrémentent concurrent → 1 perdu
**Code source** : `app/services/epicerie/stock.py:valider_transfert`

### Description

Cible : ajouter `with_for_update` à la sélection stock_management avant décrément.

## Solution

```python
# app/services/epicerie/stock.py
async def valider_transfert(self, produit_id, qty, tenant_id):
    async with self.db.begin():
        sm = await self.db.execute(
            select(EpicerieStockManagement)
            .where(
                EpicerieStockManagement.produit_id == produit_id,
                EpicerieStockManagement.tenant_id == tenant_id,
            )
            .with_for_update()  # FIX TR-41
        )
        sm = sm.scalar_one()
        if sm.qty_available < qty:
            raise InsufficientStock(...)
        sm.qty_available -= qty
```

### Test concurrence

```python
async def test_valider_transfert_no_race(db, produit_with_stock_10):
    """2 transferts qty=6 simultanés → 1 succès / 1 InsufficientStock (pas 2 succès laissant -2)."""
    results = await asyncio.gather(
        service.valider_transfert(produit_with_stock_10.id, qty=6, tenant_id=1),
        service.valider_transfert(produit_with_stock_10.id, qty=6, tenant_id=1),
        return_exceptions=True,
    )
    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, InsufficientStock)]
    assert len(successes) == 1
    assert len(failures) == 1
```

## DoD

- [ ] `with_for_update` ajouté
- [ ] Test concurrence : 1 succès / 1 fail
- [ ] Pattern cohérent avec `release_n` B4.S2.T2

---

# Story B5.S6.T5 — Decimal end-to-end (TR-56)

## Contexte

**Friction** : TR-56, F891, F927, F958
**Sévérité** : P1 — `quantite × prix_cts` en float → perte précision sur grandes commandes

### Description

Cible : audit + fix tous calculs centimes en `Decimal` (pas `float`).

## Solution

```bash
grep -rn "qty \* prix\|quantite \* prix" app/services/
# Pour chaque résultat : convertir en Decimal
```

```python
# Avant
total = line.qty * line.prix_unitaire_cts  # int * int → int OK
# Mais si line.prix_unitaire_cts est Decimal en réalité (ETL)
total = float(line.qty) * float(line.prix_unitaire_cts)  # ❌ float

# Après
total = Decimal(line.qty) * Decimal(line.prix_unitaire_cts)
```

### Script CI

```python
# tools/check_no_float_centimes.py
"""Refuse arithmétique float sur centimes dans services money/stock."""
PATTERN = re.compile(r"float\(.*_cents.*\)|float\(.*prix_cts.*\)")
```

## DoD

- [ ] Audit grep + fix
- [ ] Script CI actif
- [ ] Test : 1000 unités × 123.45 cents → Decimal exact

---

# Story B5.S6.T6 — Validation finale Bloc 5

## Contexte

Sprint final Bloc 5, audit cohérence checklist.

## Solution

### Test E2E Restaurant complet

```python
async def test_bloc5_e2e_restaurant_workflow(client, tenant_resto, tenant_epi):
    # 1. ETL upload TAIYAT → AWAITING_VENDOR_MATCH si vendor inconnu
    # 2. Resolve vendor → run import → SUCCES
    # 3. Lancement marmite carry poulet 20 portions → consomme 10kg poulet (formule batch)
    # 4. Commande envoyée 5 portions → ligne ENVOYEE
    # 5. Cancel ligne → portions returned to marmite
    # 6. payer commande → FinanceInvoice CLIENT_RESTAURANT créée
    # 7. TransferRequest resto → epi pour 5kg tomates
    # 8. Auto-approve → APPROVED
    # 9. Fulfill → InternalTransfer IN_TRANSIT + stock épi -5kg
    # 10. Receive → stock_restaurant +5kg
```

## DoD

- [ ] Test E2E workflow restaurant 10 étapes
- [ ] Audit checklist Bloc 5 passé
- [ ] Tous Bloc 5 sprints livrés

---

## Critères de succès Sprint B5.S6

- [ ] **TR-54 / F923 résolu** : workflow TransferRequest complet APPROVED → FULFILLED
- [ ] **Q32=A résolu** : auto-approve par stock check + advisory lock anti race
- [ ] **F912 résolu** : conversion auto InternalTransfer + receive
- [ ] **TR-41 / F871 résolu** : `with_for_update` valider_transfert
- [ ] **TR-56 résolu** : Decimal end-to-end
- [ ] Test E2E restaurant workflow complet
- [ ] **Bloc 5 verrouillé** : 6 sprints livrés (B5.S1 → B5.S6)

---

**Fin du document — 15-sprint-B5.S6.md**
