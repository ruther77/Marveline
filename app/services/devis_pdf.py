"""Service de génération PDF des devis — WeasyPrint + HTML inline."""
from datetime import date
from app.models.devis import Devis


def _cents_to_eur(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", "\u202f").replace(".", ",")


def _fmt_date(d: date | None) -> str:
    if d is None:
        return "—"
    return d.strftime("%d/%m/%Y")


def generate_devis_pdf(devis: Devis) -> bytes:
    """Génère le PDF d'un devis et retourne les bytes.

    Args:
        devis: Instance Devis avec relations chargées (customer, lines)

    Returns:
        Contenu PDF en bytes
    """
    from weasyprint import HTML

    customer = devis.customer
    customer_name = ""
    if customer:
        customer_name = f"{customer.first_name} {customer.last_name}".strip()

    lines_html = ""
    for line in devis.lines:
        lines_html += f"""
        <tr>
            <td>{line.label}</td>
            <td style="text-align:center">{line.quantity}</td>
            <td style="text-align:right">{_cents_to_eur(line.unit_price_cents)}</td>
            <td style="text-align:right">{"—" if not line.discount_pct else f"{line.discount_pct / 100:.0f}%"}</td>
            <td style="text-align:right">{_cents_to_eur(line.subtotal_cents)}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 12px; color: #222; margin: 0; padding: 40px; }}
  h1 {{ font-size: 22px; color: #1a1a2e; }}
  .header {{ display: flex; justify-content: space-between; margin-bottom: 30px; }}
  .meta {{ font-size: 11px; color: #555; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
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
    <h1>DEVIS {devis.reference}</h1>
    <div class="meta">
      Statut : {devis.status.upper()}<br>
      Valable jusqu'au : {_fmt_date(devis.valid_until)}<br>
      Date événement : {_fmt_date(devis.event_date)}<br>
      Lieu : {devis.event_location or "—"}
    </div>
  </div>
  <div class="meta" style="text-align:right">
    <strong>Client</strong><br>
    {customer_name}<br>
    {getattr(customer, "email", "") or ""}
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Désignation</th>
      <th style="text-align:center">Qté</th>
      <th style="text-align:right">Prix unitaire</th>
      <th style="text-align:right">Remise</th>
      <th style="text-align:right">Sous-total</th>
    </tr>
  </thead>
  <tbody>
    {lines_html}
  </tbody>
</table>

<div class="totals">
  <table>
    <tr><td>Sous-total HT</td><td style="text-align:right">{_cents_to_eur(devis.subtotal_cents)}</td></tr>
    <tr><td>TVA ({devis.tva_rate / 100:.0f}%)</td><td style="text-align:right">{_cents_to_eur(devis.tva_cents)}</td></tr>
    <tr class="total-row"><td>Total TTC</td><td style="text-align:right">{_cents_to_eur(devis.total_cents)}</td></tr>
    {"<tr><td>Caution</td><td style='text-align:right'>" + _cents_to_eur(devis.caution_amount_cents) + "</td></tr>" if devis.caution_required else ""}
  </table>
</div>

{"<p style='margin-top:20px;font-size:11px;color:#555'>Notes : " + devis.notes + "</p>" if devis.notes else ""}

<div class="footer">
  Ce document est un devis — il n'a pas valeur de facture.
</div>
</body>
</html>"""

    return HTML(string=html).write_pdf()
