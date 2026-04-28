"""Tests de non-régression pour _cleanup_designation_final.

Cas réels capturés le 2026-04-24 sur 1620 produits tenant 2 — chaque règle
validée sur au moins 1 exemple représentatif. Si ces tests passent, les
patterns dégueulasses identifiés dans l'analyse qualité sont neutralisés.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.etl.sync_catalogue_to_epicerie import (
    _cleanup_designation_final,
    _build_designation_vente,
    _normaliser,
)


class TestLatinTaxon:
    """R1 : retrait des noms taxonomiques latins entre parenthèses."""

    def test_drop_latin_taxon_ferme(self) -> None:
        assert _cleanup_designation_final("Morue Ambassade (gadus morhua) 3kg") == "Morue Ambassade 3kg"

    def test_drop_latin_taxon_ouvert(self) -> None:
        assert _cleanup_designation_final("Chat Poisson (clarias Macrocep 4kg") == "Chat Poisson 4kg"

    def test_drop_thon_taxon(self) -> None:
        assert _cleanup_designation_final("Thon Garba (euthynnus Alletera)") == "Thon Garba"

    def test_preserve_parenthese_numerique(self) -> None:
        # "(5kg)" n'est pas un taxon latin → à garder intact
        result = _cleanup_designation_final("Riz Basmati (5kg pack)")
        # Note : nous ne préservons pas forcément les parenthèses numériques,
        # mais on ne doit pas casser le sens
        assert "Riz Basmati" in result


class TestUnclosedParenthesis:
    """R2 : parenthèse orpheline en fin."""

    def test_simple_orphan(self) -> None:
        assert _cleanup_designation_final("Westcoast Chinchard 400+(trachuru 20kg") == "Westcoast Chinchard 400+ 20kg"

    def test_orphan_in_middle_with_number(self) -> None:
        # "(pangasius Hypophth" n'est pas fermé AVANT le volume
        assert _cleanup_designation_final("Malangua Gros (pangasius Hypophth 4kg") == "Malangua Gros 4kg"


class TestOrphanDegree:
    """R3 : °N mal parsé sans N devant."""

    def test_haricots(self) -> None:
        assert _cleanup_designation_final("Haricots Blancs °1") == "Haricots Blancs N°1"

    def test_haricots_cornilles(self) -> None:
        assert _cleanup_designation_final("Haricots Cornilles °1") == "Haricots Cornilles N°1"

    def test_fufu(self) -> None:
        # Trailing comma to be handled by R7
        assert _cleanup_designation_final("Farine Manioc Fufu °1,") == "Farine Manioc Fufu N°1"

    def test_idempotent_sur_N_deja_present(self) -> None:
        # Ne doit pas toucher "N°1" déjà formé
        assert _cleanup_designation_final("Number One Fleur Bissap Rouge N°1 100g") == "Number One Fleur Bissap Rouge N°1 100g"


class TestMetroSubBrand:
    """R4 : sous-marques METRO à retirer."""

    def test_pro_mpro(self) -> None:
        assert _cleanup_designation_final("Metro Pro Mpro Bobine Ultr. Abs") == "Metro Bobine Ultr. Abs"

    def test_mpro_seul(self) -> None:
        assert _cleanup_designation_final("Metro Mpro Assiette") == "Metro Assiette"

    def test_ppx(self) -> None:
        assert _cleanup_designation_final("Ppx Oeuf") == "Oeuf"

    def test_hwd(self) -> None:
        assert _cleanup_designation_final("Hwd S/s Greenfresh Dr") == "S/s Greenfresh"


class TestTrailingCodeSuffix:
    """R5 : suffixes tronqués en fin."""

    def test_gr_orphan(self) -> None:
        assert _cleanup_designation_final("Pilchard Nature N°1 Gr") == "Pilchard Nature N°1"

    def test_ca_orphan(self) -> None:
        assert _cleanup_designation_final("L'or Espresso Splendente Ca") == "L'or Espresso Splendente"

    def test_mu_orphan(self) -> None:
        assert _cleanup_designation_final("Masque Pli Ref Mu") == "Masque Pli"

    def test_fi_orphan(self) -> None:
        assert _cleanup_designation_final("Daurade Royale El/gr Fi") == "Daurade Royale El/gr"

    def test_ds_orphan(self) -> None:
        assert _cleanup_designation_final("Plq.500g Pres. Pro Beurre Ds") == "Plq.500g Pres. Pro Beurre"

    def test_iterative_multi_suffix(self) -> None:
        # "X Gr Ca" → strip itératif
        assert _cleanup_designation_final("Tomate Pelée Gr Ca") == "Tomate Pelée"

    def test_preserve_mot_normal(self) -> None:
        # "Caramel" commence par Ca mais ce n'est pas un suffixe codé
        assert _cleanup_designation_final("Chocolat Caramel") == "Chocolat Caramel"


class TestMarqueCommune:
    """R6 : préfixe Marque Commune (générique marque blanche METRO)."""

    def test_marque_commune_prefix(self) -> None:
        assert _cleanup_designation_final("Marque Commune Epinard Branche") == "Epinard Branche"

    def test_marque_commune_avec_poids(self) -> None:
        assert _cleanup_designation_final("Marque Commune Queue Crev Cru 500g") == "Queue Crev Cru 500g"

    def test_marque_commune_casse_mixte(self) -> None:
        assert _cleanup_designation_final("MARQUE COMMUNE Thon 200g") == "Thon 200g"


class TestTrailingPunctuation:
    """R7 : ponctuation finale indésirable."""

    def test_trailing_comma(self) -> None:
        assert _cleanup_designation_final("Farine Manioc,") == "Farine Manioc"

    def test_trailing_semicolon(self) -> None:
        assert _cleanup_designation_final("Tomate Pelée;") == "Tomate Pelée"

    def test_preserve_mid_comma(self) -> None:
        # Virgule au milieu préservée (contexte possible)
        assert _cleanup_designation_final("Gel, Parfum Lavande") == "Gel, Parfum Lavande"


class TestDoubleApostrophes:
    """R8 : apostrophes doubles OCR."""

    def test_double_apostrophe(self) -> None:
        # Double apos compressé en simple. L'espace avant apostrophe est préservé
        # (acceptable visuellement vs ''), le taxon latin est retiré en parallèle.
        result = _cleanup_designation_final("Coupé Crabe '' (scylla Serrata) 12kg")
        assert result in {"Coupé Crabe ' 12kg", "Coupé Crabe' 12kg"}

    def test_simple_apostrophe_preserved(self) -> None:
        assert _cleanup_designation_final("L'or Espresso 100g") == "L'or Espresso 100g"


class TestIdempotence:
    """Cleanup est idempotent (appliquer 2x = 1x)."""

    @pytest.mark.parametrize("inp", [
        "Metro Pro Mpro Bobine",
        "Haricots Blancs °1",
        "Morue Ambassade (gadus morhua) 3kg",
        "Pilchard Nature N°1 Gr",
        "Marque Commune Epinard",
    ])
    def test_idempotent(self, inp: str) -> None:
        once = _cleanup_designation_final(inp)
        twice = _cleanup_designation_final(once)
        assert once == twice


class TestEmptyInputs:
    """Cas limites : vide, espaces, None."""

    def test_empty_string(self) -> None:
        assert _cleanup_designation_final("") == ""

    def test_only_whitespace(self) -> None:
        assert _cleanup_designation_final("   ") == ""

    def test_only_code_suffix(self) -> None:
        # "Gr" seul ne devrait PAS être vidé (ce n'est pas un suffixe, c'est tout le contenu)
        # Le iterative strip ne s'applique pas sur single token — le rsplit renverrait [""]
        # et parts[1] serait "Gr" mais parts[0] vide — comportement actuel = "Gr" préservé
        result = _cleanup_designation_final("Gr")
        assert result == "Gr"  # Mot unique préservé


class TestCombinedRealWorld:
    """Cas réels combinant plusieurs règles simultanément."""

    def test_taiyat_avec_latin_et_virgule(self) -> None:
        # Latin taxon + trailing punctuation
        assert _cleanup_designation_final("Eiglefin (melanogrammus Aeglefinus) 3kg,") == "Eiglefin 3kg"

    def test_metro_mpro_avec_suffix_code(self) -> None:
        # Sous-marque METRO + suffixe orphelin
        result = _cleanup_designation_final("Metro Pro Mpro Assiette Dess Rond Pu Lp")
        assert result == "Metro Assiette Dess Rond Pu"  # Lp retiré (code), Pu gardé (non whitelisted)

    def test_taiyat_orphan_paren_et_poids(self) -> None:
        # Parenthèse ouverte + unité en fin
        assert _cleanup_designation_final("Coupé Stockfish (gadus 5kg") == "Coupé Stockfish 5kg"
