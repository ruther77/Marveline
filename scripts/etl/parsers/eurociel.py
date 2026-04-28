"""Parser fournisseur EUROCIEL — factures PDF multi-factures (ADR-08).

Format source : PDF Sage contenant N factures concaténées (1 à 2 pages chacune).

Structure header facture :
    N° de Facture Date
    FA20248483 09/11/23

Structure ligne produit :
    <idx> <DESIGNATION> <Qté> <Poids> <PU_HT> <Montant_HT> <Code_TVA>
    Exemple : 1 CREVETTE ROSE DECORTIQUE (25X320) - 10Kg/Brut 1,000 10 109,9500 109,95 C2

Codes TVA : C2 = 5,5% | C1 = 20% | C0 = exonéré

Contrat public (identique METRO/TAIYAT) :
  - parse(fichier) → list[LigneParsee]
  - parse_facture(fichier) → tuple[list[LigneParsee], FactureMetadata]
  - parse_with_facture_metrics(fichier) → tuple[list[LigneParsee], dict]

Un PDF = potentiellement N factures. Les fonctions acceptent `invoice_number`
pour sélectionner une facture précise. list_invoices() retourne la liste.

Routing multi-tenant : INCONTOURNABLE → tenant 3 (resto), NOUTAM → tenant 2.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Optional

from app.etl_types import FactureMetadata, LigneParsee

logger = logging.getLogger(__name__)

_SOURCE_FOURNISSEUR = "EUROCIEL"

_CLIENT_TO_TENANT: dict[str, int] = {
    "INCONTOURNABLE": 3,
    "NOUTAM": 2,
}

_TVA_CODES: dict[str, float] = {
    "C0": 0.0,
    "C1": 20.0,
    "C2": 5.5,
    "C3": 10.0,
}

_RE_FACTURE_NUMERO = re.compile(r"\b(FA\d{7,10})\b")
_RE_DATE = re.compile(r"\b(\d{2}/\d{2}/\d{2})\b")
_RE_DATE_LONG = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

# Ligne produit : idx DESIGNATION qte poids pu montant_ht code_tva
# Les nombres français : virgule décimale, espaces milliers
_RE_PRODUCT_LINE = re.compile(
    r"^(?P<idx>\d+)\s+"
    r"(?P<designation>.+?)\s+"
    r"(?P<qte>-?\d+(?:[.,]\d+)?)\s+"
    r"(?P<poids>-?\d+(?:[.,]\d+)?)\s+"
    r"(?P<pu>-?\d+[.,]\d+)\s+"
    r"(?P<montant_ht>-?\d+[.,]\d+)\s+"
    r"(?P<tva_code>C\s*\*?\s*\d)\s*\*?\s*\d?\s*$"
)

# Ligne récap TVA : "C2 109,95 5,5% 6,05 109,95 116,00 0,00 116,00"
# Format récap : "C2 <base> <taux>% <taxe> [tot_ht] [port] <tot_ttc> [acompte] [net]"
# Le nombre de colonnes varie (port absent, acompte absent). On extrait robustement :
# code + base + taux% + taxe, puis on prend le DERNIER nombre comme NET (= TTC final).
_RE_TOTAL_TVA = re.compile(
    r"^(?P<code>C\s*\*?\s*\d)\s+"
    r"(?P<base>\d+[.,]\d+)\s+"
    r"(?P<taux>\d+[.,]\d+)%\s+"
    r"(?P<taxe>\d+[.,]\d+)\s+"
    r"(?P<rest>.+)$"
)

_RE_CLIENT_INCONTOURNABLE = re.compile(r"INCONTOURNABLE", re.IGNORECASE)
_RE_CLIENT_NOUTAM = re.compile(r"NOUTAM", re.IGNORECASE)


@dataclass
class _InvoiceBlock:
    numero: str
    date: Optional[date_cls] = None
    client: Optional[str] = None
    pages: list[str] = field(default_factory=list)
    lignes: list[LigneParsee] = field(default_factory=list)
    totaux_by_tva: dict[str, dict] = field(default_factory=dict)  # {C2: {base, taxe, ttc}}


def _parse_fr_number(raw: str) -> Optional[float]:
    if not raw:
        return None
    s = raw.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: str) -> Optional[date_cls]:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _detect_client(full_text: str) -> Optional[str]:
    """INCONTOURNABLE prioritaire sur NOUTAM si les deux présents (code client)."""
    up = full_text.upper()
    if "CLINCONTOURNABLE" in up or _RE_CLIENT_INCONTOURNABLE.search(up):
        return "INCONTOURNABLE"
    if "CNOUTAM" in up or _RE_CLIENT_NOUTAM.search(up):
        return "NOUTAM"
    return None


def _parse_product_line(line: str, default_tva_centieme: int = 550) -> Optional[LigneParsee]:
    match = _RE_PRODUCT_LINE.match(line.strip())
    if not match:
        return None

    designation = match.group("designation").strip()
    if len(designation) < 3:
        return None

    qte = _parse_fr_number(match.group("qte"))
    pu = _parse_fr_number(match.group("pu"))
    montant_ht = _parse_fr_number(match.group("montant_ht"))
    tva_code_raw = match.group("tva_code").strip()
    # Extraire uniquement "C2" en évitant les suffixes "C * 2" ou "C2 *"
    tva_code = re.match(r"C\d", tva_code_raw.replace(" ", "").replace("*", ""))
    tva_code = tva_code.group(0) if tva_code else "C2"
    taux_tva = _TVA_CODES.get(tva_code, 5.5)

    if qte is None or montant_ht is None:
        return None

    prix_ht_cts = round(pu * 100) if pu is not None else None
    montant_ht_cts = round(montant_ht * 100)
    taux_tva_centieme = round(taux_tva * 100)
    montant_ttc_cts = round(montant_ht_cts * (1 + taux_tva / 100))
    prix_ttc_cts = round(prix_ht_cts * (1 + taux_tva / 100)) if prix_ht_cts else None

    return LigneParsee(
        designation=designation,
        unite_base="U",
        source_fournisseur=_SOURCE_FOURNISSEUR,
        ean=None,
        quantite=qte,
        prix_unitaire_cts=prix_ttc_cts,
        montant_ht_cts=montant_ht_cts,
        montant_ttc_cts=montant_ttc_cts,
        taux_tva_centieme=taux_tva_centieme,
        designation_raw=designation,
    )


def _extract_invoices(fichier: str) -> dict[str, _InvoiceBlock]:
    """Parse un PDF multi-factures → {numero: _InvoiceBlock}.

    Stratégie : on itère page par page. La première occurrence de FA\d+ sur une
    page l'associe à cette facture. Si la page n'en contient pas, elle est
    rattachée à la dernière facture ouverte (cas multi-page).
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("pdfplumber requis pour parser EUROCIEL") from exc

    path = Path(fichier)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {fichier}")

    invoices: dict[str, _InvoiceBlock] = {}
    current: Optional[_InvoiceBlock] = None

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text:
                continue

            fa_match = _RE_FACTURE_NUMERO.search(text)
            if fa_match:
                numero = fa_match.group(1)
                if numero not in invoices:
                    invoices[numero] = _InvoiceBlock(numero=numero)
                current = invoices[numero]
                # Date (dd/mm/yy ou dd/mm/yyyy sur la ligne juste après FA)
                lines = text.splitlines()
                for i, ln in enumerate(lines):
                    if numero in ln:
                        # Chercher la date sur la même ligne ou l'adjacente
                        for candidate in lines[max(0, i-1):min(len(lines), i+2)]:
                            m = _RE_DATE.search(candidate) or _RE_DATE_LONG.search(candidate)
                            if m:
                                # Préférer YYYY (4 chiffres)
                                long_m = _RE_DATE_LONG.search(candidate)
                                current.date = _parse_date(
                                    long_m.group(1) if long_m else m.group(1)
                                )
                                break
                        break

            if current is None:
                continue
            current.pages.append(text)

            # Détecter client (première occurrence suffit)
            if current.client is None:
                current.client = _detect_client(text)

            # Parse lignes produits
            for raw_line in text.splitlines():
                ligne = _parse_product_line(raw_line)
                if ligne is not None:
                    current.lignes.append(ligne)

            # Parse récap TVA
            for raw_line in text.splitlines():
                m = _RE_TOTAL_TVA.match(raw_line.strip())
                if m:
                    code = m.group("code").replace(" ", "").replace("*", "")
                    base = _parse_fr_number(m.group("base"))
                    taxe = _parse_fr_number(m.group("taxe"))
                    # Dernier nombre du groupe "rest" = NET (=TTC)
                    rest_nums = re.findall(r"\d+[.,]\d+", m.group("rest"))
                    if not rest_nums or base is None or taxe is None:
                        continue
                    net = _parse_fr_number(rest_nums[-1])
                    current.totaux_by_tva[code] = {
                        "base_cts": round(base * 100),
                        "taxe_cts": round(taxe * 100),
                        "ttc_cts": round(net * 100) if net is not None else round((base + taxe) * 100),
                    }
    return invoices


def list_invoices(fichier: str) -> list[str]:
    """Liste les numéros de facture présents dans un PDF EUROCIEL."""
    return sorted(_extract_invoices(fichier).keys())


def parse_with_facture_metrics(
    fichier: str, invoice_number: Optional[str] = None,
) -> tuple[list[LigneParsee], dict]:
    """Parse EUROCIEL et renvoie lignes + métriques pour UNE facture."""
    blocks = _extract_invoices(fichier)
    if not blocks:
        return [], {"file": str(fichier), "error": "no_invoices"}

    if invoice_number is None:
        invoice_number = next(iter(blocks))
    elif invoice_number not in blocks:
        raise ValueError(
            f"Facture {invoice_number!r} introuvable. Disponibles : {list(blocks)[:5]}..."
        )

    block = blocks[invoice_number]

    # Agrégation montants attendus via récap TVA
    declared_ht_cts = sum(t.get("base_cts", 0) for t in block.totaux_by_tva.values())
    declared_tva_cts = sum(t.get("taxe_cts", 0) for t in block.totaux_by_tva.values())
    declared_ttc_cts = sum(t.get("ttc_cts", 0) for t in block.totaux_by_tva.values())

    computed_ht_cts = sum(l.montant_ht_cts or 0 for l in block.lignes)
    ecart_ht = (declared_ht_cts - computed_ht_cts) / 100.0

    line_outliers = []
    for l in block.lignes:
        if l.quantite is None or l.prix_unitaire_cts is None:
            continue
        # Note : prix_unitaire_cts est TTC dans ce parser
        expected_ttc = round(l.quantite * l.prix_unitaire_cts)
        delta = abs(expected_ttc - (l.montant_ttc_cts or 0))
        if delta > 20:  # tolérance 20 centimes (arrondi TVA)
            line_outliers.append({
                "designation": l.designation, "expected_cts": expected_ttc,
                "actual_cts": l.montant_ttc_cts, "delta_cts": delta,
            })

    is_coherent = abs(ecart_ht) <= 0.05 and declared_ttc_cts > 0

    quality = 0
    if block.numero:
        quality += 20
    if block.date:
        quality += 20
    if declared_ttc_cts:
        quality += 20
    if block.lignes:
        quality += 20 * (1 - len(line_outliers) / max(len(block.lignes), 1))
    if is_coherent:
        quality += 20

    metrics = {
        "file": str(fichier),
        "invoice_number": block.numero,
        "invoice_date": block.date.isoformat() if block.date else None,
        "client_name": block.client,
        "line_count_output": len(block.lignes),
        "line_count_rejected": 0,
        "line_coherence_outlier_count": len(line_outliers),
        "line_coherence_outliers": line_outliers,
        "total_ht_declared_cts": declared_ht_cts,
        "total_tva_declared_cts": declared_tva_cts,
        "total_ttc_declared": declared_ttc_cts / 100.0 if declared_ttc_cts else None,
        "total_ttc_computed": sum(l.montant_ttc_cts or 0 for l in block.lignes) / 100.0,
        "ecart_ttc": ecart_ht,
        "ecart_ttc_abs": abs(ecart_ht),
        "is_total_coherent": is_coherent,
        "totaux_by_tva": block.totaux_by_tva,
        "quality_score": round(quality, 2),
    }
    return block.lignes, metrics


def parse_facture(
    fichier: str, invoice_number: Optional[str] = None,
) -> tuple[list[LigneParsee], FactureMetadata]:
    lignes, metrics = parse_with_facture_metrics(fichier, invoice_number)

    client_name = metrics.get("client_name")
    target_tenant_id = _CLIENT_TO_TENANT.get(client_name) if client_name else None

    date_iso = metrics.get("invoice_date")
    date_obj = None
    if date_iso:
        try:
            date_obj = date_cls.fromisoformat(date_iso)
        except (ValueError, TypeError):
            pass

    metadata = FactureMetadata(
        vendor_code=_SOURCE_FOURNISSEUR,
        numero_facture=metrics.get("invoice_number"),
        date_facture=date_obj,
        montant_ht_total=metrics.get("total_ht_declared_cts"),
        montant_tva_total=metrics.get("total_tva_declared_cts"),
        montant_ttc_total=(round(metrics["total_ttc_declared"] * 100)
                            if metrics.get("total_ttc_declared") else None),
        quality_score=min(round(metrics.get("quality_score", 0)), 100),
        ecart_reconciliation=metrics.get("ecart_ttc"),
        lignes_brutes=len(lignes),
        client_name=client_name,
        target_tenant_id=target_tenant_id,
    )
    return lignes, metadata


def parse(fichier: str, invoice_number: Optional[str] = None) -> list[LigneParsee]:
    lignes, _ = parse_with_facture_metrics(fichier, invoice_number)
    return lignes


__all__ = [
    "parse", "parse_facture", "parse_with_facture_metrics",
    "list_invoices",
]
