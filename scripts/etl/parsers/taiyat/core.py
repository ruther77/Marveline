"""Core du parser TAIYAT v2 — assemblage final.

Fonctions publiques :
  - parse(fichier) → list[LigneParsee]
  - parse_facture(fichier) → tuple[list[LigneParsee], FactureMetadata]
  - parse_with_facture_metrics(fichier) → tuple[list[LigneParsee], dict]

Stratégie alignée sur METRO v2 :
  - Extraction column-based (extract_line TAIYAT)
  - Tokenisation sémantique (BRAND/WORD/NUMERIC/PACKAGING/MULTIPLIER/CONTAINER/DEGREE)
  - Attributs structurés : colisage, volume_unitaire_ml, contenant, degre_alcool
  - Enrichissement marque via brand_dictionary (multi-mots + single)
  - Catégorie : brand_cat > KNN catalogue > keyword classifier
  - Réconciliation par taux TVA (spécifique TAIYAT, repris du legacy)

Spécificités TAIYAT :
  - Pas d'EAN ni article fournisseur
  - PU et montants en TTC → déduction HT via taux TVA
  - Routing multi-tenant INCONTOURNABLE=3 / NOUTAM=2
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

from app.etl_types import FactureMetadata, LigneParsee

from scripts.etl.parsers._shared.column_utils import group_by_y
from scripts.etl.parsers._shared.conditionnement import extract_conditionnement
from scripts.etl.parsers._shared.tokenizer import (
    DesigToken,
    TokenType,
    build_designation,
    build_designation_raw,
    extract_colisage,
    extract_container,
    extract_degree,
    extract_volume_ml,
)
from scripts.etl.parsers.brand_dictionary import get_brand_dictionary
from scripts.etl.parsers.taiyat.columns import ExtractedLineTAIYAT, extract_line
from scripts.etl.parsers.taiyat.constants import (
    ABBREVIATIONS,
    LINE_TOLERANCE,
    LINE_TOLERANCE_EUR,
    PAYS_PROVENANCE,
    SOURCE_FOURNISSEUR,
    TOTAL_TOLERANCE_EUR,
    TVA_CODE_TO_CENTIEME,
    UV_TO_UNITE,
)
from scripts.etl.parsers.taiyat.facture import (
    best_group_total,
    build_facture_metadata,
    extract_invoice_header,
    extract_total_ttc_declared,
    extract_tva_summary_totals,
)

logger = logging.getLogger(__name__)

# ── Chargement brand dictionary (module-load) ────────────────────────────────

_brand_dict = get_brand_dictionary()
_known_brands = _brand_dict.as_frozenset()


# ── Extraction de marque TAIYAT ──────────────────────────────────────────────


def _extract_brand_taiyat(
    tokens: list[DesigToken],
    designation: str,
) -> tuple[Optional[str], Optional[str]]:
    """Extrait la marque depuis les tokens TAIYAT via brand_dict.

    Stratégie :
      1. Lookup multi-mots sur la séquence WORD/BRAND/NUMERIC
      2. Lookup single-word sur les tokens BRAND
      3. NULL sinon (pas de marque = mieux qu'une fausse)
    """
    # Tokens candidats marque (WORD, BRAND, NUMERIC en 1ère position)
    desig_words = [
        t.cleaned for t in tokens
        if t.token_type in (TokenType.BRAND, TokenType.WORD, TokenType.NUMERIC)
    ]

    # 1. Multi-mots (greedy)
    for i in range(len(desig_words)):
        match = _brand_dict.lookup_multiword(desig_words, i)
        if match:
            brand_name, brand_entry, _n = match
            all_texts = [t.cleaned for t in tokens]
            brand_cat = _brand_dict.resolve_category(brand_name, all_texts)
            return brand_name, brand_cat

    # 2. Single-word sur BRAND token
    for t in tokens:
        if t.token_type == TokenType.BRAND:
            entry = _brand_dict.lookup(t.cleaned)
            if entry:
                all_texts = [tk.cleaned for tk in tokens]
                brand_cat = _brand_dict.resolve_category(t.cleaned, all_texts)
                return t.cleaned.upper(), brand_cat
            break

    return None, None


def _classify_categorie(
    designation: str,
    brand_cat: Optional[str],
) -> Optional[str]:
    """Classifie la catégorie : brand_cat si pertinent, sinon classifier keyword."""
    if brand_cat and brand_cat != "_PRIVATE_LABEL":
        return brand_cat
    try:
        from app.services.catalogue.etl_classification import classify_categorie_code
        from app.services.catalogue.etl_deduplication import normalize_designation
        norm = normalize_designation(designation)
        classified = classify_categorie_code(norm)
        if classified and classified != "AUTRE":
            return classified
    except Exception as exc:
        logger.debug("TAIYAT classify_categorie failed: %s", exc)
    return None


# ── Conversion ExtractedLineTAIYAT → LigneParsee ─────────────────────────────


def _deduce_ht_cts(
    montant_ttc: float,
    taux_tva_centieme: Optional[int],
) -> Optional[int]:
    """Déduit le HT en centimes depuis le TTC (EUR float) et le taux TVA en centièmes."""
    if taux_tva_centieme is None:
        return None
    ttc_cts = round(montant_ttc * 100)
    return round(ttc_cts * 10000 / (10000 + taux_tva_centieme))


def _deduce_pu_ht_cts(
    prix_ttc_unit_effectif: float,
    taux_tva_centieme: Optional[int],
) -> Optional[int]:
    """Déduit le PU HT en centimes depuis le PU TTC effectif."""
    if taux_tva_centieme is None:
        return None
    pu_ttc_cts = round(prix_ttc_unit_effectif * 100)
    return round(pu_ttc_cts * 10000 / (10000 + taux_tva_centieme))


def _extracted_to_ligne(ex: ExtractedLineTAIYAT) -> Optional[LigneParsee]:
    """Convertit une ExtractedLineTAIYAT en LigneParsee.

    TAIYAT travaille en TTC → on calcule HT par déduction via taux TVA.
    """
    tokens = ex.designation_tokens

    designation = build_designation(
        tokens,
        abbrev_dict=ABBREVIATIONS,
        extra_noise_words=PAYS_PROVENANCE,
    )
    designation_raw = build_designation_raw(tokens)

    if not designation or len(designation) < 3:
        return None

    # Attributs structurés depuis tokens
    degree = extract_degree(tokens)
    container = extract_container(tokens)
    volume_ml = extract_volume_ml(tokens)
    colisage_from_tokens = extract_colisage(tokens)

    # Conditionnement non-destructif
    conditionnement, unite_base_tokens, contenant_from_cond = extract_conditionnement(tokens)
    contenant = contenant_from_cond or container

    # Colisage : priorité à la colonne Pièces (plus fiable), fallback tokens
    if ex.pieces is not None and ex.pieces > 1:
        colisage = ex.pieces
    else:
        colisage = colisage_from_tokens

    # Unité de base : priorité à Uv (c/p/u/k), fallback tokens
    unite_base = UV_TO_UNITE.get(ex.uv or "", unite_base_tokens)

    # Marque + catégorie
    marque, brand_cat = _extract_brand_taiyat(tokens, designation)
    categorie = _classify_categorie(designation, brand_cat)

    # Calculs financiers : TAIYAT est en TTC
    taux_tva_centieme = TVA_CODE_TO_CENTIEME.get(ex.tva_code or "")
    montant_ttc_cts = round(ex.montant_ttc * 100) if ex.montant_ttc is not None else None
    montant_ht_cts = _deduce_ht_cts(ex.montant_ttc, taux_tva_centieme) if ex.montant_ttc is not None else None
    pu_ht_cts = _deduce_pu_ht_cts(ex.prix_ttc_unit_effectif, taux_tva_centieme) if ex.prix_ttc_unit_effectif is not None else None

    return LigneParsee(
        designation=designation,
        unite_base=unite_base,
        source_fournisseur=SOURCE_FOURNISSEUR,
        ean=None,  # TAIYAT ne fournit pas d'EAN
        conditionnement=conditionnement,
        categorie_code=categorie,
        marque=marque,
        # Financier (en centimes)
        quantite=ex.colis,
        prix_unitaire_cts=pu_ht_cts,
        montant_ht_cts=montant_ht_cts,
        montant_ttc_cts=montant_ttc_cts,
        taux_tva_centieme=taux_tva_centieme,
        # Enrichis v2
        article_fournisseur=None,
        degre_alcool=degree,
        contenant=contenant,
        volume_unitaire_ml=volume_ml,
        colisage=colisage,
        designation_raw=designation_raw,
        # Coordonnées PDF
        page_number=ex.page_number,
        y_position=ex.y_position,
    )


# ── Détection ligne remise (post-parsing) ─────────────────────────────────────


def _is_pure_discount_line(ligne: LigneParsee, ex: ExtractedLineTAIYAT) -> bool:
    """Détecte si une ligne est une remise pure (PU TTC = 0 après remise 100%)."""
    if ex.est_remise and ex.remise_pct is not None and ex.remise_pct >= 99.9:
        return True
    if ligne.montant_ttc_cts is not None and ligne.montant_ttc_cts == 0:
        return True
    if ligne.montant_ttc_cts is not None and ligne.montant_ttc_cts < 0:
        return True
    return False


# ── Point d'entrée principal ──────────────────────────────────────────────────


def parse_with_facture_metrics(
    fichier: str,
) -> tuple[list[LigneParsee], dict]:
    """Parse un PDF TAIYAT et renvoie lignes + métriques de cohérence.

    Signature identique au parser legacy pour compatibilité.
    """
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError(
            "pdfplumber requis pour le parser TAIYAT : pip install pdfplumber"
        ) from exc

    path = Path(fichier)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : {fichier}")

    lignes_finales: list[LigneParsee] = []
    parsed_extracted: list[tuple[LigneParsee, ExtractedLineTAIYAT]] = []
    rejected_lines = 0
    text_lines_all: list[str] = []

    with pdfplumber.open(path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            # Texte brut pour header + totaux (réutilisation logique legacy)
            page_text = page.extract_text() or ""
            text_lines_all.extend(ln.strip() for ln in page_text.splitlines() if ln.strip())

            # Mots pour extraction column-based
            words = page.extract_words()
            if not words:
                continue
            line_groups = group_by_y(words, line_tolerance=LINE_TOLERANCE)

            for y in sorted(line_groups):
                word_group = line_groups[y]
                ex = extract_line(word_group, known_brands=_known_brands)
                if ex is None:
                    continue

                ex.page_number = page_idx
                ex.y_position = y

                ligne = _extracted_to_ligne(ex)
                if ligne is None:
                    rejected_lines += 1
                    continue

                lignes_finales.append(ligne)
                parsed_extracted.append((ligne, ex))

    # ── Header facture ────────────────────────────────────────────────────
    header = extract_invoice_header(text_lines_all, path)

    # ── Totaux déclarés ───────────────────────────────────────────────────
    total_ttc_declared = extract_total_ttc_declared(text_lines_all)

    # Total calculé depuis les lignes (en EUR pour rester compatible legacy)
    total_ttc_computed = round(
        sum((l.montant_ttc_cts or 0) / 100.0 for l in lignes_finales),
        2,
    )

    ecart_ttc = None
    ecart_ttc_abs = None
    if total_ttc_declared is not None:
        ecart_ttc = round(total_ttc_declared - total_ttc_computed, 2)
        ecart_ttc_abs = abs(ecart_ttc)

    # ── Réconciliation par taux TVA ───────────────────────────────────────
    computed_ttc_by_rate: dict[float, float] = {}
    group_amounts_by_rate: dict[float, list[float]] = {}
    for ligne, _ex in parsed_extracted:
        if ligne.taux_tva_centieme is None or ligne.montant_ttc_cts is None:
            continue
        rate = round(ligne.taux_tva_centieme / 100.0, 2)
        ttc_eur = ligne.montant_ttc_cts / 100.0
        computed_ttc_by_rate[rate] = round(
            computed_ttc_by_rate.get(rate, 0.0) + ttc_eur, 2,
        )
        group_amounts_by_rate.setdefault(rate, []).append(ttc_eur)

    declared_ttc_by_rate = extract_tva_summary_totals(text_lines_all)

    reconciled_ttc_by_rate: dict[float, float] = dict(computed_ttc_by_rate)
    reconciliation_notes: list[dict] = []

    if declared_ttc_by_rate:
        reconciled_ttc_by_rate = {}
        all_rates = sorted(set(declared_ttc_by_rate) | set(computed_ttc_by_rate))
        for rate in all_rates:
            declared_rate_total = round(declared_ttc_by_rate.get(rate, 0.0), 2)
            computed_rate_total = round(computed_ttc_by_rate.get(rate, 0.0), 2)
            amounts = group_amounts_by_rate.get(rate, [])

            chosen_total = computed_rate_total
            method = "computed"

            if rate in declared_ttc_by_rate:
                if not amounts:
                    chosen_total = declared_rate_total
                    method = "declared_no_lines"
                else:
                    best_subset_total, subset_method = best_group_total(
                        amounts, declared_rate_total,
                    )
                    diff_computed = abs(declared_rate_total - computed_rate_total)
                    diff_subset = abs(declared_rate_total - best_subset_total)

                    if diff_subset + 1e-9 < diff_computed:
                        chosen_total = best_subset_total
                        method = f"subset:{subset_method}"
                    elif len(amounts) == 1 and diff_computed <= 5.0:
                        chosen_total = declared_rate_total
                        method = "single_line_ocr_adjust"

            chosen_total = round(chosen_total, 2)
            reconciled_ttc_by_rate[rate] = chosen_total

            if method != "computed":
                reconciliation_notes.append({
                    "rate": rate,
                    "method": method,
                    "declared": declared_rate_total,
                    "computed": computed_rate_total,
                    "chosen": chosen_total,
                })

    total_ttc_reconciled = round(sum(reconciled_ttc_by_rate.values()), 2)

    ecart_ttc_reconciled = None
    ecart_ttc_reconciled_abs = None
    if total_ttc_declared is not None:
        ecart_ttc_reconciled = round(total_ttc_declared - total_ttc_reconciled, 2)
        ecart_ttc_reconciled_abs = abs(ecart_ttc_reconciled)

    # ── Override zero-declared-remise ─────────────────────────────────────
    zero_declared_remise_override = False
    if (
        total_ttc_declared is not None
        and abs(total_ttc_declared) <= TOTAL_TOLERANCE_EUR
        and total_ttc_reconciled > TOTAL_TOLERANCE_EUR
    ):
        positive_lines = {
            l.designation for (l, _ex) in parsed_extracted
            if (l.montant_ttc_cts or 0) > round(TOTAL_TOLERANCE_EUR * 100)
        }
        remise_lines = {
            l.designation for (l, ex) in parsed_extracted
            if _is_pure_discount_line(l, ex)
        }
        if positive_lines and positive_lines.issubset(remise_lines):
            zero_declared_remise_override = True
            total_ttc_reconciled = 0.0
            ecart_ttc_reconciled = 0.0
            ecart_ttc_reconciled_abs = 0.0
            reconciliation_notes.append({
                "rate": None,
                "method": "zero_declared_remise_override",
                "declared": total_ttc_declared,
                "computed": total_ttc_computed,
                "chosen": total_ttc_reconciled,
            })

    # ── Métriques qualité ligne ───────────────────────────────────────────
    line_outliers: list[dict] = []
    line_ok_count = 0
    for ligne, ex in parsed_extracted:
        if ex.prix_ttc_unit_effectif is None or ex.colis is None:
            continue
        expected_ttc = round(ex.colis * ex.prix_ttc_unit_effectif, 2)
        actual_ttc = ex.montant_ttc or 0.0
        delta = round(abs(expected_ttc - actual_ttc), 2)
        if delta > LINE_TOLERANCE_EUR:
            line_outliers.append({
                "designation": ligne.designation,
                "expected_ttc": expected_ttc,
                "actual_ttc": actual_ttc,
                "delta": delta,
            })
        else:
            line_ok_count += 1

    line_count = len(parsed_extracted)
    remise_count = sum(
        1 for (l, ex) in parsed_extracted if _is_pure_discount_line(l, ex)
    )

    # ── Score qualité ─────────────────────────────────────────────────────
    quality_score = 0.0
    if header["numero_facture"]:
        quality_score += 20
    if header["date_facture"]:
        quality_score += 20
    if total_ttc_declared is not None:
        quality_score += 20
    if line_count > 0:
        quality_score += 20 * (line_ok_count / line_count)
    if ecart_ttc_reconciled_abs is not None:
        if ecart_ttc_reconciled_abs <= TOTAL_TOLERANCE_EUR:
            quality_score += 20
        elif ecart_ttc_reconciled_abs <= 1.0:
            quality_score += 10

    is_total_coherent_raw = (
        ecart_ttc_abs is not None and ecart_ttc_abs <= TOTAL_TOLERANCE_EUR
    )
    is_total_coherent = (
        ecart_ttc_reconciled_abs is not None
        and ecart_ttc_reconciled_abs <= TOTAL_TOLERANCE_EUR
    )

    metrics = {
        "file": str(path),
        "invoice_number": header["numero_facture"],
        "invoice_date": header["date_facture"],
        "client_name": header["client_nom"],
        "client_code": header["client_code"],
        "line_count_output": line_count,
        "line_count_rejected": rejected_lines,
        "line_count_discount": remise_count,
        "line_coherence_tolerance_eur": LINE_TOLERANCE_EUR,
        "line_coherence_ok_count": line_ok_count,
        "line_coherence_outlier_count": len(line_outliers),
        "line_coherence_outliers": line_outliers[:25],
        "declared_ttc_by_rate": declared_ttc_by_rate,
        "computed_ttc_by_rate": computed_ttc_by_rate,
        "reconciled_ttc_by_rate": reconciled_ttc_by_rate,
        "reconciliation_notes": reconciliation_notes,
        "total_ttc_declared": total_ttc_declared,
        "total_ttc_computed": total_ttc_computed,
        "total_ttc_reconciled": total_ttc_reconciled,
        "total_tolerance_eur": TOTAL_TOLERANCE_EUR,
        "ecart_ttc": ecart_ttc,
        "ecart_ttc_abs": ecart_ttc_abs,
        "ecart_ttc_reconciled": ecart_ttc_reconciled,
        "ecart_ttc_reconciled_abs": ecart_ttc_reconciled_abs,
        "is_total_coherent_raw": is_total_coherent_raw,
        "is_total_coherent": is_total_coherent,
        "zero_declared_remise_override": zero_declared_remise_override,
        "quality_score": round(quality_score, 2),
    }

    return lignes_finales, metrics


def parse_facture(fichier: str) -> tuple[list[LigneParsee], FactureMetadata]:
    """Parse un PDF TAIYAT et retourne lignes + FactureMetadata (ADR-25)."""
    lignes, metrics = parse_with_facture_metrics(fichier)
    metadata = build_facture_metadata(metrics, metrics.get("reconciled_ttc_by_rate", {}))
    return lignes, metadata


def parse(fichier: str) -> list[LigneParsee]:
    """Parse un PDF TAIYAT et retourne les lignes normalisées ADR-08."""
    lignes, metrics = parse_with_facture_metrics(fichier)

    if (
        metrics.get("ecart_ttc_reconciled_abs") is not None
        and metrics["ecart_ttc_reconciled_abs"] > TOTAL_TOLERANCE_EUR
    ):
        logger.warning(
            "TAIYAT parser coherence: ecart TTC eleve (%.2f) pour %s "
            "[decl=%.2f, calc=%.2f, reconc=%.2f, remises=%d]",
            metrics["ecart_ttc_reconciled_abs"],
            Path(fichier).name,
            metrics.get("total_ttc_declared", 0.0),
            metrics.get("total_ttc_computed", 0.0),
            metrics.get("total_ttc_reconciled", 0.0),
            metrics.get("line_count_discount", 0),
        )

    logger.info("TAIYAT parser: %d lignes extraites depuis %s", len(lignes), Path(fichier).name)
    return lignes
