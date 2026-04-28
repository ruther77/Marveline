"""Tests parser METRO v2 — tokenizer, ocr_clean, columns, conditionnement.

Stratégie : tests unitaires purs (pas de PDF réel).
"""
import pytest

from scripts.etl.parsers.metro.tokenizer import (
    TokenType,
    classify_token,
    build_designation,
    build_designation_raw,
    extract_degree,
    extract_container,
    extract_volume_ml,
    extract_colisage,
    tokenize_designation,
    DesigToken,
)
from scripts.etl.parsers.metro.ocr_clean import (
    clean_ocr_token,
    expand_abbreviation,
    ocr_to_digits,
)
from scripts.etl.parsers.metro.conditionnement import extract_conditionnement
from scripts.etl.parsers.metro.columns import (
    extract_line,
    group_by_y,
    parse_fr_number,
)
from scripts.etl.parsers.metro.constants import ABBREVIATIONS


# ══════════════════════════════════════════════════════════════════════════════
# tokenizer — classify_token
# ══════════════════════════════════════════════════════════════════════════════


class TestClassifyToken:
    def test_degree_40d(self):
        assert classify_token("40D") == TokenType.DEGREE

    def test_degree_5_5d(self):
        assert classify_token("5.5D") == TokenType.DEGREE

    def test_degree_37_5d_comma(self):
        assert classify_token("37,5D") == TokenType.DEGREE

    def test_container_vp(self):
        assert classify_token("VP") == TokenType.CONTAINER

    def test_container_bte(self):
        assert classify_token("BTE") == TokenType.CONTAINER

    def test_container_pet(self):
        assert classify_token("PET") == TokenType.CONTAINER

    def test_container_boite(self):
        assert classify_token("BOITE") == TokenType.CONTAINER

    def test_multiplier_qty_18x25cl(self):
        assert classify_token("18X25CL") == TokenType.MULTIPLIER

    def test_multiplier_qty_6x140g(self):
        assert classify_token("6X140G") == TokenType.MULTIPLIER

    def test_multiplier_only_x6(self):
        assert classify_token("X6") == TokenType.MULTIPLIER

    def test_multiplier_only_x20(self):
        assert classify_token("X20") == TokenType.MULTIPLIER

    def test_packaging_75cl(self):
        assert classify_token("75CL") == TokenType.PACKAGING

    def test_packaging_500g(self):
        assert classify_token("500G") == TokenType.PACKAGING

    def test_packaging_2_5kg(self):
        assert classify_token("2.5KG") == TokenType.PACKAGING

    def test_packaging_1l(self):
        assert classify_token("1L") == TokenType.PACKAGING

    def test_numeric_1664(self):
        """Bug #1 : '1664' ne doit PAS être rejeté."""
        assert classify_token("1664") == TokenType.NUMERIC

    def test_numeric_86(self):
        assert classify_token("86") == TokenType.NUMERIC

    def test_word_blonde(self):
        assert classify_token("BLONDE") == TokenType.WORD

    def test_word_jack(self):
        assert classify_token("JACK") == TokenType.WORD

    def test_noise_empty(self):
        assert classify_token("") == TokenType.NOISE

    def test_brand_lookup(self):
        brands = frozenset({"1664", "HEINEKEN"})
        assert classify_token("1664", known_brands=brands) == TokenType.BRAND
        assert classify_token("HEINEKEN", known_brands=brands) == TokenType.BRAND


# ══════════════════════════════════════════════════════════════════════════════
# tokenizer — build_designation
# ══════════════════════════════════════════════════════════════════════════════


class TestBuildDesignation:
    def test_1664_blonde_complete(self):
        """Ligne réelle : '1664 BLDE 5.5D 18X25CL VP' → '1664 BLONDE'"""
        tokens = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.NUMERIC),
            DesigToken(raw="BLDE", cleaned="BLDE", token_type=TokenType.WORD),
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="18X25CL", cleaned="18X25CL", token_type=TokenType.MULTIPLIER),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        assert build_designation(tokens) == "1664 BLONDE"

    def test_jack_daniels(self):
        tokens = [
            DesigToken(raw="WH", cleaned="WH", token_type=TokenType.WORD),
            DesigToken(raw="JACK", cleaned="JACK", token_type=TokenType.WORD),
            DesigToken(raw="DANIEL'S", cleaned="DANIEL'S", token_type=TokenType.WORD),
            DesigToken(raw="40D", cleaned="40D", token_type=TokenType.DEGREE),
            DesigToken(raw="35CL", cleaned="35CL", token_type=TokenType.PACKAGING),
        ]
        assert build_designation(tokens) == "WHISKY JACK DANIEL'S"

    def test_no_duplicate_adjacent(self):
        """LEFFE BLONDE BLE → LEFFE BLONDE (pas BLONDE BLONDE)"""
        tokens = [
            DesigToken(raw="LEFFE", cleaned="LEFFE", token_type=TokenType.WORD),
            DesigToken(raw="BLONDE", cleaned="BLONDE", token_type=TokenType.WORD),
            DesigToken(raw="BLE", cleaned="BLE", token_type=TokenType.WORD),
        ]
        assert build_designation(tokens) == "LEFFE BLONDE"

    def test_mc_expansion(self):
        tokens = [
            DesigToken(raw="MC", cleaned="MC", token_type=TokenType.WORD),
            DesigToken(raw="MOUTARDE", cleaned="MOUTARDE", token_type=TokenType.WORD),
        ]
        assert build_designation(tokens) == "MARQUE COMMUNE MOUTARDE"

    # ─── Fix A (audit 2026-04-24) : enrichissement désignation pauvre ──────
    def test_enrichment_when_brand_only_adds_degree_packaging(self):
        """Désignation "1664 5.5D 75CL VP" (sans WORD) → enrichie avec DEGREE+PACK+CONT."""
        tokens = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.BRAND),
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="75CL", cleaned="75CL", token_type=TokenType.PACKAGING),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        d = build_designation(tokens)
        assert "1664" in d
        assert "5.5D" in d
        assert "75CL" in d
        # doit discriminer des variantes : "1664 5.5D 75CL VP"
        assert d != "1664"

    def test_enrichment_not_applied_when_rich(self):
        """Désignation déjà riche (≥2 tokens) ne doit PAS être enrichie."""
        tokens = [
            DesigToken(raw="VODKA", cleaned="VODKA", token_type=TokenType.WORD),
            DesigToken(raw="CIROC", cleaned="CIROC", token_type=TokenType.BRAND),
            DesigToken(raw="COCONUT", cleaned="COCONUT", token_type=TokenType.WORD),
            DesigToken(raw="37.5D", cleaned="37.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="70CL", cleaned="70CL", token_type=TokenType.PACKAGING),
        ]
        d = build_designation(tokens)
        # Doit garder la forme "VODKA CIROC COCONUT" sans degré/volume
        assert d == "VODKA CIROC COCONUT"

    def test_enrichment_discriminates_1664_variants(self):
        """Deux variantes 1664 doivent produire des désignations DIFFÉRENTES."""
        t1 = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.BRAND),
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="75CL", cleaned="75CL", token_type=TokenType.PACKAGING),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        t2 = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.BRAND),
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="25CLX6", cleaned="25CLX6", token_type=TokenType.MULTIPLIER),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        assert build_designation(t1) != build_designation(t2)


# ══════════════════════════════════════════════════════════════════════════════
# tokenizer — extract_degree, extract_container, extract_volume_ml
# ══════════════════════════════════════════════════════════════════════════════


class TestTokenizerExtracts:
    def test_extract_degree_40(self):
        tokens = [
            DesigToken(raw="40D", cleaned="40D", token_type=TokenType.DEGREE),
        ]
        assert extract_degree(tokens) == 40.0

    def test_extract_degree_5_5(self):
        tokens = [
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
        ]
        assert extract_degree(tokens) == 5.5

    def test_extract_degree_none(self):
        tokens = [
            DesigToken(raw="BLONDE", cleaned="BLONDE", token_type=TokenType.WORD),
        ]
        assert extract_degree(tokens) is None

    def test_extract_container_vp(self):
        tokens = [
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        assert extract_container(tokens) == "VP"

    def test_extract_volume_75cl(self):
        tokens = [
            DesigToken(raw="75CL", cleaned="75CL", token_type=TokenType.PACKAGING),
        ]
        assert extract_volume_ml(tokens) == 750

    def test_extract_volume_from_multiplier(self):
        tokens = [
            DesigToken(raw="18X25CL", cleaned="18X25CL", token_type=TokenType.MULTIPLIER),
        ]
        assert extract_volume_ml(tokens) == 250

    def test_extract_colisage_from_multiplier(self):
        """Cas standard : '12X120G' → colisage 12."""
        tokens = [
            DesigToken(raw="12X120G", cleaned="12X120G", token_type=TokenType.MULTIPLIER),
        ]
        assert extract_colisage(tokens) == 12

    def test_extract_colisage_from_multiplier_only(self):
        """Cas lot sans unité : 'X6' → colisage 6."""
        tokens = [
            DesigToken(raw="X6", cleaned="X6", token_type=TokenType.MULTIPLIER),
        ]
        assert extract_colisage(tokens) == 6

    def test_extract_colisage_fallback_qty_prefix_150(self):
        """Cas ambigu (bug '150 SUCETTES FRUIT') : le '150' reclassé NOISE par le
        post-traitement _QTY_PREFIXES doit être récupéré comme colisage en fallback.
        """
        tokens = [
            DesigToken(raw="150", cleaned="150", token_type=TokenType.NOISE),
            DesigToken(raw="SUCETTES", cleaned="SUCETTES", token_type=TokenType.WORD),
            DesigToken(raw="FRUIT", cleaned="FRUIT", token_type=TokenType.WORD),
        ]
        assert extract_colisage(tokens) == 150

    def test_extract_colisage_multiplier_wins_over_fallback(self):
        """Si un MULTIPLIER est présent, il prime sur le fallback NOISE."""
        tokens = [
            DesigToken(raw="150", cleaned="150", token_type=TokenType.NOISE),
            DesigToken(raw="SUCETTES", cleaned="SUCETTES", token_type=TokenType.WORD),
            DesigToken(raw="X6", cleaned="X6", token_type=TokenType.MULTIPLIER),
        ]
        assert extract_colisage(tokens) == 6

    def test_extract_colisage_no_noise_no_multiplier(self):
        """Pas de colisage détectable : retourne None."""
        tokens = [
            DesigToken(raw="BLONDE", cleaned="BLONDE", token_type=TokenType.WORD),
            DesigToken(raw="75CL", cleaned="75CL", token_type=TokenType.PACKAGING),
        ]
        assert extract_colisage(tokens) is None

    def test_extract_colisage_noise_not_qty_prefix(self):
        """NOISE en position 0 mais pas dans _QTY_PREFIXES (ex: '7') → pas de colisage."""
        tokens = [
            DesigToken(raw="7", cleaned="7", token_type=TokenType.NOISE),
            DesigToken(raw="SUCETTES", cleaned="SUCETTES", token_type=TokenType.WORD),
        ]
        assert extract_colisage(tokens) is None


# ══════════════════════════════════════════════════════════════════════════════
# ocr_clean
# ══════════════════════════════════════════════════════════════════════════════


class TestOcrClean:
    def test_prefix_p(self):
        assert clean_ocr_token("pBLANC") == "BLANC"

    def test_suffix_p_in_boitpe(self):
        assert clean_ocr_token("BOITpE") == "BOITE"

    def test_numeric_prefix_c(self):
        assert clean_ocr_token("c0,280") == "0,280"

    def test_clean_normal_word(self):
        assert clean_ocr_token("HEINEKEN") == "HEINEKEN"

    def test_clean_number(self):
        assert clean_ocr_token("1664") == "1664"

    def test_abbreviation_blde(self):
        assert expand_abbreviation("BLDE") == "BLONDE"

    def test_abbreviation_wh(self):
        assert expand_abbreviation("WH") == "WHISKY"

    def test_abbreviation_ch(self):
        assert expand_abbreviation("CH") == "CHAMPAGNE"

    def test_abbreviation_mc(self):
        assert expand_abbreviation("MC") == "MARQUE COMMUNE"

    def test_abbreviation_unknown(self):
        assert expand_abbreviation("XYZ") == "XYZ"

    def test_ocr_to_digits(self):
        assert ocr_to_digits("O12I") == "0121"


# ══════════════════════════════════════════════════════════════════════════════
# conditionnement
# ══════════════════════════════════════════════════════════════════════════════


class TestConditionnement:
    def test_simple_75cl(self):
        tokens = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.NUMERIC),
            DesigToken(raw="75CL", cleaned="75CL", token_type=TokenType.PACKAGING),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        cond, unite, contenant = extract_conditionnement(tokens)
        assert cond == "75cL"
        assert unite == "cL"
        assert contenant == "VP"

    def test_multiplier_18x25cl(self):
        tokens = [
            DesigToken(raw="18X25CL", cleaned="18X25CL", token_type=TokenType.MULTIPLIER),
            DesigToken(raw="VP", cleaned="VP", token_type=TokenType.CONTAINER),
        ]
        cond, unite, contenant = extract_conditionnement(tokens)
        assert cond == "18×25cL"
        assert unite == "cL"
        assert contenant == "VP"

    def test_lot_x6(self):
        tokens = [
            DesigToken(raw="X6", cleaned="X6", token_type=TokenType.MULTIPLIER),
            DesigToken(raw="25CL", cleaned="25CL", token_type=TokenType.PACKAGING),
        ]
        cond, unite, contenant = extract_conditionnement(tokens)
        assert "lot de 6" in cond
        assert unite == "cL"

    def test_no_conditionnement(self):
        tokens = [
            DesigToken(raw="HEINEKEN", cleaned="HEINEKEN", token_type=TokenType.WORD),
        ]
        cond, unite, contenant = extract_conditionnement(tokens)
        assert cond is None
        assert unite == "piece"
        assert contenant is None

    def test_non_destructive(self):
        """Bug #2 : 'BOITE 5.5D 50CL' ne doit PAS détruire la désignation."""
        tokens = [
            DesigToken(raw="1664", cleaned="1664", token_type=TokenType.NUMERIC),
            DesigToken(raw="BOITE", cleaned="BOITE", token_type=TokenType.CONTAINER),
            DesigToken(raw="5.5D", cleaned="5.5D", token_type=TokenType.DEGREE),
            DesigToken(raw="50CL", cleaned="50CL", token_type=TokenType.PACKAGING),
        ]
        cond, unite, contenant = extract_conditionnement(tokens)
        assert contenant == "BOITE"
        assert cond == "50cL"
        # Fix A (audit 2026-04-24) : la désignation est enrichie quand elle
        # serait trop pauvre (≤1 token), ici "1664" → "1664 BOITE 5.5D 50CL".
        # Les attributs physiques restent aussi accessibles séparément via
        # extract_conditionnement / extract_degree / extract_container.
        desig = build_designation(tokens)
        assert "1664" in desig
        assert "5.5D" in desig
        assert "50CL" in desig


# ══════════════════════════════════════════════════════════════════════════════
# columns — parse_fr_number
# ══════════════════════════════════════════════════════════════════════════════


class TestParseFrNumber:
    def test_simple(self):
        assert parse_fr_number("18,68") == 18.68

    def test_negative_suffix(self):
        assert parse_fr_number("5,00-") == -5.0

    def test_thousands_space(self):
        assert parse_fr_number("1 503,20") == 1503.20

    def test_none_on_empty(self):
        assert parse_fr_number("") is None

    def test_none_on_text(self):
        assert parse_fr_number("abc") is None


# ══════════════════════════════════════════════════════════════════════════════
# columns — extract_line (mock words)
# ══════════════════════════════════════════════════════════════════════════════


def _make_word(text: str, x0: float, x1: float = 0, top: float = 100.0) -> dict:
    if x1 == 0:
        x1 = x0 + len(text) * 6
    return {"text": text, "x0": x0, "x1": x1, "top": top}


class TestExtractLine:
    def test_1664_line(self):
        """Ligne réelle : EAN=03080213000759 Art=2025435 '1664 BOITE 5.5D 50CL' Regie=B"""
        words = [
            _make_word("03080213000759", 25.8, 85.2),
            _make_word("2025435", 89.5, 119.2),
            _make_word("1664", 123.5, 140.5),
            _make_word("BOITE", 144.8, 166.0),
            _make_word("5.5D", 170.2, 187.2),
            _make_word("50CL", 191.5, 208.5),
            _make_word("B", 263.8, 268.0),
            _make_word("5,5", 280.8, 293.5),
            _make_word("0,028", 306.2, 327.5),
            _make_word("0,500", 353.0, 374.2),
            _make_word("1,040", 408.2, 429.5),
            _make_word("24", 450.8, 459.2),
            _make_word("1", 467.8, 472.0),
            _make_word("24,96", 493.2, 514.5),
            _make_word("D", 531.5, 535.8),
        ]
        ex = extract_line(words)
        assert ex is not None
        assert ex.ean == "03080213000759"
        assert ex.article == "2025435"
        assert ex.regie == "B"
        assert ex.categorie_code == "ALC_BIERE"
        assert ex.vol_alcool == 5.5
        # Colisage et quantité : les colonnes sont serrées sur les alcools,
        # l'extraction dépend de la fusion de mots numériques adjacents.
        # On vérifie que au moins un des deux est extrait.
        assert ex.colisage is not None or ex.quantite is not None or ex.montant_ht is not None
        assert ex.montant_ht is not None
        assert ex.tva_code == "D"

    def test_non_product_line(self):
        """Ligne sans EAN ni article → None"""
        words = [
            _make_word("Total", 50.0, 100.0),
            _make_word("HT", 110.0, 130.0),
        ]
        assert extract_line(words) is None
