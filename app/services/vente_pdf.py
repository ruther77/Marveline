"""Service de génération PDF des ventes — WeasyPrint + HTML inline."""
from datetime import date
from app.models.vente import Vente


def _cents_to_eur(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", "\u202f").replace(".", ",")


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    return d.strftime("%d/%m/%Y")


def generate_vente_pdf(vente: Vente) -> bytes:
    """Génère le PDF d'une vente et retourne les bytes.

    Args:
        vente: Instance Vente avec relations chargées (customer, lines, payments)

    Returns:
        Contenu PDF en bytes
    """
    from weasyprint import HTML

    customer = vente.customer
    customer_name = ""
    if customer:
        customer_name = f"{customer.first_name} {customer.last_name}".strip()

    lines_html = ""
    for line in vente.lines:
        unit_price = getattr(line, "unit_price_cents", 0) or 0
        qty = getattr(line, "quantity", 1) or 1
        subtotal = getattr(line, "subtotal_cents", unit_price * qty) or (unit_price * qty)
        label = getattr(line, "label", "") or f"Article #{getattr(line, 'product_id', '?')}"
        lines_html += f"""
        <tr>
            <td>{label}</td>
            <td style="text-align:center">{qty}</td>
            <td style="text-align:right">{_cents_to_eur(unit_price)}</td>
            <td style="text-align:right">{_cents_to_eur(subtotal)}</td>
        </tr>"""

    payments_html = ""
    for p in vente.payments:
        payments_html += f"""
        <tr>
            <td>{_fmt_date(getattr(p, "payment_date", None))}</td>
            <td>{getattr(p, "payment_method", "").replace("_", " ").title()}</td>
            <td style="text-align:right">{_cents_to_eur(getattr(p, "amount_cents", 0) or 0)}</td>
        </tr>"""

    status_labels = {
        "draft": "Brouillon",
        "pending": "En attente",
        "deposit_paid": "Acompte réglé",
        "fully_paid": "Soldée",
        "overdue": "En retard",
        "refunded": "Remboursée",
        "cancelled": "Annulée",
    }

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 12px; color: #222; margin: 0; padding: 40px; }}
  h1 {{ font-size: 22px; color: #1a1a2e; }}
  h2 {{ font-size: 14px; color: #1a1a2e; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }}
  .header {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
  .meta {{ font-size: 11px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
  th {{ background: #1a1a2e; color: #fff; padding: 8px 10px; text-align: left; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #eee; }}
  .totals {{ margin-top: 20px; text-align: right; }}
  .totals table {{ width: 280px; margin-left: auto; }}
  .totals td {{ border: none; }}
  .total-row td {{ font-weight: bold; font-size: 14px; border-top: 2px solid #1a1a2e; }}
  .footer {{ margin-top: 40px; font-size: 10px; color: #888; border-top: 1px solid #ddd; padding-top: 10px; }}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>VENTE {vente.reference}</h1>
    <div class="meta">
      Statut : {status_labels.get(vente.status, vente.status).upper()}<br>
      Échéance paiement : {_fmt_date(vente.payment_due_date)}
    </div>
  </div>
  <div class="meta" style="text-align:right">
    <strong>Client</strong><br>
    {customer_name}<br>
    {getattr(customer, "email", "") or ""}
  </div>
</div>

<h2>Articles</h2>
<table>
  <thead>
    <tr>
      <th>Désignation</th>
      <th style="text-align:center">Qté</th>
      <th style="text-align:right">Prix unitaire</th>
      <th style="text-align:right">Sous-total</th>
    </tr>
  </thead>
  <tbody>
    {lines_html}
  </tbody>
</table>

<div class="totals">
  <table>
    <tr><td>Sous-total HT</td><td style="text-align:right">{_cents_to_eur(vente.subtotal_cents)}</td></tr>
    <tr><td>TVA</td><td style="text-align:right">{_cents_to_eur(vente.tva_cents)}</td></tr>
    <tr class="total-row"><td>Total TTC</td><td style="text-align:right">{_cents_to_eur(vente.total_cents)}</td></tr>
    <tr><td>Montant réglé</td><td style="text-align:right">{_cents_to_eur(vente.paid_cents)}</td></tr>
    <tr><td>Solde restant</td><td style="text-align:right">{_cents_to_eur(vente.total_cents - vente.paid_cents)}</td></tr>
  </table>
</div>

{"<h2>Historique des paiements</h2><table><thead><tr><th>Date</th><th>Mode</th><th style='text-align:right'>Montant</th></tr></thead><tbody>" + payments_html + "</tbody></table>" if payments_html else ""}

{"<p style='margin-top:20px;font-size:11px;color:#555'>Notes : " + vente.notes + "</p>" if vente.notes else ""}

<div class="footer">
  Document généré automatiquement — Marveline
</div>
</body>
</html>"""

    return HTML(string=html).write_pdf()
