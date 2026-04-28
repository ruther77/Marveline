"""Service de génération PDF des factures — WeasyPrint + Jinja2."""
import os
from datetime import date, timedelta
from typing import Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models.invoice import Invoice
from app.constants.business import (
    BALANCE_DUE_DAYS_BEFORE_EVENT,
    TVA_RATE,
)


_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

_DEFAULT_BRAND = {
    "name": "Marveline",
    "legal_name": "Marveline SAS",
    "email": "contact@marveline.fr",
    "phone": "",
    "address": "",
    "frontend_url": "",  # None = caller fallback to settings.FRONTEND_URL
    "mfa_issuer_name": "Marveline",
}

_STATUS_LABELS = {
    "draft": "Brouillon",
    "sent": "Envoyée",
    "paid": "Payée",
    "overdue": "En retard",
    "cancelled": "Annulée",
}


def _cents_to_eur(cents: int) -> str:
    """Formate des centimes en euros (ex: 12345 → '123,45 €')."""
    return f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def _format_date(d: date) -> str:
    """Formate une date en français (ex: '15/06/2026')."""
    return d.strftime("%d/%m/%Y")


def generate_invoice_pdf(invoice: Invoice, brand: dict[str, Any] | None = None) -> bytes:
    """Génère le PDF d'une facture et retourne les bytes.

    Args:
        invoice: Instance Invoice avec relations chargées
                 (invoice.reservation, reservation.customer, reservation.lines)
        brand: dict {name, legal_name, email, phone, address} — identité marque du tenant.
               Fallback Marveline si absent.

    Returns:
        Contenu PDF en bytes
    """
    from weasyprint import HTML

    brand_ctx = {**_DEFAULT_BRAND, **(brand or {})}

    reservation = invoice.reservation
    if reservation is None:
        raise ValueError(
            f"Facture {invoice.id} n'est pas liée à une réservation — PDF impossible"
        )
    customer = reservation.customer
    if customer is None:
        raise ValueError(
            f"Réservation {reservation.id} n'a pas de client associé — PDF impossible"
        )

    # Montants HT/TVA/TTC — utiliser les champs stockés (évite recalcul inverse)
    total_ht = invoice.total_amount_cents
    tva = invoice.tva_amount_cents if invoice.tva_amount_cents is not None else int(total_ht * TVA_RATE)
    total_ttc = invoice.total_ttc_cents if invoice.total_ttc_cents is not None else total_ht + tva

    # Calculs acompte / solde — advance_rate capture sur la facture a la creation
    advance_rate = invoice.advance_rate if invoice.advance_rate else 0.40
    advance = round(total_ttc * advance_rate)
    balance = total_ttc - advance
    balance_due_date = reservation.event_date - timedelta(days=BALANCE_DUE_DAYS_BEFORE_EVENT)

    # Lignes de réservation
    lines = []
    for line in reservation.lines:
        lines.append({
            "product_name": line.product.name if line.product else f"Produit #{line.product_id}",
            "product_sku": line.product.sku if line.product else "",
            "quantity": line.quantity,
            "unit_price_eur": _cents_to_eur(line.unit_price_cents),
            "subtotal_eur": _cents_to_eur(line.subtotal_cents),
        })

    # Nom client
    if customer.first_name:
        customer_name = f"{customer.first_name} {customer.last_name}"
    else:
        customer_name = customer.company_name or "Client"

    # Tableau TVA multi-taux pour le template (si breakdown présent)
    tva_rows = []
    if invoice.tva_breakdown:
        for item in invoice.tva_breakdown:
            tva_rows.append({
                "rate_label": f"{item['rate'] * 100:.1f} %",
                "base_ht_eur": _cents_to_eur(item["base_ht_cents"]),
                "tva_eur": _cents_to_eur(item["tva_cents"]),
                "ttc_eur": _cents_to_eur(item["ttc_cents"]),
            })

    context = {
        "invoice_number": invoice.invoice_number,
        "issue_date": _format_date(invoice.issue_date),
        "due_date": _format_date(invoice.due_date),
        "status": invoice.status,
        "status_label": _STATUS_LABELS.get(invoice.status, invoice.status),
        # Client
        "customer_name": customer_name,
        "customer_address": customer.address or "",
        "customer_city": customer.city or "",
        "customer_postal_code": customer.postal_code or "",
        "customer_email": customer.email or "",
        "customer_phone": customer.phone or "",
        # Réservation
        "reservation_reference": reservation.reference,
        "event_date": _format_date(reservation.event_date),
        "event_location": reservation.event_location or "",
        # Lignes
        "lines": lines,
        # Montants
        "total_ht_eur": _cents_to_eur(total_ht),
        "tva_eur": _cents_to_eur(tva),
        "total_ttc_eur": _cents_to_eur(total_ttc),
        "advance_amount_eur": _cents_to_eur(advance),
        "balance_amount_eur": _cents_to_eur(balance),
        "balance_due_date": _format_date(balance_due_date),
        "paid_amount_cents": invoice.paid_amount_cents,
        "paid_amount_eur": _cents_to_eur(invoice.paid_amount_cents),
        "remaining_amount_eur": _cents_to_eur(invoice.remaining_amount_cents),
        "deposit_amount_eur": _cents_to_eur(reservation.deposit_amount_cents),
        # TVA multi-taux
        "tva_rows": tva_rows,
        "tva_rate_label": f"{(invoice.tva_rate or TVA_RATE) * 100:.1f} %",
        # Identite marque (tenant-dependante)
        "brand": brand_ctx,
    }

    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("invoices/invoice.html")
    html_content = template.render(**context)

    pdf_bytes: bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes


def _build_brand_dict(ts) -> dict[str, Any]:
    """Construit un dict brand a partir d'une row TenantSettings. Helper partage."""
    if ts is None:
        return _DEFAULT_BRAND.copy()
    legal = ts.company_name or _DEFAULT_BRAND["legal_name"]
    display = legal.replace(" SAS", "").replace(" SARL", "").strip() or legal
    return {
        "name": display,
        "legal_name": legal,
        "email": ts.company_email or _DEFAULT_BRAND["email"],
        "phone": ts.company_phone or "",
        "address": ts.company_address or "",
        "frontend_url": ts.frontend_url or "",
        "mfa_issuer_name": ts.mfa_issuer_name or display,
    }


async def load_brand_for_tenant(db, tenant_id: int) -> dict[str, Any]:
    """Charge l'identite marque d'un tenant depuis tenant_settings (async).

    Retourne dict {name, legal_name, email, phone, address, frontend_url, mfa_issuer_name}
    — fallback Marveline si settings absents ou champs vides.
    """
    from sqlalchemy import select as _select
    from app.models.tenant_settings import TenantSettings

    result = await db.execute(
        _select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
    )
    return _build_brand_dict(result.scalar_one_or_none())


def load_brand_for_tenant_sync(db, tenant_id: int) -> dict[str, Any]:
    """Variante sync pour services Celery / scripts."""
    from app.models.tenant_settings import TenantSettings

    ts = (
        db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
    )
    return _build_brand_dict(ts)
