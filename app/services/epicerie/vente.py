"""Service Vente POS épicerie — encaissement atomique et annulation.

Invariant atomique POST /ventes/encaisser (FC_EPICERIE_POS §4) :
  1. Résoudre produits DB, calculer totaux bruts
  2. Valider remise_centimes <= total_ttc_brut → 422 REMISE_INVALIDE
  3. Calculer total_ttc_remise, HT/TVA remisés (proportion)
  4. Valider montants paiement >= total_ttc_remise → 422 PAIEMENT_INSUFFISANT
  5. Vérifier stocks si check_stock=True → 409 STOCK_INSUFFISANT
  6. Créer EpicerieVente (EN_COURS)
  7. Créer EpicerieVenteLigne + mouvements VENTE
  8. Créer FinanceInvoice (CLIENT) + marquer PAYEE
  9. Passer vente à VALIDEE

Annulation : remet en stock via mouvements AJUSTEMENT (FC_EPICERIE_POS §5).
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.epicerie.vente import AsyncEpicerieVenteRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.vente import EncaissementRequest, EncaissementResponse

_STATUT_ANNULABLE = {"EN_COURS", "VALIDEE"}


def _prix_unitaire_ht(prix_ttc: int, taux_tva: int) -> int:
    """Prix unitaire HT depuis TTC — TVA extraite (ADR-06-BIS)."""
    return round(prix_ttc * 10000 / (10000 + taux_tva))


def _calcul_ligne(prix_unitaire_cts: int, taux_tva: int, quantite: float) -> dict:
    """Calcule les montants bruts d'une ligne (sans remise — remise globale uniquement)."""
    montant_ttc = round(prix_unitaire_cts * quantite)
    pu_ht = _prix_unitaire_ht(prix_unitaire_cts, taux_tva)
    montant_ht = round(pu_ht * quantite)
    return {
        "prix_unitaire_ht": pu_ht,
        "montant_ht": montant_ht,
        "montant_tva": montant_ttc - montant_ht,
        "montant_ttc": montant_ttc,
    }


def _appliquer_remise(total_ht_brut: int, total_ttc_brut: int, remise_centimes: int) -> dict:
    """Calcule les totaux après remise globale proportionnelle."""
    total_ttc_remise = total_ttc_brut - remise_centimes
    facteur = total_ttc_remise / total_ttc_brut if total_ttc_brut > 0 else 1
    total_ht_remise = round(total_ht_brut * facteur)
    return {
        "total_ttc_remise": total_ttc_remise,
        "total_ht_remise": total_ht_remise,
        "total_tva_remise": total_ttc_remise - total_ht_remise,
    }


def _valider_remise(remise_centimes: int, total_ttc_brut: int) -> None:
    if remise_centimes > total_ttc_brut:
        raise HTTPException(status_code=422, detail="REMISE_INVALIDE")


def _valider_paiement(payload: EncaissementRequest, total_ttc_remise: int) -> None:
    somme = payload.montant_especes + payload.montant_cb + payload.montant_virement
    if somme < total_ttc_remise:
        raise HTTPException(status_code=422, detail="PAIEMENT_INSUFFISANT")


async def encaisser(
    db: AsyncSession,
    tenant_id: int,
    payload: EncaissementRequest,
    vendeur_id: Optional[int] = None,
) -> EncaissementResponse:
    """Encaissement POS atomique — FC_EPICERIE_POS §4."""
    produit_repo = AsyncEpicerieProduitRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)
    vente_repo = AsyncEpicerieVenteRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)

    # Phase 1 — résolution produits + calcul lignes brutes
    lignes_calculees = []
    for ligne in payload.lignes:
        produit = await produit_repo.get_by_id(ligne.produit_id, tenant_id)
        if produit is None or not produit.actif:
            raise NotFound(f"Produit {ligne.produit_id} introuvable ou inactif")
        calcul = _calcul_ligne(produit.prix_unitaire_cts, produit.taux_tva, ligne.quantite)
        lignes_calculees.append({"produit": produit, "ligne": ligne, **calcul})

    # Phase 2 — totaux bruts
    total_ht_brut = sum(lc["montant_ht"] for lc in lignes_calculees)
    total_ttc_brut = sum(lc["montant_ttc"] for lc in lignes_calculees)
    total_tva_brut = total_ttc_brut - total_ht_brut

    # Phase 3 — validation remise + calcul remisé
    _valider_remise(payload.remise_centimes, total_ttc_brut)
    remise = _appliquer_remise(total_ht_brut, total_ttc_brut, payload.remise_centimes)

    # Phase 4 — validation paiement
    _valider_paiement(payload, remise["total_ttc_remise"])
    monnaie_rendue = max(0, payload.montant_especes - remise["total_ttc_remise"])

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

    now = datetime.now(timezone.utc)

    # Phase 6 — création vente
    vente = await vente_repo.create_vente(
        tenant_id=tenant_id,
        date_vente=now,
        mode_paiement=payload.mode_paiement.upper(),
        total_ht=remise["total_ht_remise"],
        total_tva=remise["total_tva_remise"],
        total_ttc=remise["total_ttc_remise"],
        remise_pct=0.0,
        remise_montant=payload.remise_centimes,
        montant_especes=payload.montant_especes,
        montant_cb=payload.montant_cb,
        montant_rendu=monnaie_rendue,
        client_nom=payload.client_nom,
        client_email=None,
        vendeur_id=vendeur_id,
        notes=payload.remise_motif,
    )

    # Phase 7 — lignes + mouvements stock
    for lc in lignes_calculees:
        await vente_repo.create_ligne(
            tenant_id=tenant_id,
            vente_id=vente.id,
            produit_id=lc["produit"].id,
            quantite=lc["ligne"].quantite,
            prix_unitaire_ht=lc["prix_unitaire_ht"],
            taux_tva=lc["produit"].taux_tva,
            montant_ht=lc["montant_ht"],
            montant_tva=lc["montant_tva"],
            montant_ttc=lc["montant_ttc"],
            remise_pct=0.0,
        )
        stock = await stock_repo.get_or_create(lc["produit"].id, tenant_id)
        nouvelle_qte = float(stock.quantite) - lc["ligne"].quantite
        await stock_repo.update_quantite(stock, -lc["ligne"].quantite)
        await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=lc["produit"].id,
            type="VENTE",
            quantite=-lc["ligne"].quantite,
            stock_apres=nouvelle_qte,
            vente_id=vente.id,
            created_by_id=vendeur_id,
        )

    # Phase 8 — facture CLIENT
    invoice = await invoice_repo.create(
        tenant_id=tenant_id,
        type="CLIENT",
        date_facture=now.date(),
        montant_ht=remise["total_ht_remise"],
        montant_tva=remise["total_tva_remise"],
        montant_ttc=remise["total_ttc_remise"],
        vente_id=vente.id,
        reference=vente.numero_ticket,
    )
    await invoice_repo.update_statut(invoice, "PAYEE")

    # Phase 9 — VALIDEE
    await vente_repo.update_statut(vente, "VALIDEE", invoice_id=invoice.id)

    return EncaissementResponse(
        id=vente.id,
        numero_ticket=vente.numero_ticket,
        statut="VALIDEE",
        total_ht_brut=total_ht_brut,
        total_tva_brut=total_tva_brut,
        total_ttc_brut=total_ttc_brut,
        remise_centimes=payload.remise_centimes,
        remise_motif=payload.remise_motif,
        total_ttc_remise=remise["total_ttc_remise"],
        total_ht_remise=remise["total_ht_remise"],
        total_tva_remise=remise["total_tva_remise"],
        monnaie_rendue=monnaie_rendue,
        created_at=now,
    )


async def annuler_vente(
    db: AsyncSession,
    tenant_id: int,
    vente_id: int,
) -> None:
    """Annule une vente et remet en stock via mouvements AJUSTEMENT (FC §5)."""
    vente_repo = AsyncEpicerieVenteRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)

    vente = await vente_repo.get_by_id(vente_id, tenant_id)
    if vente is None:
        raise NotFound(f"Vente {vente_id} introuvable")
    if vente.statut not in _STATUT_ANNULABLE:
        raise HTTPException(
            status_code=409,
            detail=f"Impossible d'annuler une vente au statut {vente.statut!r}",
        )

    lignes = await vente_repo.list_lignes(vente.id)
    for ligne in lignes:
        stock = await stock_repo.get_or_create(ligne.produit_id, tenant_id)
        nouvelle_qte = float(stock.quantite) + float(ligne.quantite)
        await stock_repo.update_quantite(stock, float(ligne.quantite))
        await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=ligne.produit_id,
            type="AJUSTEMENT",
            quantite=float(ligne.quantite),
            stock_apres=nouvelle_qte,
            vente_id=vente.id,
        )

    await vente_repo.update_statut(vente, "ANNULEE")
