"""Service Transferts internes epicerie -> restaurant.

3 fonctions publiques calquees sur le pattern recevoir_commande() :
  - creer_transfert  : cree un transfert PENDING avec lignes
  - valider_transfert : atomique — stock epicerie + stock restaurant + invoice
  - annuler_transfert : annule un transfert PENDING

Stock restaurant via MouvementStockService.create() (SELECT FOR UPDATE + alertes).
Stock epicerie via AsyncEpicerieStockRepository (pattern eprouve).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.epicerie.internal_transfer import InternalTransfer
from app.repositories.epicerie.internal_transfer import AsyncInternalTransferRepository
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.transfert import InternalTransferCreate


def _calcul_ligne(prix_unitaire: int, quantite: float, tva_pct: int) -> tuple[int, int]:
    """Calcule montant_ht et montant_ttc pour une ligne."""
    montant_ht = round(prix_unitaire * quantite)
    tva = round(montant_ht * tva_pct / 10000)
    return montant_ht, montant_ht + tva


async def creer_transfert(
    db: AsyncSession,
    tenant_id: int,
    payload: InternalTransferCreate,
    user_id: int,
) -> InternalTransfer:
    """Cree un transfert interne PENDING avec ses lignes."""
    if tenant_id == payload.dest_tenant_id:
        raise BadRequest("Source et destination ne peuvent pas etre identiques")

    repo = AsyncInternalTransferRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)

    # Valider tous les produits avant de creer quoi que ce soit
    for ligne in payload.lignes:
        produit = await produit_repo.get_by_id(ligne.produit_id, tenant_id)
        if produit is None:
            raise NotFound(f"Produit {ligne.produit_id} introuvable ou inactif")

        if ligne.ingredient_id is not None:
            from app.repositories.restaurant.ingredient import AsyncIngredientRepo
            ing_repo = AsyncIngredientRepo(db)
            ing = await ing_repo.get_by_id(ligne.ingredient_id)
            if ing is None:
                raise NotFound(f"Ingredient {ligne.ingredient_id} introuvable")

    # Creer le transfert
    transfer = await repo.create(
        tenant_id=tenant_id,
        dest_tenant_id=payload.dest_tenant_id,
        reference=payload.reference,
        notes=payload.notes,
        created_by=user_id,
    )

    # Creer les lignes
    for ligne in payload.lignes:
        produit = await produit_repo.get_by_id(ligne.produit_id, tenant_id)
        montant_ht, montant_ttc = _calcul_ligne(
            ligne.prix_unitaire, ligne.quantite, ligne.tva_pct,
        )
        await repo.create_line(
            transfer_id=transfer.id,
            produit_id=ligne.produit_id,
            designation=produit.designation_clean,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            montant_ht=montant_ht,
            montant_ttc=montant_ttc,
            tva_pct=ligne.tva_pct,
            unite=ligne.unite,
            ingredient_id=ligne.ingredient_id,
        )

    return transfer


async def valider_transfert(
    db: AsyncSession,
    tenant_id: int,
    transfer_id: int,
    user_id: int,
) -> InternalTransfer:
    """Validation atomique : stock epicerie + stock restaurant + invoice."""
    repo = AsyncInternalTransferRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)

    transfer = await repo.get_by_id(transfer_id, tenant_id)
    if transfer is None:
        raise NotFound(f"Transfert {transfer_id} introuvable")
    if transfer.status != "PENDING":
        raise BadRequest(f"Transfert non validable au statut {transfer.status!r}")

    lines = await repo.list_lines(transfer_id)
    total_ht = 0
    total_ttc = 0

    for line in lines:
        montant_ht, montant_ttc = _calcul_ligne(
            line.prix_unitaire, float(line.quantite), line.tva_pct,
        )
        total_ht += montant_ht
        total_ttc += montant_ttc

        mvt_epicerie_id = None
        mvt_restaurant_id = None

        # 1. Decrementer stock epicerie
        stock = await stock_repo.get_by_produit(line.produit_id, tenant_id)
        if stock is None:
            raise BadRequest(f"Stock introuvable pour produit {line.produit_id}")
        nouvelle_qte = float(stock.quantite) - float(line.quantite)
        if nouvelle_qte < 0:
            raise BadRequest(
                f"Stock insuffisant pour '{line.designation}' "
                f"(dispo: {stock.quantite}, demande: {line.quantite})"
            )
        await stock_repo.update_quantite(stock, -float(line.quantite))
        mvt_epicerie_obj = await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=line.produit_id,
            type="TRANSFERT_RESTAURANT",
            quantite=-float(line.quantite),
            stock_apres=nouvelle_qte,
            transfer_id=transfer_id,
            notes=f"Transfert #{transfer.id}",
            created_by_id=user_id,
        )
        mvt_epicerie_id = mvt_epicerie_obj.id

        # 2. Incrementer stock restaurant (si ingredient associe)
        if line.ingredient_id is not None:
            from app.services.restaurant.mouvement_stock import MouvementStockService
            from app.schemas.restaurant.mouvement_stock import MouvementStockCreate

            mvt_service = MouvementStockService(db)
            mvt_payload = MouvementStockCreate(
                ingredient_id=line.ingredient_id,
                type_mouvement="transfert_entrant",
                quantite=Decimal(str(line.quantite)),
                date_mouvement=datetime.now(timezone.utc),
                notes=f"Transfert epicerie #{transfer.id}",
            )
            mvt_response = await mvt_service.create(
                mvt_payload, created_by_id=user_id,
            )
            if mvt_response is not None:
                mvt_restaurant_id = mvt_response.id

        # 3. Lier mouvements a la ligne
        await repo.update_line_mouvements(
            line,
            mouvement_epicerie_id=mvt_epicerie_id,
            mouvement_restaurant_id=mvt_restaurant_id,
        )

    # 4. Facture interne
    now = datetime.now(timezone.utc)
    invoice = await invoice_repo.create(
        tenant_id=tenant_id,
        type="INTERNE",
        date_facture=now.date(),
        montant_ht=total_ht,
        montant_tva=total_ttc - total_ht,
        montant_ttc=total_ttc,
        transfer_id=transfer_id,
    )
    await invoice_repo.update_statut(invoice, "PAYEE")

    # 5. Marquer valide
    await repo.validate(
        transfer=transfer,
        validated_by=user_id,
        invoice_id=invoice.id,
        montant_ht=total_ht,
        montant_ttc=total_ttc,
    )

    return transfer


async def annuler_transfert(
    db: AsyncSession,
    tenant_id: int,
    transfer_id: int,
    raison: Optional[str] = None,
) -> InternalTransfer:
    """Annule un transfert PENDING."""
    repo = AsyncInternalTransferRepository(db)

    transfer = await repo.get_by_id(transfer_id, tenant_id)
    if transfer is None:
        raise NotFound(f"Transfert {transfer_id} introuvable")
    if transfer.status != "PENDING":
        raise BadRequest(f"Transfert non annulable au statut {transfer.status!r}")

    await repo.cancel(transfer, raison=raison)
    return transfer
