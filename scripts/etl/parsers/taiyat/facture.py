"""Logique facture TAIYAT — header, totaux, réconciliation par taux TVA.

Repris de taiyat_legacy.py (éprouvé sur 193 PDFs, cohérence 100%) :
  - Extraction en-tête (numéro facture, date, client, code client)
  - Extraction total TTC déclaré (scoring NET À PAYER / HT)
  - Récapitulatif TVA par taux (reconciliation subset)
  - Override zero-remise (ligne 100% remisée avec total 0)
  - Build FactureMetadata avec routing multi-tenant
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from scripts.etl.parsers._shared.column_utils import parse_fr_number
from scripts.etl.parsers.taiyat.constants import (
    CLIENT_TO_TENANT,
    RE_CODE_CLIENT,
    RE_DATE_ANY,
    RE_DATE_EXPLICIT,
    RE_FACTURE_NUM,
    RE_NUMERIC_LINE,
    RE_TOTAL_TTC_EUR,
)


def _client_from_filename(path: Path) -> Optional[str]:
    name = path.name.upper()
    if "NOUTAM" in name:
        return "NOUTAM"
    if "INCONTOURNABLE" in name:
        return "INCONTOURNABLE"
    return None


def _client_from_text(lines: list[str]) -> Optional[str]:
    """Fallback si nom de fichier ne contient pas l'indicateur client."""
    joined = " ".join(lines).upper()
    if "NOUTAM" in joined:
        return "NOUTAM"
    if "INCONTOURNABLE" in joined:
        return "INCONTOURNABLE"
    return None


def _parse_date_to_iso(date_raw: Optional[str]) -> Optional[str]:
    if not date_raw:
        return None
    try:
        return datetime.strptime(date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_date_iso_to_date(iso_str: Optional[str]) -> Optional[date]:
    """Convertit une date ISO string en datetime.date."""
    if not iso_str:
        return None
    try:
        return date.fromisoformat(iso_str)
    except (ValueError, TypeError):
        return None


def extract_invoice_header(lines: list[str], file_path: Path) -> dict:
    """Extrait numéro facture, date, client (nom + code)."""
    text = "\n".join(lines)
    facture_match = RE_FACTURE_NUM.search(text)
    code_client_match = RE_CODE_CLIENT.search(text)

    date_match = RE_DATE_EXPLICIT.search(text)
    if date_match is None:
        date_match = RE_DATE_ANY.search(text)

    client_nom = _client_from_filename(file_path) or _client_from_text(lines)

    return {
        "numero_facture": facture_match.group(1) if facture_match else None,
        "date_facture": _parse_date_to_iso(date_match.group(1)) if date_match else None,
        "client_nom": client_nom,
        "client_code": code_client_match.group(1) if code_client_match else None,
    }


def extract_total_ttc_declared(lines: list[str]) -> Optional[float]:
    """Sélectionne le meilleur candidat total TTC depuis les lignes "XXX EUR"."""
    candidates: list[tuple[int, int, float]] = []
    total_lines = len(lines)

    for idx, line in enumerate(lines):
        m = RE_TOTAL_TTC_EUR.search(line)
        if not m:
            continue
        value = parse_fr_number(m.group(1))
        if value is None:
            continue

        prev_window = " ".join(lines[max(0, idx - 4): idx + 1]).upper()
        score = 0
        if "PAYER" in prev_window or "NET A" in prev_window:
            score += 2
        if "HT." in prev_window or "BASE" in prev_window:
            score += 1
        if idx >= total_lines // 2:
            score += 1

        candidates.append((score, idx, value))

    if not candidates:
        return None

    best_score, _, best_value = max(candidates, key=lambda item: (item[0], item[1]))
    if best_score == 0:
        return candidates[-1][2]
    return best_value


def extract_tva_summary_totals(lines: list[str]) -> dict[float, float]:
    """Extrait un total TTC attendu par taux de TVA depuis le récapitulatif."""
    totals: dict[float, float] = {}

    for line in lines:
        if not RE_NUMERIC_LINE.match(line):
            continue

        nums = [parse_fr_number(x) for x in re.findall(r"\d+[.,]\d+", line)]
        nums = [n for n in nums if n is not None]
        if len(nums) < 3:
            continue

        rate = base = tax = None

        if len(nums) >= 5:
            rate_cand = nums[-2]
            base_cand = nums[-3]
            tax_cand = nums[-1]
            if 0.0 < rate_cand <= 30.0:
                rate, base, tax = rate_cand, base_cand, tax_cand
        elif len(nums) == 3:
            rate_cand = nums[1]
            base_cand = nums[0]
            tax_cand = nums[2]
            if 0.0 < rate_cand <= 30.0:
                rate, base, tax = rate_cand, base_cand, tax_cand

        if rate is None or base is None or tax is None:
            continue

        ttc = round(base + tax, 2)
        rate_key = round(rate, 2)
        totals[rate_key] = round(totals.get(rate_key, 0.0) + ttc, 2)

    return totals


def best_group_total(amounts: list[float], target: float) -> tuple[float, str]:
    """Heuristique de réconciliation d'un groupe TVA : teste all/single/pairs
    et retourne le sous-ensemble minimisant |target - sum|.
    """
    if not amounts:
        return 0.0, "none"

    total_all = round(sum(amounts), 2)
    best_total = total_all
    best_diff = abs(target - total_all)
    best_method = "all"
    n = len(amounts)

    def consider(candidate: float, method: str) -> None:
        nonlocal best_total, best_diff, best_method
        cand = round(candidate, 2)
        diff = abs(target - cand)
        if diff + 1e-9 < best_diff:
            best_total = cand
            best_diff = diff
            best_method = method

    for i in range(n):
        consider(amounts[i], "single")
        consider(total_all - amounts[i], "all_minus_one")

    for i in range(n):
        for j in range(i + 1, n):
            consider(amounts[i] + amounts[j], "pair")
            consider(total_all - amounts[i] - amounts[j], "all_minus_two")

    return best_total, best_method


def build_facture_metadata(
    metrics: dict,
    reconciled_by_rate: dict[float, float],
) -> "FactureMetadata":
    """Construit un FactureMetadata TAIYAT depuis les métriques.

    TAIYAT travaille en TTC → on déduit HT + TVA depuis le reconciled_by_rate.
    Routing multi-tenant : INCONTOURNABLE=3, NOUTAM=2.
    """
    from app.etl_types import FactureMetadata

    total_ttc_reconciled = metrics.get("total_ttc_reconciled")
    total_ttc_cts = round(total_ttc_reconciled * 100) if total_ttc_reconciled else None

    # Estimation HT depuis TTC réconcilié et breakdown par TVA
    montant_ht_cts = 0
    montant_tva_cts = 0
    if reconciled_by_rate:
        for rate, ttc_eur in reconciled_by_rate.items():
            ttc_centimes = round(ttc_eur * 100)
            taux_decimal = rate / 100.0
            ht_centimes = round(ttc_centimes / (1 + taux_decimal))
            tva_centimes = ttc_centimes - ht_centimes
            montant_ht_cts += ht_centimes
            montant_tva_cts += tva_centimes
    elif total_ttc_cts:
        # Fallback TVA 20% si pas de breakdown
        montant_ht_cts = round(total_ttc_cts / 1.20)
        montant_tva_cts = total_ttc_cts - montant_ht_cts

    quality_raw = metrics.get("quality_score", 0)
    ecart = metrics.get("ecart_ttc_reconciled")

    client_name = metrics.get("client_name")
    target_tenant_id = CLIENT_TO_TENANT.get(client_name) if client_name else None

    return FactureMetadata(
        vendor_code="TAIYAT",
        numero_facture=metrics.get("invoice_number"),
        date_facture=parse_date_iso_to_date(metrics.get("invoice_date")),
        montant_ht_total=montant_ht_cts or None,
        montant_tva_total=montant_tva_cts or None,
        montant_ttc_total=total_ttc_cts,
        quality_score=min(round(quality_raw), 100) if quality_raw else None,
        ecart_reconciliation=ecart,
        lignes_brutes=metrics.get("line_count_output", 0) + metrics.get("line_count_rejected", 0),
        client_name=client_name,
        target_tenant_id=target_tenant_id,
    )
