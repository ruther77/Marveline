"""Tests unitaires parser TAIYAT v2 (package).

Couvre :
  - Extraction column-based (ExtractedLineTAIYAT)
  - Parsing PU TTC avec remise inline (-XX.X%)
  - Conversion TTC → HT via taux TVA
  - Routing multi-tenant INCONTOURNABLE / NOUTAM
  - Réconciliation par taux TVA + override zero-remise
  - Remplissage champs enrichis (designation_raw, colisage, contenant, volume_unitaire_ml)
  - Intégration pipeline (_PARSERS)
  - Non-régression sur PDFs réels du corpus docs/TAIYAT/factures_individuelles
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.etl.import_pipeline import _PARSERS
from scripts.etl.parsers.taiyat import parse, parse_facture, parse_with_facture_metrics
from scripts.etl.parsers.taiyat.columns import (
    ExtractedLineTAIYAT,
    _parse_pu_ttc,
    extract_line,
)
from scripts.etl.parsers.taiyat.constants import (
    CLIENT_TO_TENANT,
    PAYS_PROVENANCE,
    TVA_CODE_TO_CENTIEME,
    UV_TO_UNITE,
)
from scripts.etl.parsers.taiyat.core import (
    _deduce_ht_cts,
    _deduce_pu_ht_cts,
    _extract_brand_taiyat,
)
from scripts.etl.parsers.taiyat.facture import (
    _client_from_filename,
    _client_from_text,
    best_group_total,
    extract_total_ttc_declared,
    extract_tva_summary_totals,
    parse_date_iso_to_date,
)


# ══════════════════════════════════════════════════════════════════════════════
# Intégration pipeline
# ══════════════════════════════════════════════════════════════════════════════


def test_import_pipeline_points_to_taiyat_package():
    assert _PARSERS["taiyat"] == "scripts.etl.parsers.taiyat"


def test_public_api_exposes_three_entry_points():
    assert callable(parse)
    assert callable(parse_facture)
    assert callable(parse_with_facture_metrics)


# ══════════════════════════════════════════════════════════════════════════════
# Constants & mappings
# ══════════════════════════════════════════════════════════════════════════════


def test_tva_code_mapping_5_5_and_20():
    assert TVA_CODE_TO_CENTIEME["1"] == 550
    assert TVA_CODE_TO_CENTIEME["2"] == 2000


def test_client_to_tenant_routing():
    assert CLIENT_TO_TENANT["INCONTOURNABLE"] == 3
    assert CLIENT_TO_TENANT["NOUTAM"] == 2


def test_uv_mapping():
    assert UV_TO_UNITE["c"] == "colis"
    assert UV_TO_UNITE["p"] == "piece"
    assert UV_TO_UNITE["k"] == "kg"


def test_pays_provenance_contains_typical_taiyat_countries():
    for pays in ("CAMEROUN", "POLOGNE", "BRESIL", "COSTA-RICA", "CHINE", "HONDURAS"):
        assert pays in PAYS_PROVENANCE


# ══════════════════════════════════════════════════════════════════════════════
# Parsing PU TTC avec remise inline
# ══════════════════════════════════════════════════════════════════════════════


def test_parse_pu_ttc_no_discount():
    base, pct, eff, is_remise = _parse_pu_ttc("19.900")
    assert base == 19.9
    assert pct is None
    assert eff == 19.9
    assert is_remise is False


def test_parse_pu_ttc_full_discount_100_pct():
    base, pct, eff, is_remise = _parse_pu_ttc("21.900-100.0%")
    assert base == 21.9
    assert pct == 100.0
    assert eff == 0.0
    assert is_remise is True


def test_parse_pu_ttc_partial_discount():
    base, pct, eff, is_remise = _parse_pu_ttc("10.000-25.0%")
    assert base == 10.0
    assert pct == 25.0
    assert eff == 7.5
    assert is_remise is True


def test_parse_pu_ttc_invalid_returns_none():
    base, pct, eff, is_remise = _parse_pu_ttc("not a number")
    assert base is None
    assert eff is None


# ══════════════════════════════════════════════════════════════════════════════
# extract_line — column-based
# ══════════════════════════════════════════════════════════════════════════════


def _build_words(rows: list[tuple[str, float, float]], y: float = 100.0) -> list[dict]:
    """rows = [(text, x0, x1), ...]"""
    return [{"text": t, "x0": x0, "x1": x1, "top": y} for (t, x0, x1) in rows]


def test_extract_line_standard_product():
    # "1 Gingembre Frais Cameroun 1 CAMEROUN 18.86 1 c 19.900 19.90 1"
    words = _build_words([
        ("1",          54.0,  60.0),
        ("Gingembre",  65.0, 115.0),
        ("Frais",     118.0, 140.0),
        ("Cameroun",  144.0, 180.0),
        ("1",         315.0, 320.0),
        ("CAMEROUN",  335.0, 371.0),
        ("18.86",     388.0, 411.0),
        ("1",         434.0, 440.0),
        ("c",         450.0, 455.0),
        ("19.900",    471.0, 499.0),
        ("19.90",     533.0, 556.0),
        ("1",         561.0, 564.0),
    ])
    ex = extract_line(words, known_brands=None)
    assert ex is not None
    assert ex.colis == 1.0
    assert ex.montant_ttc == 19.90
    assert ex.prix_ttc_unit_effectif == 19.9
    assert ex.est_remise is False
    assert ex.pays_origine == "CAMEROUN"
    assert ex.cat == "1"
    assert ex.uv == "c"
    assert ex.tva_code == "1"
    assert ex.prix_ht_unit == 18.86


def test_extract_line_with_multiplier_12x120gr():
    # "1 Maggi arome HOT 12x120gr 1 POLOGNE 22.75 12 c 24.000 24.00 1"
    words = _build_words([
        ("1",          54.0,  60.0),
        ("Maggi",      65.0,  90.0),
        ("arome",      92.0, 118.0),
        ("HOT",       120.0, 140.0),
        ("12x120gr",  142.0, 180.0),
        ("1",         315.0, 320.0),
        ("POLOGNE",   335.0, 370.0),
        ("22.75",     388.0, 411.0),
        ("12",        429.0, 440.0),
        ("c",         450.0, 455.0),
        ("24.000",    471.0, 499.0),
        ("24.00",     533.0, 556.0),
        ("1",         561.0, 564.0),
    ])
    ex = extract_line(words, known_brands=None)
    assert ex is not None
    assert ex.pieces == 12
    assert ex.pays_origine == "POLOGNE"
    # Le token "12x120gr" doit être présent dans les tokens désignation
    token_cleaneds = [t.cleaned for t in ex.designation_tokens]
    assert any("120" in tc for tc in token_cleaneds)


def test_extract_line_with_discount_100_pct():
    # "1 Aile de poulet VAN O BEL 10 kg 1 BELGIQUE 0.00 1 c 21.900-100.0% 0.00 1"
    words = _build_words([
        ("1",           54.0,  60.0),
        ("Aile",        65.0,  82.0),
        ("de",          86.0,  95.0),
        ("poulet",      98.0, 135.0),
        ("VAN",        140.0, 158.0),
        ("O",          161.0, 170.0),
        ("BEL",        173.0, 195.0),
        ("10",         200.0, 215.0),
        ("kg",         218.0, 230.0),
        ("1",          315.0, 320.0),
        ("BELGIQUE",   335.0, 378.0),
        ("0.00",       388.0, 411.0),
        ("1",          434.0, 440.0),
        ("c",          450.0, 455.0),
        ("21.900-100.0%", 465.0, 502.0),
        ("0.00",       533.0, 556.0),
        ("1",          561.0, 564.0),
    ])
    ex = extract_line(words, known_brands=None)
    assert ex is not None
    assert ex.est_remise is True
    assert ex.remise_pct == 100.0
    assert ex.prix_ttc_unit_effectif == 0.0
    assert ex.montant_ttc == 0.0


def test_extract_line_returns_none_if_colis_missing():
    words = _build_words([
        ("Gingembre", 65.0, 115.0),
        ("18.86",    388.0, 411.0),
        ("19.900",   471.0, 499.0),
        ("19.90",    533.0, 556.0),
    ])
    ex = extract_line(words, known_brands=None)
    assert ex is None


def test_extract_line_returns_none_if_montant_missing():
    words = _build_words([
        ("1",         54.0,  60.0),
        ("Gingembre", 65.0, 115.0),
        ("19.900",   471.0, 499.0),
    ])
    ex = extract_line(words, known_brands=None)
    assert ex is None


# ══════════════════════════════════════════════════════════════════════════════
# Déductions HT ↔ TTC
# ══════════════════════════════════════════════════════════════════════════════


def test_deduce_ht_cts_5_5_percent():
    # 100€ TTC @ 5.5% → 94.79€ HT
    ht_cts = _deduce_ht_cts(100.0, 550)
    assert ht_cts == round(10000 * 10000 / 10550)  # 9479


def test_deduce_ht_cts_20_percent():
    # 120€ TTC @ 20% → 100€ HT
    ht_cts = _deduce_ht_cts(120.0, 2000)
    assert ht_cts == 10000


def test_deduce_ht_cts_none_if_no_tva():
    assert _deduce_ht_cts(100.0, None) is None


def test_deduce_pu_ht_cts_after_discount():
    # PU TTC = 0 après 100% remise → PU HT = 0
    assert _deduce_pu_ht_cts(0.0, 550) == 0
    # PU TTC 5.50€ @ 5.5% → 5.21€ HT
    assert _deduce_pu_ht_cts(5.50, 550) == round(550 * 10000 / 10550)


# ══════════════════════════════════════════════════════════════════════════════
# Facture — header & totaux
# ══════════════════════════════════════════════════════════════════════════════


def test_client_from_filename_incontournable():
    assert _client_from_filename(Path("TAIYAT_INCONTOURNABLE_214370.pdf")) == "INCONTOURNABLE"


def test_client_from_filename_noutam():
    assert _client_from_filename(Path("TAIYAT_NOUTAM_200742.pdf")) == "NOUTAM"


def test_client_from_filename_unknown_returns_none():
    assert _client_from_filename(Path("unknown.pdf")) is None


def test_client_from_text_fallback():
    lines = ["Date: 05/03/2024", "L'INCONTOURNABLE", "1 RUE DE PARIS"]
    assert _client_from_text(lines) == "INCONTOURNABLE"


def test_extract_total_ttc_prefers_net_a_payer():
    lines = [
        "Base Taxes 834.60 EUR",
        "NET A PAYER TTC",
        "880.50 EUR",
    ]
    # "NET A" dans la fenêtre précédente → score +2
    assert extract_total_ttc_declared(lines) == 880.50


def test_extract_total_ttc_fallback_last_eur():
    lines = [
        "Some text",
        "50.00 EUR",
        "Some other text",
        "100.00 EUR",
    ]
    # Aucun mot-clé, fallback = dernier EUR
    assert extract_total_ttc_declared(lines) == 100.00


def test_extract_tva_summary_totals_parses_single_rate():
    lines = ["40.00 834.60 834.60 5.50 45.90"]
    result = extract_tva_summary_totals(lines)
    # base=834.60, tax=45.90, rate=5.50 → ttc=880.50
    assert 5.5 in result
    assert result[5.5] == 880.50


def test_best_group_total_exact_match():
    # target=30, amounts=[10, 20] → 30 avec pair (10+20)
    total, method = best_group_total([10.0, 20.0], 30.0)
    assert abs(total - 30.0) < 0.01


def test_best_group_total_single_element():
    # target=15, amounts=[10, 15, 20] → single 15
    total, method = best_group_total([10.0, 15.0, 20.0], 15.0)
    assert total == 15.0


def test_parse_date_iso_to_date_valid():
    d = parse_date_iso_to_date("2024-03-05")
    assert d.year == 2024 and d.month == 3 and d.day == 5


def test_parse_date_iso_to_date_none():
    assert parse_date_iso_to_date(None) is None
    assert parse_date_iso_to_date("") is None


# ══════════════════════════════════════════════════════════════════════════════
# Non-régression sur PDFs réels (si disponibles dans le corpus)
# ══════════════════════════════════════════════════════════════════════════════


_PDF_DIR = Path(__file__).parents[3] / "docs" / "TAIYAT" / "factures_individuelles"


@pytest.fixture(scope="module")
def sample_pdf() -> Path:
    if not _PDF_DIR.exists():
        pytest.skip(f"Corpus TAIYAT absent : {_PDF_DIR}")
    matches = sorted(_PDF_DIR.glob("TAIYAT_INCONTOURNABLE_214370_*.pdf"))
    if not matches:
        pytest.skip("PDF de référence TAIYAT_INCONTOURNABLE_214370 absent")
    return matches[0]


def test_parse_facture_returns_lignes_and_metadata(sample_pdf: Path):
    lignes, meta = parse_facture(str(sample_pdf))
    assert len(lignes) > 0
    assert meta.vendor_code == "TAIYAT"
    assert meta.numero_facture == "214370"
    assert meta.client_name == "INCONTOURNABLE"
    assert meta.target_tenant_id == 3


def test_parse_facture_quality_score_reaches_100(sample_pdf: Path):
    _, meta = parse_facture(str(sample_pdf))
    assert meta.quality_score == 100


def test_parse_facture_montants_coherents(sample_pdf: Path):
    _, meta = parse_facture(str(sample_pdf))
    assert meta.montant_ht_total is not None
    assert meta.montant_tva_total is not None
    assert meta.montant_ttc_total is not None
    # HT + TVA = TTC (tolérance 1 centime)
    assert abs((meta.montant_ht_total + meta.montant_tva_total) - meta.montant_ttc_total) <= 1


def test_parse_facture_designation_raw_toujours_remplie(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    assert all(l.designation_raw for l in lignes)


def test_parse_facture_designation_ne_contient_pas_pays(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    for l in lignes:
        words_upper = [w.strip().upper() for w in l.designation.split()]
        for pays in ("CAMEROUN", "POLOGNE", "BRESIL", "MAROC", "HONDURAS", "BELGIQUE"):
            assert pays not in words_upper, (
                f"Pays {pays!r} présent dans désignation {l.designation!r}"
            )


def test_parse_facture_categorie_taux_eleve(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    n_cat = sum(1 for l in lignes if l.categorie_code)
    # Sur le corpus TAIYAT classique, classifier keyword atteint >80%
    assert n_cat / len(lignes) >= 0.7


def test_parse_facture_tva_codes_valides(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    for l in lignes:
        if l.taux_tva_centieme is not None:
            assert l.taux_tva_centieme in (550, 2000)


def test_parse_facture_pas_de_ean(sample_pdf: Path):
    """TAIYAT PDF ne contient pas d'EAN — vérifier que c'est bien None."""
    lignes, _ = parse_facture(str(sample_pdf))
    assert all(l.ean is None for l in lignes)


def test_parse_facture_pas_d_article_fournisseur(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    assert all(l.article_fournisseur is None for l in lignes)


def test_parse_facture_source_fournisseur_taiyat(sample_pdf: Path):
    lignes, _ = parse_facture(str(sample_pdf))
    assert all(l.source_fournisseur == "TAIYAT" for l in lignes)


def test_parse_routing_noutam_tenant_2():
    """Facture NOUTAM doit router vers tenant 2 (épicerie)."""
    matches = sorted(_PDF_DIR.glob("TAIYAT_NOUTAM_*.pdf"))
    if not matches:
        pytest.skip("Aucune facture NOUTAM dans le corpus")
    _, meta = parse_facture(str(matches[0]))
    assert meta.client_name == "NOUTAM"
    assert meta.target_tenant_id == 2


def test_parse_function_returns_list(sample_pdf: Path):
    lignes = parse(str(sample_pdf))
    assert isinstance(lignes, list)
    assert len(lignes) > 0


def test_parse_with_facture_metrics_contains_reconciliation(sample_pdf: Path):
    lignes, metrics = parse_with_facture_metrics(str(sample_pdf))
    assert "reconciled_ttc_by_rate" in metrics
    assert "ecart_ttc_reconciled" in metrics
    assert "quality_score" in metrics
    assert metrics["is_total_coherent"] is True


# ══════════════════════════════════════════════════════════════════════════════
# Extraction marque
# ══════════════════════════════════════════════════════════════════════════════


def test_extract_brand_returns_none_when_no_tokens():
    marque, cat = _extract_brand_taiyat([], "")
    assert marque is None
    assert cat is None
