"""Service épicerie — Workflow approbation des TransferRequest entrantes.

Distinct de `app.services.restaurant.transfer_request.TransferRequestService` :
  - Le service restaurant est invoqué par le tenant ÉMETTEUR (create/list own/cancel)
  - Ce service est invoqué par le tenant CIBLE épicerie (list inbound/approve/reject)

Flow complet (depuis 2026-04-21) :
  1. Restaurant crée TransferRequest avec lignes {ingredient_id, qte_besoin}
  2. Épicerie appelle preview_resolution() pour voir la proposition cascade
  3. Épicerie appelle approve_with_transfer() avec overrides optionnels →
     crée un InternalTransfer PENDING + marque la request FULFILLED
  4. Épicerie valide l'InternalTransfer (stock mvt, facture) via
     services.epicerie.transfert.valider_transfert
"""
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.epicerie.produit import EpicerieProduit
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.repositories.restaurant.transfer_request import AsyncTransferRequestRepo
from app.schemas.epicerie.transfert import InternalTransferCreate, TransferLineCreate
from app.schemas.restaurant.ingredient_epicerie_mapping import (
    ApproveWithTransferRequest,
    ApproveWithTransferResponse,
    PreviewResolutionResponse,
    RequestLineResolution,
)
from app.schemas.restaurant.transfer_request import TransferRequestRead


class EpicerieTransferRequestService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = AsyncTransferRequestRepo(db)

    async def list_inbound(
        self,
        target_tenant_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[TransferRequestRead], int]:
        items, total = await self._repo.list_inbound(
            target_tenant_id=target_tenant_id,
            page=page,
            per_page=per_page,
            status=status,
        )
        return [TransferRequestRead.model_validate(i) for i in items], total

    async def approve(
        self,
        request_id: int,
        target_tenant_id: int,
    ) -> TransferRequestRead:
        approved = await self._repo.approve(request_id, target_tenant_id)
        if approved is None:
            raise NotFound("TransferRequest")
        await self._db.refresh(approved, attribute_names=["updated_at", "lignes"])
        result = TransferRequestRead.model_validate(approved)
        await self._db.commit()
        return result

    async def reject(
        self,
        request_id: int,
        target_tenant_id: int,
        raison: Optional[str],
    ) -> TransferRequestRead:
        rejected = await self._repo.reject(request_id, target_tenant_id, raison)
        if rejected is None:
            raise NotFound("TransferRequest")
        await self._db.refresh(rejected, attribute_names=["updated_at", "lignes"])
        result = TransferRequestRead.model_validate(rejected)
        await self._db.commit()
        return result

    # ── Nouveau workflow : résolveur cascade + création InternalTransfer ──

    async def preview_resolution(
        self, request_id: int, target_tenant_id: int,
    ) -> PreviewResolutionResponse:
        """Dry-run : calcule la résolution cascade pour toutes les lignes
        de la demande. Ne modifie rien en base.
        """
        # Import local pour éviter les cycles
        from app.services.restaurant.ingredient_sourcing import IngredientSourcingService

        request = await self._repo.get_for_target(request_id, target_tenant_id)
        if request is None:
            raise NotFound("TransferRequest")

        sourcing = IngredientSourcingService(self._db)
        lines: list[RequestLineResolution] = []
        unresolvable: list[int] = []

        for rline in request.lignes:
            if rline.ingredient_restaurant_id is None:
                unresolvable.append(rline.id)
                continue

            # Le mapping vit sur le tenant restaurant (source)
            try:
                resolution = await sourcing.resolve(
                    rline.ingredient_restaurant_id,
                    Decimal(rline.quantity),
                    request.tenant_id,
                )
            except ValueError:
                # Ingrédient référencé mais introuvable côté restaurant
                unresolvable.append(rline.id)
                continue

            stmt = select(IngredientRestaurant).where(
                IngredientRestaurant.id == rline.ingredient_restaurant_id,
                IngredientRestaurant.tenant_id == request.tenant_id,
            )
            ingr = (await self._db.execute(stmt)).scalar_one_or_none()
            nom = ingr.nom if ingr is not None else "?"

            lines.append(RequestLineResolution(
                request_line_id=rline.id,
                ingredient_restaurant_id=rline.ingredient_restaurant_id,
                ingredient_nom=nom,
                qte_besoin=resolution.qte_besoin,
                items=resolution.items,
                couverture_complete=resolution.couverture_complete,
                deficit=resolution.deficit,
            ))

        return PreviewResolutionResponse(
            request_id=request_id,
            lines=lines,
            unresolvable_line_ids=unresolvable,
            any_deficit=any(not l.couverture_complete for l in lines),
        )

    async def approve_with_transfer(
        self,
        request_id: int,
        target_tenant_id: int,
        user_id: int,
        payload: ApproveWithTransferRequest,
    ) -> ApproveWithTransferResponse:
        """Approuve une demande et crée l'InternalTransfer correspondant
        (status PENDING — validation physique séparée via valider_transfert).

        - Si `payload.overrides` : utilise ces lignes telles quelles.
        - Sinon : calcule la résolution cascade automatiquement.
        """
        from app.services.epicerie.transfert import creer_transfert

        request = await self._repo.get_for_target(request_id, target_tenant_id)
        if request is None:
            raise NotFound("TransferRequest")
        if request.status != "PENDING":
            raise BadRequest(
                f"Demande au statut {request.status!r}, approbation impossible"
            )

        warnings: list[str] = []
        transfer_lines: list[TransferLineCreate] = []

        if payload.overrides:
            for o in payload.overrides:
                transfer_lines.append(TransferLineCreate(
                    produit_id=o.produit_id,
                    ingredient_id=o.ingredient_id,
                    quantite=float(o.quantite),
                    unite=o.unite,
                    prix_unitaire=o.prix_unitaire,
                    tva_pct=o.tva_pct,
                ))
        else:
            preview = await self.preview_resolution(request_id, target_tenant_id)
            if preview.unresolvable_line_ids:
                warnings.append(
                    f"{len(preview.unresolvable_line_ids)} ligne(s) sans ingrédient "
                    "mappé ignorée(s)"
                )
            for line_res in preview.lines:
                if not line_res.couverture_complete:
                    warnings.append(
                        f"Ingrédient '{line_res.ingredient_nom}' : déficit "
                        f"{line_res.deficit} (couverture partielle)"
                    )
                for item in line_res.items:
                    prod_stmt = select(EpicerieProduit).where(
                        EpicerieProduit.id == item.produit_id,
                        EpicerieProduit.tenant_id == target_tenant_id,
                    )
                    prod = (await self._db.execute(prod_stmt)).scalar_one_or_none()
                    if prod is None:
                        warnings.append(
                            f"Produit #{item.produit_id} hors tenant épicerie, ligne "
                            "ignorée"
                        )
                        continue
                    transfer_lines.append(TransferLineCreate(
                        produit_id=item.produit_id,
                        ingredient_id=line_res.ingredient_restaurant_id,
                        quantite=float(item.qte_prelevee_unites_vente),
                        unite=prod.unite_vente,
                        prix_unitaire=prod.prix_achat_cts,
                        tva_pct=prod.taux_tva,
                    ))

        if not transfer_lines:
            raise BadRequest(
                "Aucune ligne de transfert à créer "
                "(couverture vide ou demande sans ingrédient mappé)"
            )

        transfer_payload = InternalTransferCreate(
            dest_tenant_id=request.tenant_id,
            reference=payload.reference or f"REQ-{request_id}",
            notes=payload.notes or f"Approbation TransferRequest #{request_id}",
            lignes=transfer_lines,
        )
        transfer = await creer_transfert(
            db=self._db,
            tenant_id=target_tenant_id,
            payload=transfer_payload,
            user_id=user_id,
        )

        approved = await self._repo.approve(
            request_id, target_tenant_id,
            fulfilled_transfer_id=transfer.id,
        )
        if approved is None:  # race condition rarissime
            raise NotFound("TransferRequest")

        return ApproveWithTransferResponse(
            transfer_id=transfer.id,
            warnings=warnings,
        )
