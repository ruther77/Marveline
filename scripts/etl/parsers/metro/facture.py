"""Logique facture METRO — header, totaux, ajustements, réconciliation.

Repris quasi à l'identique du parser legacy. Responsabilité :
  - Extraction en-tête (numéro facture, date, total HT)
  - Détection lignes remise/ajustement
  - Réconciliation montants
  - Construction FactureMetadata
"""
from __future__ import annotations

import itertools
import logging
import re
from datetime import date as date_type
from typing import Optional

from scripts.etl.parsers.metro.columns import parse_fr_number

logger = logging.getLogger(__name__)

# ── Regexes en-tête facture ──────────────────────────────────────────────────

RE_TOTAL_HT = re.compile(
    r"Total\s*H\.?T\.?\s*:?\s*([\d\s]+[,\.]\d{2}-?)", re.IGNORECASE
)
RE_FACTURE_NUM = re.compile(
    r"FACTURE\s+([\d/()]+[^\s]*)\s*.*?\((\d{3}-\d+)\)", re.IGNORECASE
)
RE_FACTURE_DATE = re.compile(
    r"Date\s+facture\s*[*:]?\s*:?\s*(\d{2}-\d{2}-\d{4})", re.IGNORECASE
)
RE_DISCOUNT_LINE = re.compile(
    r"(?:\d+\s*POUR\s*\d+|OFFRE\s+\w+.{0,20}PAYEZ.{0,15}MOINS?"
    r"|REMISE|PROMO|AVOIR|RETOUR|RISTOURNE|GRATUIT"
    r"|REDUCTION|DEDUCTION|CREDIT|GESTE\s+COMMERCIAL)"
    r".*?([\d\s]+[,\.]\d{2})\s*-",
    re.IGNORECASE,
)
RE_SURCHARGE_LINE = re.compile(
    r"(?:PLUS\s*:\s*)?(?:COTIS\.?.{0,4}SEC.{0,8}SOCIALE|FRAIS\s+TRANSPORT|FRAIS\s+LIVRAISON"
    r"|PORT\s+FORFAIT|CONSIGNE|ADHESION|ABONNEMENT|CONTRIBU"
    r"|CARTE\s+METRO|COTISATION\s+ANNUEL)"
    r".*?([\d\s]+[,\.]\d{2})",
    re.IGNORECASE,
)
RE_DONT_COTIS = re.compile(
    r"DON\w{0,3}\s*[:\s]\s*.{0,5}COTIS\.?.{0,4}SEC.{0,8}SOCIALE[^0-9]{0,4}([\d\s]+[,\.]\d{2})", re.IGNORECASE
)


def extract_header(text: str) -> dict[str, Optional[str]]:
    """Extrait numéro de facture, numéro interne et date."""
    header: dict[str, Optional[str]] = {
        "numero_facture": None,
        "numero_interne": None,
        "date_facture": None,
    }
    m_num = RE_FACTURE_NUM.search(text or "")
    if m_num:
        raw = m_num.group(1)
        header["numero_facture"] = re.sub(r"[^\d/()]", "", raw)
        header["numero_interne"] = m_num.group(2)
    m_date = RE_FACTURE_DATE.search(text or "")
    if m_date:
        header["date_facture"] = m_date.group(1)
    return header


def extract_total_ht(text: str) -> Optional[float]:
    """Extrait le Total HT déclaré depuis le texte brut de la page."""
    match = RE_TOTAL_HT.search(text or "")
    if not match:
        return None
    return parse_fr_number(match.group(1))


_RE_N_POUR_M = re.compile(r"(\d+)\s*POUR\s*(\d+)", re.IGNORECASE)


def extract_promo_ratio(line: str) -> Optional[tuple[int, int]]:
    """Détecte un pattern 'N POUR M' et retourne (reçu, payé).

    Ex : '5 POUR 4' → (5, 4) signifie 5 packs reçus, 4 payés.
    Valide seulement si reçu > payé (sinon ce n'est pas une promo).
    """
    m = _RE_N_POUR_M.search(line)
    if not m:
        return None
    received, paid = int(m.group(1)), int(m.group(2))
    if received > paid > 0:
        return received, paid
    return None


def extract_discount_amount(line: str) -> Optional[float]:
    """Détecte une ligne remise et retourne le montant négatif."""
    match = RE_DISCOUNT_LINE.search(line)
    if not match:
        return None
    val = parse_fr_number(match.group(1))
    return -abs(val) if val is not None else None


def extract_surcharge_amount(line: str) -> Optional[float]:
    """Détecte une ligne supplément et retourne le montant positif."""
    # Guard : ligne de total HT contenant "Consigne" (faux positif)
    if re.search(r"Total\s+H\.?T\.", line, re.IGNORECASE):
        return None
    # Guard : ligne "Dont : COTIS..." = récapitulatif capturé par RE_DONT_COTIS
    # → ne pas l'additionner une seconde fois via RE_SURCHARGE_LINE (double-cotis)
    if re.match(r"DON\w{0,3}\s*:", line, re.IGNORECASE):
        return None
    match = RE_SURCHARGE_LINE.search(line)
    if not match:
        return None
    val = parse_fr_number(match.group(1))
    return abs(val) if val is not None else None


def select_best_adjustments(
    total_ht: Optional[float],
    montant_base: float,
    candidates: list[float],
) -> tuple[float, list[float]]:
    """Sélectionne le sous-ensemble d'ajustements minimisant |TH - (base + sum)|.

    Algorithme exhaustif (2^n) pour n ≤ 20 candidats — traite les cas où ni
    la remise ni le supplément pris seuls n'améliorent l'écart, mais leur
    combinaison l'annule (ex : cotis − remise = target).
    Pour n > 20, repli sur le greedy d'origine.
    """
    if total_ht is None or not candidates:
        return 0.0, []

    target = total_ht - montant_base
    best_total = 0.0
    best_selected: list[float] = []
    best_diff = abs(target)

    n = len(candidates)

    if n <= 20:
        for r in range(1, n + 1):
            for combo in itertools.combinations(range(n), r):
                total = sum(candidates[i] for i in combo)
                diff = abs(target - total)
                if diff + 1e-9 < best_diff:
                    best_diff = diff
                    best_total = total
                    best_selected = [candidates[i] for i in combo]
    else:
        # Greedy pour les rares cas à très nombreux candidats
        running = 0.0
        current_diff = best_diff
        remaining = list(candidates)
        while remaining:
            best_index = None
            local_best = current_diff
            for i, amount in enumerate(remaining):
                diff = abs(target - (running + amount))
                if diff + 1e-9 < local_best:
                    local_best = diff
                    best_index = i
            if best_index is None:
                break
            chosen = remaining.pop(best_index)
            best_selected.append(chosen)
            running += chosen
            current_diff = local_best
        best_total = running

    return round(best_total, 2), best_selected


def euros_to_centimes(val: Optional[float]) -> Optional[int]:
    """Convertit un montant EUR float en centimes int."""
    if val is None:
        return None
    return round(val * 100)


def parse_date_metro(raw: Optional[str]) -> Optional[date_type]:
    """Convertit une date DD-MM-YYYY en objet date."""
    if not raw:
        return None
    parts = raw.split("-")
    if len(parts) != 3:
        return None
    try:
        return date_type(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        logger.warning("Date facture invalide : %s", raw)
        return None


def build_facture_metadata(
    metrics: dict,
) -> "FactureMetadata":
    """Construit un FactureMetadata depuis les métriques du parser."""
    from app.etl_types import FactureMetadata

    total_ht = metrics.get("total_ht_declared")
    montant_reconcilie = metrics.get("montant_reconcilie")

    # Si total_ht déclaré = 0 mais produits présents, utiliser le montant réconcilié
    if total_ht is not None and total_ht == 0.0 and montant_reconcilie and montant_reconcilie > 0:
        total_ht = montant_reconcilie

    montant_ht_cts = euros_to_centimes(total_ht or montant_reconcilie)
    montant_tva_cts = round(montant_ht_cts * 2000 / 10000) if montant_ht_cts else None
    montant_ttc_cts = (
        (montant_ht_cts + montant_tva_cts) if montant_ht_cts and montant_tva_cts else None
    )

    numero_facture = metrics.get("numero_interne") or metrics.get("numero_facture")

    quality = 0
    if numero_facture:
        quality += 10
    if metrics.get("date_facture"):
        quality += 10
    if total_ht is not None:
        quality += 30
    if metrics.get("line_count_output", 0) > 0:
        quality += 20
    ecart_abs = metrics.get("ecart_ht_abs")
    if ecart_abs is not None and ecart_abs <= 5.0:
        quality += 30
    elif ecart_abs is not None and ecart_abs <= 20.0:
        quality += 15

    return FactureMetadata(
        vendor_code="METRO",
        numero_facture=numero_facture,
        date_facture=parse_date_metro(metrics.get("date_facture")),
        montant_ht_total=montant_ht_cts,
        montant_tva_total=montant_tva_cts,
        montant_ttc_total=montant_ttc_cts,
        quality_score=min(quality, 100),
        ecart_reconciliation=metrics.get("ecart_ht"),
        lignes_brutes=metrics.get("line_count_all", 0),
    )
