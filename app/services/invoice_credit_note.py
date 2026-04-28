"""Service métier pour les avoirs (credit notes) sur factures."""
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequest, NotFound
from app.models.invoice import Invoice
from app.models.invoice_credit_note import InvoiceCreditNote
from app.repositories.invoice import AsyncInvoiceRepository
from app.repositories.invoice_credit_note import AsyncCreditNoteRepository
from app.schemas.invoice import CreditNoteCreate


async def _get_invoice_or_404(db: AsyncSession, tenant_id: int, invoice_id: int) -> Invoice:
    repo = AsyncInvoiceRepository(db)
    invoice = await repo.get_by_id(invoice_id, tenant_id)
    if not invoice:
        raise NotFound(f"Facture {invoice_id} introuvable")
    return invoice


async def create_credit_note(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    data: CreditNoteCreate,
) -> InvoiceCreditNote:
    """Crée un avoir sur une facture.

    Règle métier : avoir ≤ montant total de la facture originale.
    """
    invoice = await _get_invoice_or_404(db, tenant_id, invoice_id)

    cn_repo = AsyncCreditNoteRepository(db)
    already_credited = await cn_repo.total_credited(invoice_id, tenant_id)
    remaining_creditable = invoice.total_amount_cents - already_credited

    if data.amount_cents > remaining_creditable:
        raise BadRequest(
            f"Montant avoir ({data.amount_cents} c.) dépasse le solde créditable "
            f"({remaining_creditable} c.)"
        )

    cn = await cn_repo.create(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        amount_cents=data.amount_cents,
        reason=data.reason,
        issue_date=data.issue_date,
    )
    await db.commit()
    await db.refresh(cn)
    return cn


async def list_credit_notes(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
) -> list[InvoiceCreditNote]:
    """Retourne les avoirs d'une facture."""
    await _get_invoice_or_404(db, tenant_id, invoice_id)
    repo = AsyncCreditNoteRepository(db)
    return await repo.get_by_invoice(invoice_id, tenant_id)


async def issue_credit_note(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    cn_id: int,
) -> InvoiceCreditNote:
    """Émet un avoir (draft → issued)."""
    await _get_invoice_or_404(db, tenant_id, invoice_id)
    repo = AsyncCreditNoteRepository(db)
    cn = await repo.get_by_id(cn_id, tenant_id)
    if not cn:
        raise NotFound(f"Avoir {cn_id} introuvable")
    if cn.original_invoice_id != invoice_id:
        raise BadRequest("Cet avoir n'appartient pas à cette facture")
    if cn.status != "draft":
        raise BadRequest(f"Impossible d'émettre un avoir au statut '{cn.status}'")
    cn = await repo.update_status(cn_id, tenant_id, "issued")
    await db.commit()
    await db.refresh(cn)
    return cn


async def apply_credit_note(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    cn_id: int,
) -> InvoiceCreditNote:
    """Impute un avoir sur la prochaine facture (issued → applied)."""
    await _get_invoice_or_404(db, tenant_id, invoice_id)
    repo = AsyncCreditNoteRepository(db)
    cn = await repo.get_by_id(cn_id, tenant_id)
    if not cn:
        raise NotFound(f"Avoir {cn_id} introuvable")
    if cn.original_invoice_id != invoice_id:
        raise BadRequest("Cet avoir n'appartient pas à cette facture")
    if cn.status != "issued":
        raise BadRequest(f"Impossible d'imputer un avoir au statut '{cn.status}'")
    cn = await repo.update_status(cn_id, tenant_id, "applied")
    await db.commit()
    await db.refresh(cn)
    return cn


async def refund_credit_note(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    cn_id: int,
) -> InvoiceCreditNote:
    """Rembourse un avoir (issued → refunded)."""
    await _get_invoice_or_404(db, tenant_id, invoice_id)
    repo = AsyncCreditNoteRepository(db)
    cn = await repo.get_by_id(cn_id, tenant_id)
    if not cn:
        raise NotFound(f"Avoir {cn_id} introuvable")
    if cn.original_invoice_id != invoice_id:
        raise BadRequest("Cet avoir n'appartient pas à cette facture")
    if cn.status != "issued":
        raise BadRequest(f"Impossible de rembourser un avoir au statut '{cn.status}'")
    cn = await repo.update_status(cn_id, tenant_id, "refunded")
    await db.commit()
    await db.refresh(cn)
    return cn


async def mark_invoice_sent(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    sent_date: date | None = None,
    notes: str | None = None,
) -> Invoice:
    """Marque une facture comme envoyée manuellement."""
    repo = AsyncInvoiceRepository(db)
    invoice = await _get_invoice_or_404(db, tenant_id, invoice_id)
    if invoice.status not in ("draft", "sent"):
        raise BadRequest(f"Statut {invoice.status} incompatible avec mark-sent")
    invoice.status = "sent"
    if invoice.sent_at is None:
        invoice.sent_at = datetime.now()
    if notes and hasattr(invoice, "notes"):
        invoice.notes = notes
    await db.commit()
    hydrated = await repo.get_by_id_with_relations(invoice_id, tenant_id)
    return hydrated or invoice


async def remind_invoice(
    db: AsyncSession,
    tenant_id: int,
    invoice_id: int,
    notes: str | None = None,
) -> Invoice:
    """Enregistre une relance sur la facture (sans envoi email réel en V1)."""
    repo = AsyncInvoiceRepository(db)
    invoice = await _get_invoice_or_404(db, tenant_id, invoice_id)
    if invoice.status not in ("sent", "overdue"):
        raise BadRequest(f"Impossible de relancer une facture au statut {invoice.status}")
    now = datetime.now()
    if invoice.first_reminder_sent_at is None:
        invoice.first_reminder_sent_at = now
    invoice.last_reminder_sent_at = now
    await db.commit()
    hydrated = await repo.get_by_id_with_relations(invoice_id, tenant_id)
    return hydrated or invoice


async def create_damage_invoice(
    db: AsyncSession,
    tenant_id: int,
    reservation_id: int,
    charges: list[dict],
    notes: str | None = None,
) -> Invoice:
    """Crée une facture de dommages liée à une réservation."""
    from app.repositories.reservation import AsyncReservationRepository
    res_repo = AsyncReservationRepository(db)
    reservation = await res_repo.get_by_id(reservation_id, tenant_id)
    if not reservation:
        raise NotFound(f"Réservation {reservation_id} introuvable")

    from app.services.invoice import AsyncInvoiceService
    inv_svc = AsyncInvoiceService(db)

    # Calcul totaux (DAMAGE seulement — amount_cents direct)
    subtotal = sum(c["amount_cents"] for c in charges if c.get("amount_cents"))
    tva = int(subtotal * 0.20)
    total = subtotal + tva

    # Génération numéro facture via le service (logique centralisée)
    number = await inv_svc.generate_invoice_number(tenant_id)

    invoice = Invoice(
        tenant_id=tenant_id,
        invoice_number=number,
        reservation_id=reservation_id,
        status="draft",
        issue_date=date.today(),
        due_date=date.today(),
        total_amount_cents=total,
        paid_amount_cents=0,
    )
    db.add(invoice)
    await db.flush()

    from app.models.invoice_charge import InvoiceCharge
    for c in charges:
        charge = InvoiceCharge(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            charge_type=c.get("charge_type", "DAMAGE"),
            description=c["description"],
            amount_cents=c.get("amount_cents"),
            hours=c.get("hours"),
            day_type=c.get("day_type"),
            damage_type_id=c.get("damage_type_id"),
        )
        db.add(charge)
    await db.flush()

    await db.commit()
    repo = AsyncInvoiceRepository(db)
    hydrated = await repo.get_by_id_with_relations(invoice.id, tenant_id)
    return hydrated or invoice
