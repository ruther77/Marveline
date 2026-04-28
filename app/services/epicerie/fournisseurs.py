"""Service Fournisseurs épicerie — liste, stats, factures, enrichissements UX."""
from datetime import date
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFound
from app.models.catalogue.etl_import import EtlImport
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.supply_order import AsyncSupplyOrderRepository
from app.repositories.finance.vendor import AsyncFinanceVendorRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.finance import (
    AlertePrixItem,
    AlertesPrixResponse,
    CaHistoriqueItem,
    CaHistoriqueResponse,
    CategoryDistribution,
    FinanceInvoiceRead,
    FournisseurRead,
    FournisseurStats,
    QualiteResponse,
    StockMargesResponse,
)


def _badge_statut(has_retard: bool, dette: int) -> str:
    """F2 : valeurs conformes FC_EPICERIE_FOURNISSEURS §badge."""
    if has_retard:
        return "en_retard"
    if dette > 0:
        return "en_attente"
    return "a_jour"


async def list_fournisseurs(
    db: AsyncSession,
    tenant_id: int,
    search: Optional[str] = None,
) -> list[FournisseurRead]:
    """Retourne la liste des fournisseurs avec indicateurs clés (F1 : filtre search)."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)

    vendors = await vendor_repo.list_all()

    if search:
        sl = search.lower()
        vendors = [v for v in vendors if sl in (v.name or "").lower() or sl in (v.code or "").lower()]

    result = []
    for vendor in vendors:
        nb_articles = await _count_articles_vendor(produit_repo, vendor.id, tenant_id)
        ca_mensuel = await invoice_repo.sum_achats_mois(vendor.id, tenant_id)
        dette = await invoice_repo.sum_dette(vendor.id, tenant_id)
        has_retard = await invoice_repo.has_retard(vendor.id, tenant_id)

        result.append(FournisseurRead(
            vendor_id=vendor.id,
            nom=vendor.name,
            code=vendor.code,
            nb_articles=nb_articles,
            ca_mensuel_cts=ca_mensuel,
            dette_cts=dette,
            badge_statut=_badge_statut(has_retard, dette),
        ))

    return result


async def get_fournisseur_stats(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
) -> FournisseurStats:
    """Statistiques agrégées d'un fournisseur."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    supply_repo = AsyncSupplyOrderRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)

    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    livraisons_mois = await supply_repo.count_livraisons_mois(vendor_id, tenant_id)
    achats_mois = await invoice_repo.sum_achats_mois(vendor_id, tenant_id)
    invoices = await invoice_repo.list_by_vendor(vendor_id, tenant_id, limit=100)

    delai_moyen = _calcul_delai_moyen(invoices)
    categories = await _distribution_categories(produit_repo, vendor_id, tenant_id)

    return FournisseurStats(
        livraisons_mois=livraisons_mois,
        achats_mois_cts=achats_mois,
        delai_paiement_moyen_jours=delai_moyen,
        distribution_categories=categories,
    )


async def list_factures_fournisseur(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
    statut: Optional[str] = None,
) -> list[FinanceInvoiceRead]:
    """Retourne les factures d'un fournisseur (F4 : filtre statut optionnel)."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)

    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    invoices = await invoice_repo.list_by_vendor(vendor_id, tenant_id)
    if statut:
        invoices = [inv for inv in invoices if inv.statut == statut.upper()]

    return [
        FinanceInvoiceRead.model_validate(inv).model_copy(
            update={"montant_cts": inv.montant_ttc}
        )
        for inv in invoices
    ]


async def get_ca_historique(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
) -> CaHistoriqueResponse:
    """Sparkline CA mensuel TTC sur 6 mois + variation M vs M-1."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)

    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    rows = await invoice_repo.ca_par_mois(vendor_id, tenant_id, nb_mois=6)
    lookup = dict(rows)

    today = date.today()
    months: list[str] = []
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(f"{y}-{m:02d}")

    items = [CaHistoriqueItem(mois=m, montant_cts=lookup.get(m, 0)) for m in months]

    variation: Optional[float] = None
    precedent = items[-2].montant_cts
    actuel = items[-1].montant_cts
    if precedent > 0:
        variation = round((actuel - precedent) / precedent * 100, 1)

    return CaHistoriqueResponse(items=items, variation_pct=variation)


async def get_stock_marges(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
) -> StockMargesResponse:
    """Marge réelle moyenne du fournisseur vs marge moyenne du catalogue."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)

    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    items_vendor, _ = await produit_repo.list_paginated(
        tenant_id=tenant_id, vendor_id=vendor_id, per_page=1000
    )
    items_all, _ = await produit_repo.list_paginated(
        tenant_id=tenant_id, per_page=5000
    )

    def _marge_pct(p) -> Optional[float]:
        if not p.prix_achat_cts or p.prix_achat_cts <= 0:
            return None
        if not p.prix_unitaire_cts or p.prix_unitaire_cts <= 0:
            return None
        tva_factor = 1 + (p.taux_tva or 2000) / 10000
        prix_ht_vente = p.prix_unitaire_cts / tva_factor
        return (prix_ht_vente - p.prix_achat_cts) / p.prix_achat_cts * 100

    marges_vendor = [m for p in items_vendor if (m := _marge_pct(p)) is not None]
    marges_all = [m for p in items_all if (m := _marge_pct(p)) is not None]

    marge_moy = round(sum(marges_vendor) / len(marges_vendor), 1) if marges_vendor else 0.0
    marge_cat = round(sum(marges_all) / len(marges_all), 1) if marges_all else 0.0

    return StockMargesResponse(
        marge_moy_pct=marge_moy,
        marge_catalogue_moy_pct=marge_cat,
        nb_articles=len(marges_vendor),
    )


async def get_alertes_prix(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
) -> AlertesPrixResponse:
    """Compare les 2 dernières factures ETL VALIDATED du fournisseur — détecte les hausses de prix."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    if not vendor.code:
        return AlertesPrixResponse(alertes=[], date_import_precedente=None, date_import_actuelle=None)

    result = await db.execute(
        select(EtlImport)
        .where(
            EtlImport.vendor_code == vendor.code,
            EtlImport.statut == "VALIDATED",
            EtlImport.lignes_data.isnot(None),
            EtlImport.date_facture.isnot(None),
            or_(EtlImport.target_tenant_id == tenant_id, EtlImport.target_tenant_id.is_(None)),
        )
        .order_by(EtlImport.date_facture.desc())
        .limit(2)
    )
    imports = list(result.scalars().all())

    if len(imports) < 2:
        date_actuelle = str(imports[0].date_facture) if imports else None
        return AlertesPrixResponse(alertes=[], date_import_precedente=None, date_import_actuelle=date_actuelle)

    imp_actuel, imp_precedent = imports[0], imports[1]

    def _prix_par_cle(lignes_data) -> dict[str, int]:
        prix: dict[str, int] = {}
        for ligne in (lignes_data or []):
            if not isinstance(ligne, dict):
                continue
            prix_val = ligne.get('prix_unitaire_cts')
            if not isinstance(prix_val, int) or prix_val <= 0:
                continue
            cle = ligne.get('ean') or ligne.get('designation') or ''
            if cle:
                prix[cle] = prix_val
        return prix

    prix_precedent = _prix_par_cle(imp_precedent.lignes_data)
    prix_actuel = _prix_par_cle(imp_actuel.lignes_data)

    alertes: list[AlertePrixItem] = []
    for ligne in (imp_actuel.lignes_data or []):
        if not isinstance(ligne, dict):
            continue
        prix_val = ligne.get('prix_unitaire_cts')
        if not isinstance(prix_val, int) or prix_val <= 0:
            continue
        cle = ligne.get('ean') or ligne.get('designation') or ''
        if not cle or cle not in prix_precedent:
            continue
        ancien = prix_precedent[cle]
        if prix_val > ancien:
            variation = round((prix_val - ancien) / ancien * 100, 1)
            if variation > 0:
                alertes.append(AlertePrixItem(
                    designation=ligne.get('designation') or cle,
                    ean=ligne.get('ean'),
                    prix_precedent_cts=ancien,
                    prix_actuel_cts=prix_val,
                    variation_pct=variation,
                ))

    alertes.sort(key=lambda a: a.variation_pct, reverse=True)

    return AlertesPrixResponse(
        alertes=alertes,
        date_import_precedente=str(imp_precedent.date_facture) if imp_precedent.date_facture else None,
        date_import_actuelle=str(imp_actuel.date_facture) if imp_actuel.date_facture else None,
    )


async def get_qualite(
    db: AsyncSession,
    tenant_id: int,
    vendor_id: int,
) -> QualiteResponse:
    """Signaux qualité : % livraisons à l'heure + % factures en retard."""
    vendor_repo = AsyncFinanceVendorRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)
    supply_repo = AsyncSupplyOrderRepository(db)

    vendor = await vendor_repo.get_by_id(vendor_id)
    if vendor is None:
        raise NotFound(f"Fournisseur {vendor_id} introuvable")

    nb_total_factures = await invoice_repo.count_all_by_vendor(vendor_id, tenant_id)
    nb_retard = await invoice_repo.count_retard_by_vendor(vendor_id, tenant_id)

    taux_retard: Optional[float] = None
    if nb_total_factures > 0:
        taux_retard = round(nb_retard / nb_total_factures * 100, 1)

    orders_livrees, _ = await supply_repo.list_paginated(
        tenant_id=tenant_id, vendor_id=vendor_id, statut="livree", per_page=100
    )

    nb_evaluees = 0
    nb_temps = 0
    for order in orders_livrees:
        if order.date_livraison_prevue and order.date_livraison_reelle:
            nb_evaluees += 1
            if order.date_livraison_reelle <= order.date_livraison_prevue:
                nb_temps += 1

    taux_livraison: Optional[float] = None
    if nb_evaluees >= 3:
        taux_livraison = round(nb_temps / nb_evaluees * 100, 1)

    return QualiteResponse(
        taux_livraison_temps_pct=taux_livraison,
        taux_factures_retard_pct=taux_retard,
        nb_commandes_evaluees=nb_evaluees,
        nb_factures_total=nb_total_factures,
    )


async def _count_articles_vendor(
    produit_repo: AsyncEpicerieProduitRepository,
    vendor_id: int,
    tenant_id: int,
) -> int:
    _, total = await produit_repo.list_paginated(
        tenant_id=tenant_id, vendor_id=vendor_id, per_page=1
    )
    return total


def _calcul_delai_moyen(invoices) -> float:
    """Calcule le délai moyen de paiement en jours."""
    delais = []
    for inv in invoices:
        if inv.date_facture and inv.date_echeance:
            delta = (inv.date_echeance - inv.date_facture).days
            delais.append(delta)
    if not delais:
        return 0.0
    return round(sum(delais) / len(delais), 1)


async def _distribution_categories(
    produit_repo: AsyncEpicerieProduitRepository,
    vendor_id: int,
    tenant_id: int,
) -> list[CategoryDistribution]:
    """F3 : distribution des articles par catégorie (list avec pct), triée par pct DESC."""
    items, total = await produit_repo.list_paginated(
        tenant_id=tenant_id, vendor_id=vendor_id, per_page=1000
    )
    if not items:
        return []

    dist: dict[str, int] = {}
    for produit in items:
        cat = produit.categorie or "Autres"
        dist[cat] = dist.get(cat, 0) + 1

    nb_total = sum(dist.values()) or 1
    return sorted(
        [
            CategoryDistribution(categorie_nom=cat, pct=round(count / nb_total * 100, 1))
            for cat, count in dist.items()
        ],
        key=lambda x: x.pct,
        reverse=True,
    )
