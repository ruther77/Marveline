"""Service Commandes fournisseurs épicerie — création, transitions, réception atomique.

Transitions statut autorisées :
  en_attente → confirmee | annulee
  confirmee  → expediee  | annulee
  expediee   → livree
  livree     → (immuable)
  annulee    → (immuable)

Invariant réception (livree) :
  1. MAJ received_quantity sur chaque ligne
  2. Incrémenter stock épicerie + créer mouvement ENTREE
  3. Calculer totaux réels (quantités reçues)
  4. Créer FinanceInvoice FOURNISSEUR
  5. statut=livree + date_livraison_reelle + invoice_id
"""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.repositories.epicerie.produit import AsyncEpicerieProduitRepository
from app.repositories.epicerie.stock import AsyncEpicerieStockRepository
from app.repositories.epicerie.supply_order import AsyncSupplyOrderRepository
from app.repositories.finance.invoice import AsyncFinanceInvoiceRepository
from app.schemas.epicerie.supply_order import (
    SupplyOrderCreate,
    ReceiveOrderRequest,
)

_TRANSITIONS_VALIDES = {
    "en_attente": {"confirmee", "annulee"},
    "confirmee": {"expediee", "annulee"},
    "expediee": {"livree"},
}


def _verif_transition(statut_actuel: str, statut_cible: str) -> None:
    autorisees = _TRANSITIONS_VALIDES.get(statut_actuel, set())
    if statut_cible not in autorisees:
        raise BadRequest(
            f"Transition {statut_actuel!r} → {statut_cible!r} interdite"
        )


def _calcul_totaux_lignes(lignes) -> tuple[int, int, int]:
    """Calcule (montant_ht, montant_tva, montant_ttc) en centimes."""
    total_ht = 0
    total_ttc = 0
    for ligne in lignes:
        qte = float(ligne.received_quantity or ligne.quantity)
        ht = round(ligne.prix_unitaire * qte)
        tva = round(ht * ligne.taux_tva / 10000)
        ttc = ht + tva
        total_ht += ht
        total_ttc += ttc
    total_tva = total_ttc - total_ht
    return total_ht, total_tva, total_ttc


async def creer_commande(
    db: AsyncSession,
    tenant_id: int,
    payload: SupplyOrderCreate,
) -> object:
    """Crée une commande fournisseur avec ses lignes."""
    order_repo = AsyncSupplyOrderRepository(db)

    order = await order_repo.create(
        tenant_id=tenant_id,
        vendor_id=payload.vendor_id,
        date_commande=payload.date_commande,
        reference=payload.reference,
        date_livraison_prevue=payload.date_livraison_prevue,
        notes=payload.notes,
    )

    for ligne in payload.lignes:
        await order_repo.create_line(
            order_id=order.id,
            designation=ligne.designation,
            quantity=ligne.quantity,
            prix_unitaire=ligne.prix_unitaire,
            taux_tva=ligne.taux_tva,
            produit_id=ligne.produit_id,
            notes=ligne.notes,
        )

    # Calcul des totaux initiaux (quantités commandées)
    lines = await order_repo.list_lines(order.id)
    ht, tva, ttc = _calcul_totaux_lignes(lines)
    await order_repo.update_totaux(order, ht, tva, ttc)

    return order


async def changer_statut(
    db: AsyncSession,
    tenant_id: int,
    order_id: int,
    statut_cible: str,
) -> object:
    """Effectue une transition de statut sur une commande."""
    order_repo = AsyncSupplyOrderRepository(db)

    order = await order_repo.get_by_id(order_id, tenant_id)
    if order is None:
        raise NotFound(f"Commande {order_id} introuvable")

    _verif_transition(order.statut, statut_cible)
    await order_repo.update_statut(order, statut_cible)
    return order


async def recevoir_commande(
    db: AsyncSession,
    tenant_id: int,
    order_id: int,
    payload: ReceiveOrderRequest,
    user_id: int,
) -> object:
    """Réception atomique : stock + mouvements + facture fournisseur."""
    order_repo = AsyncSupplyOrderRepository(db)
    stock_repo = AsyncEpicerieStockRepository(db)
    produit_repo = AsyncEpicerieProduitRepository(db)
    invoice_repo = AsyncFinanceInvoiceRepository(db)

    order = await order_repo.get_by_id(order_id, tenant_id)
    if order is None:
        raise NotFound(f"Commande {order_id} introuvable")
    if order.statut not in ("confirmee", "expediee", "en_attente"):
        raise BadRequest(f"Commande non réceptionnable au statut {order.statut!r}")

    lines = await order_repo.list_lines(order_id)
    lines_by_id = {line.id: line for line in lines}

    # --- MAJ quantités reçues + stock ---
    for item in payload.lignes:
        line = lines_by_id.get(item.line_id)
        if line is None:
            raise NotFound(f"Ligne {item.line_id} introuvable dans la commande")

        await order_repo.update_line_received(line, item.received_quantity)

        if line.produit_id is None or item.received_quantity <= 0:
            continue

        produit = await produit_repo.get_by_id(line.produit_id, tenant_id)
        if produit is None:
            continue

        stock = await stock_repo.get_or_create(line.produit_id, tenant_id)
        nouvelle_qte = float(stock.quantite) + item.received_quantity
        await stock_repo.update_quantite(stock, item.received_quantity)
        await stock_repo.create_movement(
            tenant_id=tenant_id,
            produit_id=line.produit_id,
            type="ENTREE",
            quantite=item.received_quantity,
            stock_apres=nouvelle_qte,
            supply_order_id=order_id,
            notes=item.notes,
            created_by_id=user_id,
        )

    # --- Calcul totaux réels ---
    lines_updated = await order_repo.list_lines(order_id)
    ht, tva, ttc = _calcul_totaux_lignes(lines_updated)
    await order_repo.update_totaux(order, ht, tva, ttc)

    # --- Facture fournisseur ---
    invoice = await invoice_repo.create(
        tenant_id=tenant_id,
        type="FOURNISSEUR",
        date_facture=payload.date_livraison_reelle,
        montant_ht=ht,
        montant_tva=tva,
        montant_ttc=ttc,
        vendor_id=order.vendor_id,
        supply_order_id=order_id,
        reference=order.reference,
    )

    # --- Passage à livree ---
    await order_repo.update_statut(
        order,
        statut="livree",
        invoice_id=invoice.id,
        date_livraison_reelle=payload.date_livraison_reelle,
    )

    return order
