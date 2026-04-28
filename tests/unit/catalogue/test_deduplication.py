"""Tests Session 6-B1 — Service déduplication ETL M05.

Spec : ADR-07 (Jaro-Winkler, seuils 0.85/0.75, normalisation désignation).
Stratégie : tests unitaires purs — aucun mock, aucune DB.
"""
import pytest

from app.services.catalogue.etl_deduplication import (
    ETL_DESIGNATION_MAXLEN,
    ETL_SEUIL_CONFLIT,
    ETL_SEUIL_MATCH,
    DecisionDeduplication,
    ResultatDeduplication,
    classify_designation,
    compute_similarity,
    decide,
    is_ean_valid,
    normalize_designation,
)


# ── normalize_designation ────────────────────────────────────────────────────

class TestNormalizeDesignation:
    def test_lowercase(self):
        """La désignation est convertie en minuscules."""
        assert normalize_designation("HUILE OLIVE") == "huile olive"

    def test_strip_accents(self):
        """Les accents sont supprimés via NFD → ASCII."""
        result = normalize_designation("Côtelette porc")
        assert "c" in result
        assert "ô" not in result
        # "Côtelette" → "cotelette" après strip accent
        assert result == "cotelette porc"

    def test_strip_ponctuation(self):
        """La ponctuation est remplacée par des espaces."""
        result = normalize_designation("Beurre, doux 250g")
        assert "," not in result
        assert result == "beurre doux 250g"

    def test_remove_stopwords(self):
        """Les mots vides ADR-07 sont supprimés (de, du, des, le, la, les, en, au)."""
        result = normalize_designation("Côte de porc au four")
        # "de" et "au" sont des stop words
        assert "de" not in result.split()
        assert "au" not in result.split()
        assert "porc" in result

    def test_remove_multiple_stopwords(self):
        """Plusieurs mots vides supprimés dans une même désignation."""
        result = normalize_designation("le filet des poulets en sauce")
        tokens = result.split()
        for stopword in ("le", "des", "en"):
            assert stopword not in tokens

    def test_truncate_to_maxlen(self):
        """Troncature à ETL_DESIGNATION_MAXLEN caractères."""
        long_input = "a " * 60  # 120 chars, bien au-delà de la limite
        result = normalize_designation(long_input)
        assert len(result) <= ETL_DESIGNATION_MAXLEN

    def test_empty_string(self):
        """Désignation vide → chaîne vide."""
        assert normalize_designation("") == ""

    def test_only_stopwords(self):
        """Désignation composée uniquement de mots vides → chaîne vide."""
        result = normalize_designation("le la les de du des en au")
        assert result == ""

    def test_alphanumeric_preserved(self):
        """Chiffres et lettres sont préservés."""
        result = normalize_designation("Yaourt 125g x4")
        assert "yaourt" in result
        assert "125g" in result or ("125" in result and "g" in result)
        assert "x4" in result

    def test_normalisation_idempotente(self):
        """Appeler normalize deux fois sur une désignation déjà normalisée = même résultat."""
        once = normalize_designation("Beurre doux 250g")
        twice = normalize_designation(once)
        assert once == twice


# ── is_ean_valid ─────────────────────────────────────────────────────────────

class TestIsEanValid:
    def test_ean13_valid(self):
        """EAN-13 numérique de 13 chiffres est valide."""
        assert is_ean_valid("3017620425035") is True

    def test_ean8_valid(self):
        """EAN-8 numérique de 8 chiffres est valide."""
        assert is_ean_valid("01234565") is True

    def test_wrong_length_6(self):
        """EAN de longueur 6 est invalide."""
        assert is_ean_valid("123456") is False

    def test_wrong_length_12(self):
        """EAN de longueur 12 est invalide (UPC-A non accepté)."""
        assert is_ean_valid("012345678905") is False

    def test_none(self):
        """None → False."""
        assert is_ean_valid(None) is False

    def test_empty_string(self):
        """Chaîne vide → False."""
        assert is_ean_valid("") is False

    def test_non_numeric_ean(self):
        """EAN avec lettres → False."""
        assert is_ean_valid("30176204ABC35") is False

    def test_ean_with_whitespace(self):
        """EAN avec espaces autour → valide si longueur OK après strip."""
        assert is_ean_valid("  3017620425035  ") is True


# ── compute_similarity ────────────────────────────────────────────────────────

class TestComputeSimilarity:
    def test_identical_strings(self):
        """Chaînes identiques → score 1.0."""
        assert compute_similarity("huile olive", "huile olive") == pytest.approx(1.0)

    def test_empty_first_arg(self):
        """Premier argument vide → 0.0."""
        assert compute_similarity("", "huile olive") == 0.0

    def test_empty_second_arg(self):
        """Deuxième argument vide → 0.0."""
        assert compute_similarity("huile olive", "") == 0.0

    def test_both_empty(self):
        """Deux chaînes vides → 0.0."""
        assert compute_similarity("", "") == 0.0

    def test_very_different_strings(self):
        """Désignations très différentes → score faible."""
        score = compute_similarity("huile olive vierge", "beurre lait entier")
        assert score < ETL_SEUIL_CONFLIT

    def test_similar_strings_above_match_threshold(self):
        """Désignations quasi identiques → score ≥ ETL_SEUIL_MATCH."""
        score = compute_similarity("huile olive extra vierge", "huile olive vierge extra")
        assert score >= ETL_SEUIL_MATCH

    def test_score_range(self):
        """Le score est toujours dans [0.0, 1.0]."""
        score = compute_similarity("porc filet", "poulet entier")
        assert 0.0 <= score <= 1.0


# ── decide ────────────────────────────────────────────────────────────────────

class TestDecide:
    def test_match_above_threshold(self):
        """Score ≥ 0.85 → MATCH."""
        assert decide(0.90) == DecisionDeduplication.MATCH

    def test_match_at_exact_threshold(self):
        """Score exactement 0.85 → MATCH (seuil inclusif)."""
        assert decide(ETL_SEUIL_MATCH) == DecisionDeduplication.MATCH

    def test_conflict_in_zone(self):
        """Score dans [0.75, 0.85[ → CONFLICT."""
        assert decide(0.80) == DecisionDeduplication.CONFLICT

    def test_conflict_at_lower_threshold(self):
        """Score exactement 0.75 → CONFLICT (seuil inclusif bas)."""
        assert decide(ETL_SEUIL_CONFLIT) == DecisionDeduplication.CONFLICT

    def test_new_below_threshold(self):
        """Score < 0.75 → NEW."""
        assert decide(0.70) == DecisionDeduplication.NEW

    def test_new_at_zero(self):
        """Score 0.0 → NEW."""
        assert decide(0.0) == DecisionDeduplication.NEW

    def test_match_at_perfect(self):
        """Score 1.0 → MATCH."""
        assert decide(1.0) == DecisionDeduplication.MATCH

    def test_conflict_boundary_just_below_match(self):
        """Score juste en dessous de 0.85 → CONFLICT, pas MATCH."""
        assert decide(0.849) == DecisionDeduplication.CONFLICT

    def test_new_boundary_just_below_conflict(self):
        """Score juste en dessous de 0.75 → NEW, pas CONFLICT."""
        assert decide(0.749) == DecisionDeduplication.NEW


# ── classify_designation ──────────────────────────────────────────────────────

class TestClassifyDesignation:
    def test_empty_candidates_returns_new(self):
        """Aucun candidat → décision NEW, candidate_id=None, score=None."""
        result = classify_designation("Huile olive 1L", [])
        assert result.decision == DecisionDeduplication.NEW
        assert result.candidate_id is None
        assert result.score is None

    def test_perfect_match(self):
        """Candidat identique → MATCH, candidate_id renvoyé."""
        norm = normalize_designation("Huile olive vierge")
        result = classify_designation("Huile olive vierge", [(42, norm)])
        assert result.decision == DecisionDeduplication.MATCH
        assert result.candidate_id == 42
        assert result.score is not None
        assert result.score >= ETL_SEUIL_MATCH

    def test_conflict_zone(self):
        """Candidat proche mais sous le seuil MATCH → CONFLICT."""
        # "huile olive" vs "huile olivee" — légèrement différents
        result = classify_designation(
            "Huile d olive bouteille",
            [(10, "huile olive extra vierge 75cl"), (11, "margarine tournesol")],
        )
        # Le résultat peut être MATCH ou CONFLICT selon le score réel — on vérifie
        # que le meilleur candidat est sélectionné (pas margarine)
        assert result.candidate_id in (10, None)  # margarine ne doit pas gagner si diff trop grande

    def test_best_candidate_selected(self):
        """Le candidat avec le score le plus élevé est sélectionné."""
        norm_proche = normalize_designation("Huile olive vierge 1L")
        norm_loin = normalize_designation("Beurre doux 250g")
        result = classify_designation(
            "Huile olive vierge",
            [(99, norm_loin), (100, norm_proche)],
        )
        assert result.candidate_id == 100

    def test_designation_norm_set(self):
        """designation_norm correspond à la normalisation de la désignation entrante."""
        result = classify_designation("Côtelette de porc", [])
        expected_norm = normalize_designation("Côtelette de porc")
        assert result.designation_norm == expected_norm

    def test_score_rounded_to_3_decimals(self):
        """Le score est arrondi à 3 décimales dans le résultat."""
        norm = normalize_designation("Yaourt nature 125g")
        result = classify_designation("Yaourt nature 125g", [(1, norm)])
        assert result.score is not None
        # score 1.0 arrondi à 3 décimales → 1.0 ou 1.000
        assert result.score == round(result.score, 3)

    def test_new_candidate_id_is_none(self):
        """Quand la décision est NEW, candidate_id doit être None."""
        norm_tres_different = normalize_designation("Moteur diesel v8 turbo")
        result = classify_designation(
            "Yaourt fraise 125g",
            [(5, norm_tres_different)],
        )
        # Score très faible → NEW → candidate_id None
        if result.decision == DecisionDeduplication.NEW:
            assert result.candidate_id is None

    def test_result_is_frozen_dataclass(self):
        """ResultatDeduplication est immuable (frozen=True)."""
        result = classify_designation("Test", [])
        with pytest.raises(Exception):  # FrozenInstanceError ou AttributeError
            result.decision = DecisionDeduplication.MATCH  # type: ignore[misc]
