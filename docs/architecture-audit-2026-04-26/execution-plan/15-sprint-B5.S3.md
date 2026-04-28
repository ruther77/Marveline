# Sprint B5.S3 — FSM helper appliqué multi-app + cancel cascade unifié + protéine XOR

> **STATUT** : ⏳ À démarrer après B5.S2
> **DURÉE MAX** : 2 semaines
> **OWNER** : Dev3
> **BLOQUE** : B5.S4 (Celery tenant-aware), B5.S6 (TransferRequest workflow)
> **DÉPEND DE** : B3.S2 (FSM helper), B5.S1 (cancel resto cascade tactique)
> **OBJECTIF** : Appliquer le pattern FSM helper (B3.S2) à toutes les entités multi-app : `EpicerieVenteFSM`, `CommandeRestaurantFSM`, `LigneCommandeFSM`, `EtlImportFSM`, `EtlConflictFSM`, `InternalTransferFSM`, `TransferRequestFSM`. Unifier cancel cascade. Implémenter protéine XOR (F913 — recette TypePreparation seul, drop `VariantePlat.ingredient_proteine_id` selon Q31=A). Annuler vente épicerie VALIDEE → CreditNote + remise stock + audit (F872 / TR-44).

## Vue d'ensemble

| Story | Friction | Sévérité | Estimation | Bloque |
|---|---|---|---|---|
| **B5.S3.T1** | FSM matrices 7 entités multi-app + DB triggers + tables fsm_transitions logging | P0 | 2.5 j | T2-T4 |
| **B5.S3.T2** | F913 / Q31=A — Drop `VariantePlat.ingredient_proteine_id` + migration data → recette | P0 | 1.5 j | aucun |
| **B5.S3.T3** | F872 / TR-44 — `EpicerieVente.annuler_vente VALIDEE` → CreditNote + remise stock + audit | P0 | 1.5 j | aucun |
| **B5.S3.T4** | Cancel cascade unifié pour `InternalTransfer` + `TransferRequest` | P1 | 1 j | aucun |
| **B5.S3.T5** | Audit `@audit_action` cohérent multi-app (drop décor middleware sur mutations) | P1 | 1 j | aucun |

**Total effort** : 7.5 jours-homme.

---

# Story B5.S3.T1 — FSM matrices 7 entités multi-app

## Contexte

**Décision** : pattern FSM helper Bloc 3 réappliqué intégralement
**Sévérité** : P0 — sans FSM enforced, transitions illégales `OUVERTE → ANNULEE direct` sur restaurant_commandes possibles

### Description

7 matrices à ajouter au registry `FSM_MATRICES` (cf. B3.S2.T1) + triggers DB enforcement.

## Solution

### Matrices

```python
# app/services/fsm.py — registry étendu

# Épicerie
EPICERIE_VENTE_FSM = FSMMatrix(
    entity_type="epicerie_vente",
    transitions={
        ("PANIER", "VALIDEE"),
        ("VALIDEE", "PAYEE"),
        ("VALIDEE", "ANNULEE"),
        ("PAYEE", "ANNULEE"),  # → CreditNote (T3)
        ("PANIER", "ANNULEE"),
    },
    initial_states={"PANIER"},
    terminal_states={"PAYEE", "ANNULEE"},
)

# Restaurant
COMMANDE_RESTAURANT_FSM = FSMMatrix(
    entity_type="commande_restaurant",
    transitions={
        ("OUVERTE", "FERMEE"),       # cuisine validée → addition
        ("FERMEE", "PAYEE"),
        ("OUVERTE", "ANNULEE"),
        ("FERMEE", "ANNULEE"),       # cancel avant paiement
        # OUVERTE → PAYEE INTERDIT (must close first)
    },
    initial_states={"OUVERTE"},
    terminal_states={"PAYEE", "ANNULEE"},
)

LIGNE_COMMANDE_FSM = FSMMatrix(
    entity_type="ligne_commande",
    transitions={
        ("ENVOYEE", "EN_PREPARATION"),
        ("EN_PREPARATION", "PRETE"),
        ("PRETE", "SERVIE"),
        ("ENVOYEE", "ANNULEE"),
        ("EN_PREPARATION", "ANNULEE"),
        ("PRETE", "ANNULEE"),
        # SERVIE → ANNULEE INTERDIT (déjà consommé)
    },
    initial_states={"ENVOYEE"},
    terminal_states={"SERVIE", "ANNULEE"},
)

# ETL
ETL_IMPORT_FSM = FSMMatrix(
    entity_type="etl_import",
    transitions={
        ("PARSING", "AWAITING_VENDOR_MATCH"),
        ("PARSING", "VALIDATING"),
        ("AWAITING_VENDOR_MATCH", "VALIDATING"),
        ("VALIDATING", "SUCCES"),
        ("VALIDATING", "PARTIEL"),
        ("VALIDATING", "ECHEC"),  # B5.S2.T7 résolu
    },
    initial_states={"PARSING"},
    terminal_states={"SUCCES", "PARTIEL", "ECHEC"},
)

ETL_CONFLICT_FSM = FSMMatrix(
    entity_type="etl_conflict",
    transitions={
        ("PENDING", "RESOLVED_AUTO"),
        ("PENDING", "RESOLVED_MANUAL"),
        ("PENDING", "REJECTED"),
    },
    initial_states={"PENDING"},
    terminal_states={"RESOLVED_AUTO", "RESOLVED_MANUAL", "REJECTED"},
)

# Transferts
INTERNAL_TRANSFER_FSM = FSMMatrix(
    entity_type="internal_transfer",
    transitions={
        ("PENDING", "IN_TRANSIT"),
        ("IN_TRANSIT", "RECEIVED"),
        ("PENDING", "CANCELLED"),
        ("IN_TRANSIT", "CANCELLED"),
    },
    initial_states={"PENDING"},
    terminal_states={"RECEIVED", "CANCELLED"},
)

TRANSFER_REQUEST_FSM = FSMMatrix(
    entity_type="transfer_request",
    transitions={
        ("PENDING", "APPROVED"),
        ("PENDING", "REJECTED"),
        ("APPROVED", "FULFILLED"),  # B5.S6 livre fulfilled_transfer_id
        ("APPROVED", "CANCELLED"),
        ("PENDING", "CANCELLED"),
    },
    initial_states={"PENDING"},
    terminal_states={"FULFILLED", "REJECTED", "CANCELLED"},
)

# Register all
for matrix in [
    EPICERIE_VENTE_FSM, COMMANDE_RESTAURANT_FSM, LIGNE_COMMANDE_FSM,
    ETL_IMPORT_FSM, ETL_CONFLICT_FSM, INTERNAL_TRANSFER_FSM, TRANSFER_REQUEST_FSM,
]:
    FSM_MATRICES[matrix.entity_type] = matrix
```

### DB Triggers

```python
# alembic/versions/i1a2b3c4d5ff_fsm_triggers_multi_app.py
def upgrade() -> None:
    # Pattern partagé : trigger BEFORE UPDATE OF status sur chaque table
    # Generated dynamically pour les 7 entités
    
    for entity_table, transitions in [
        ("epicerie_ventes", EPICERIE_VENTE_TRANSITIONS_SQL),
        ("restaurant_commandes", COMMANDE_RESTAURANT_TRANSITIONS_SQL),
        # ...
    ]:
        op.execute(text(f"""
            CREATE OR REPLACE FUNCTION {entity_table}_fsm_check()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.status = NEW.status THEN RETURN NEW; END IF;
                IF NOT ({transitions}) THEN
                    RAISE EXCEPTION '{entity_table}_fsm_invalid: % -> %', OLD.status, NEW.status;
                END IF;
                RETURN NEW;
            END $$ LANGUAGE plpgsql;
        """))
        op.execute(text(f"""
            CREATE TRIGGER trg_{entity_table}_fsm_check
            BEFORE UPDATE OF status ON {entity_table}
            FOR EACH ROW EXECUTE FUNCTION {entity_table}_fsm_check();
        """))
```

### Tests

```python
async def test_commande_restaurant_ouverte_to_payee_direct_refused(db, commande_ouverte):
    """OUVERTE → PAYEE direct interdit (must FERMEE first)."""
    with pytest.raises(IntegrityError, match="commande_restaurant_fsm_invalid"):
        await db.execute(
            update(CommandeRestaurant).where(CommandeRestaurant.id == commande_ouverte.id).values(status="PAYEE")
        )

async def test_ligne_servie_to_annulee_refused(db, ligne_servie):
    """SERVIE déjà consommée → cancel impossible."""
    with pytest.raises(IntegrityError, match="ligne_commande_fsm_invalid"):
        await db.execute(
            update(LigneCommande).where(LigneCommande.id == ligne_servie.id).values(status="ANNULEE")
        )
```

## DoD

- [ ] 7 matrices ajoutées au registry
- [ ] 7 triggers DB BEFORE UPDATE
- [ ] Tests transitions illégales pour chaque entité
- [ ] Logs `fsm_transitions` cohérents (B3.S2.T2)

---

# Story B5.S3.T2 — Drop `VariantePlat.ingredient_proteine_id` (F913 / Q31=A)

## Contexte

**Friction** : F913, TR-45 (cf. `architecture-cible.md Q31=A`)
**Sévérité** : P0 — double consommation protéine si admin remplit recette ET variante
**Code source** : `app/models/variante_plat.py`, `app/models/recette_type_preparation.py`

### Description

Décision Q31=A : protéine = ligne dans `RecetteTypePreparation` UNIQUEMENT. Drop `VariantePlat.ingredient_proteine_id` + `quantite_proteine` après backfill.

## Solution

### Migration data

```python
# tools/migrate_proteine_to_recette.py (one-shot)
"""Convertit (variante.ingredient_proteine_id, variante.quantite_proteine) en lignes RecetteTypePreparation."""
async def migrate():
    async with AsyncSessionLocal() as db:
        # Pour chaque VariantePlat avec ingredient_proteine_id défini
        variantes = await db.scalars(
            select(VariantePlat).where(VariantePlat.ingredient_proteine_id.is_not(None))
        )
        for v in variantes.all():
            # Vérifier si la recette TypePreparation a déjà la protéine
            existing = await db.scalar(
                select(RecetteTypePreparation).where(
                    RecetteTypePreparation.type_preparation_id == v.type_preparation_id,
                    RecetteTypePreparation.ingredient_id == v.ingredient_proteine_id,
                )
            )
            if existing is None:
                db.add(RecetteTypePreparation(
                    type_preparation_id=v.type_preparation_id,
                    ingredient_id=v.ingredient_proteine_id,
                    quantite_par_batch=v.quantite_proteine,
                ))
        await db.commit()
```

### Migration drop colonnes

```python
def upgrade() -> None:
    # Pre-check : aucune variante non migrée
    op.execute(text("""
        DO $$ BEGIN
            IF (SELECT COUNT(*) FROM variantes_plat WHERE ingredient_proteine_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM recettes_type_preparation r
                    WHERE r.type_preparation_id = variantes_plat.type_preparation_id
                      AND r.ingredient_id = variantes_plat.ingredient_proteine_id
                )) > 0 THEN
                RAISE EXCEPTION 'Migration data manquante : run tools/migrate_proteine_to_recette.py';
            END IF;
        END $$
    """))
    op.drop_column("variantes_plat", "ingredient_proteine_id")
    op.drop_column("variantes_plat", "quantite_proteine")
```

### Service refacto

```python
# app/services/restaurant/instance_preparation.py
class InstancePreparationService:
    async def lancer_marmite(self, type_prep_id, portions, tenant_id):
        # AVANT : consommait variante.ingredient_proteine_id séparément
        # APRÈS : consomme tout via recette_type_preparation
        await self._verifier_et_consommer_recette(type_prep_id, portions, tenant_id)
        # Plus de _consommer_proteine_variante() séparé
```

## DoD

- [ ] Script migration data testé
- [ ] Migration drop colonnes après check
- [ ] Service ne consomme plus que via recette
- [ ] Test : marmite carry poulet → poulet consommé 1× (pas 2×)

---

# Story B5.S3.T3 — `EpicerieVente.annuler_vente VALIDEE` → CreditNote (F872 / TR-44)

## Contexte

**Friction** : F872, TR-44
**Sévérité** : P0 — stock revient mais facture reste `PAYEE` ; reporting TVA + CA divergent

### Description

Cible : annulation vente épicerie au statut `PAYEE` → orchestre :
1. FSM transit `PAYEE → ANNULEE`
2. Remise stock (epicerie_stock_management.qty_available += line.qty)
3. Movement `RETOUR_ANNULATION` (epicerie_stock_movement)
4. CreditNote (FinanceCreditNote) référençant l'invoice originale
5. Outbox event `EpicerieVenteAnnulled`

## Solution

```python
# app/services/epicerie/vente.py
class EpicerieVenteService:
    async def annuler_vente(
        self,
        vente_id: UUID,
        actor_id: UUID,
        tenant_id: int,
        reason: str,
    ) -> FinanceCreditNote:
        async with self.db.begin():
            vente = await self.db.get(EpicerieVente, vente_id, options=[selectinload(EpicerieVente.lignes), selectinload(EpicerieVente.invoice)], with_for_update=True)
            await fsm.assert_transition(self.db, "epicerie_vente", vente.id, vente.status, "ANNULEE", actor_id=actor_id)

            # 1. Remise stock + movement RETOUR_ANNULATION
            for ligne in vente.lignes:
                await self.db.execute(
                    update(EpicerieStockManagement)
                    .where(EpicerieStockManagement.produit_id == ligne.produit_id)
                    .values(qty_available=EpicerieStockManagement.qty_available + ligne.qty)
                )
                self.db.add(EpicerieStockMovement(
                    produit_id=ligne.produit_id, qty=ligne.qty, type="RETOUR_ANNULATION",
                    source_type="epicerie_vente", source_id=vente.id, tenant_id=tenant_id,
                ))

            # 2. CreditNote sur invoice si payée
            credit_note = None
            if vente.invoice and vente.invoice.status == "emitted":
                credit_note = FinanceCreditNote(
                    invoice_id=vente.invoice.id,
                    tenant_id=tenant_id,
                    total_ht_cents=-vente.invoice.total_ht_cents,
                    total_tva_cents=-vente.invoice.total_tva_cents,
                    total_ttc_cents=-vente.invoice.total_ttc_cents,
                    reason=f"Annulation vente {vente.reference}: {reason}",
                    emitted_at=datetime.now(UTC),
                )
                self.db.add(credit_note)

            vente.status = "ANNULEE"
            vente.cancelled_at = datetime.now(UTC)
            vente.cancelled_reason = reason

            self.db.add(OutboxEvent(
                event_type="EpicerieVenteAnnulled",
                aggregate_id=vente.id,
                tenant_id=tenant_id,
                payload={"vente_id": str(vente.id), "credit_note_id": str(credit_note.id) if credit_note else None, "reason": reason},
            ))

            return credit_note
```

### Test

```python
async def test_annuler_vente_payee_creates_credit_note(db, vente_payee):
    credit_note = await service.annuler_vente(vente_payee.id, actor_id=user.id, tenant_id=tenant.id, reason="customer_return")
    assert credit_note is not None
    assert credit_note.total_ttc_cents == -vente_payee.total_ttc_cents

async def test_annuler_vente_returns_stock(db, vente_payee_with_stock):
    qty_avant = (await db.scalar(select(EpicerieStockManagement.qty_available).where(...))).qty_available
    await service.annuler_vente(vente_payee_with_stock.id, ...)
    qty_apres = (await db.scalar(select(EpicerieStockManagement.qty_available).where(...))).qty_available
    assert qty_apres == qty_avant + vente_payee_with_stock.lignes[0].qty
```

## DoD

- [ ] Annulation cascade stock + CreditNote + Outbox
- [ ] Movement `RETOUR_ANNULATION` créé
- [ ] Test : vente PAYEE annulée → CreditNote + stock remis
- [ ] CA + TVA reporting cohérent post-annulation

---

# Story B5.S3.T4 — Cancel cascade `InternalTransfer` + `TransferRequest`

## Contexte

**Friction** : annulation transferts non gérée

### Description

Cible : `InternalTransferCancelService` + `TransferRequestCancelService` orchestrent :
- IN_TRANSIT → cancel : remise stock à la source
- APPROVED TransferRequest → cancel : libération réservation stock côté source

## Solution

```python
# app/services/transfer/cancel.py
class InternalTransferCancelService:
    async def cancel(self, transfer_id, actor_id, tenant_id, reason):
        async with self.db.begin():
            transfer = await self.db.get(InternalTransfer, transfer_id, with_for_update=True)
            await fsm.assert_transition(self.db, "internal_transfer", transfer.id, transfer.status, "CANCELLED", actor_id=actor_id)

            # Si IN_TRANSIT : remise stock côté source
            if transfer.status == "IN_TRANSIT":
                await self.stock.reintegrate(transfer.source_id, transfer.qty, tenant_id, source_id=transfer.id)

            transfer.status = "CANCELLED"
            self.db.add(OutboxEvent(event_type="InternalTransferCancelled", ...))
```

## DoD

- [ ] Service cancel pour les 2 entités
- [ ] Test : InternalTransfer IN_TRANSIT → cancel → stock remis source
- [ ] Test : TransferRequest APPROVED → cancel → libération réservation

---

# Story B5.S3.T5 — Audit cohérent multi-app

## Contexte

Pattern décorateur `@audit_action` (B6.S2.T1) appliqué aux services multi-app.

### Description

Cible : décorer 15+ méthodes services multi-app avec `@audit_action`. Drop écriture mutations depuis middleware (déjà fait B6.S2.T1).

## Solution

```python
# app/services/restaurant/commande.py
class CommandeService:
    @audit_action(entity_type="CommandeRestaurant", action_template="commande.{op}")
    async def annuler(self, ...): ...

    @audit_action(entity_type="CommandeRestaurant", action_template="commande.{op}")
    async def payer(self, ...): ...

# Idem pour 13 autres méthodes services multi-app
```

## DoD

- [ ] 15 méthodes décorées
- [ ] Test : mutation epicerie/restaurant → AuditLog créé avec changes
- [ ] Cohérent avec B6.S2.T1 audit refondu

---

## Critères de succès Sprint B5.S3

- [ ] **7 FSM matrices** multi-app actives + triggers DB
- [ ] **F913 / Q31=A résolu** : protéine recette seule, drop `VariantePlat.ingredient_proteine_id`
- [ ] **F872 / TR-44 résolu** : annulation vente PAYEE → CreditNote
- [ ] Cancel cascade unifié `InternalTransfer` + `TransferRequest`
- [ ] Audit `@audit_action` cohérent multi-app
- [ ] Test E2E : commande resto annulée → cascade complet (stock + audit + Outbox)
- [ ] Test E2E : double protéine refusée (recette + variante simultané)

---

**Fin du document — 15-sprint-B5.S3.md**
