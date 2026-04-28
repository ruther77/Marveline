"""Tests unitaires pour _normaliser() de sync_catalogue_to_epicerie.

Couvre :
  - Suppression poids/volumes (GR, KG, CL, L, ML)
  - Suppression conditionnement (SAC, BOITE, LOT DE, PACK)
  - Suppression multiplicateurs (X12, X 24)
  - Suppression codes article numériques en tête
  - Suppression mots-bruit fournisseur (METRO, REF, ART.)
  - Title case intelligent (préserve AOC, BIO, IGP)
  - Cas limites (vide, espaces, tout supprimé)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.etl.sync_catalogue_to_epicerie import _normaliser


class TestNormaliserPoidsVolumes:
    """Suppression des quantités + unités de poids/volume."""

    def test_grammes(self) -> None:
        assert _normaliser("PAIN BAGUETTE TRADITION 600 GR") == "Pain Baguette Tradition"

    def test_grammes_colles(self) -> None:
        assert _normaliser("FARINE T55 1000GR") == "Farine T55"

    def test_kilogrammes(self) -> None:
        assert _normaliser("RIZ BASMATI 5KG") == "Riz Basmati"

    def test_kilogrammes_decimal(self) -> None:
        assert _normaliser("HUILE D OLIVE VIERGE EXTRA 1.5KG") == "Huile d Olive Vierge Extra"

    def test_centilitres(self) -> None:
        assert _normaliser("COCA COLA CHERRY 33CL") == "Coca Cola Cherry"

    def test_litres(self) -> None:
        assert _normaliser("HUILE D OLIVE VIERGE EXTRA 5L") == "Huile d Olive Vierge Extra"

    def test_millilitres(self) -> None:
        assert _normaliser("GEL DOUCHE LAVANDE 250 ML") == "Gel Douche Lavande"

    def test_grammes_g_seul(self) -> None:
        assert _normaliser("SUCRE EN POUDRE 1000G") == "Sucre En Poudre"


class TestNormaliserConditionnement:
    """Suppression des contenants et conditionnements."""

    def test_le_sac(self) -> None:
        assert _normaliser("PAIN BAGUETTE TRADITION LE SAC 600 GR") == "Pain Baguette Tradition"

    def test_boite(self) -> None:
        assert _normaliser("THON ALBACORE BOITE 200GR") == "Thon Albacore"

    def test_boite_de_n(self) -> None:
        assert _normaliser("OEUFS PLEIN AIR BOITE DE 12") == "Oeufs Plein Air"

    def test_lot_de_n(self) -> None:
        assert _normaliser("SERVIETTE PAPIER 2 PLIS LOT DE 3") == "Serviette Papier 2 Plis"

    def test_pack(self) -> None:
        assert _normaliser("EAU MINERALE PACK 6") == "Eau Minerale"

    def test_bidon(self) -> None:
        assert _normaliser("LESSIVE LIQUIDE BIDON 4L") == "Lessive Liquide"

    def test_barquette(self) -> None:
        assert _normaliser("VIANDE HACHEE BARQUETTE 500GR") == "Viande Hachee"

    def test_sachet(self) -> None:
        assert _normaliser("THE VERT SACHET 100GR") == "The Vert"


class TestNormaliserMultiplicateurs:
    """Suppression des multiplicateurs X12, X 24."""

    def test_x_colle(self) -> None:
        assert _normaliser("COCA COLA 33CL X24") == "Coca Cola"

    def test_x_espace(self) -> None:
        assert _normaliser("YAOURT NATURE X 12") == "Yaourt Nature"

    def test_x_minuscule(self) -> None:
        assert _normaliser("COMPOTE POMME x6") == "Compote Pomme"


class TestNormaliserCodesArticle:
    """Suppression des codes article numériques en tête."""

    def test_code_6_chiffres(self) -> None:
        assert _normaliser("123456 PAIN DE MIE COMPLET") == "Pain De Mie Complet"

    def test_code_7_chiffres(self) -> None:
        assert _normaliser("1234567 BEURRE DOUX") == "Beurre Doux"

    def test_pas_de_code_court(self) -> None:
        """Les nombres courts (< 4 chiffres) ne sont pas des codes article."""
        result = _normaliser("12 OEUFS BIO")
        assert "Oeufs" in result


class TestNormaliserMotsBruit:
    """Suppression des mots-bruit fournisseur."""

    def test_metro(self) -> None:
        assert _normaliser("METRO PAIN COMPLET") == "Pain Complet"

    def test_ref(self) -> None:
        assert _normaliser("CAFE ARABICA REF 4521") == "Cafe Arabica"

    def test_art_point(self) -> None:
        assert _normaliser("ART. PAIN COMPLET") == "Pain Complet"


class TestNormaliserTitleCase:
    """Title case intelligent avec préservation des sigles."""

    def test_basic_title_case(self) -> None:
        assert _normaliser("FROMAGE COMTE") == "Fromage Comte"

    def test_preserve_aoc(self) -> None:
        assert _normaliser("FROMAGE COMTE AOC") == "Fromage Comte AOC"

    def test_preserve_bio(self) -> None:
        assert _normaliser("LENTILLES VERTES BIO") == "Lentilles Vertes BIO"

    def test_preserve_igp(self) -> None:
        assert _normaliser("SAUCISSE DE TOULOUSE IGP") == "Saucisse De Toulouse IGP"

    def test_preserve_aop(self) -> None:
        assert _normaliser("BEURRE CHARENTES POITOU AOP") == "Beurre Charentes Poitou AOP"


class TestNormaliserCasLimites:
    """Cas limites et edge cases."""

    def test_vide(self) -> None:
        assert _normaliser("") == ""

    def test_espaces(self) -> None:
        assert _normaliser("   ") == ""

    def test_espaces_multiples(self) -> None:
        result = _normaliser("PAIN    BAGUETTE    TRADITION")
        assert result == "Pain Baguette Tradition"

    def test_tout_supprime_fallback(self) -> None:
        """Si tout est supprimé, fallback sur le texte nettoyé original."""
        result = _normaliser("600 GR")
        assert result != ""

    def test_troncature_255(self) -> None:
        long_text = "MOT " * 100
        result = _normaliser(long_text)
        assert len(result) <= 255

    def test_designation_realiste_metro(self) -> None:
        """Cas réaliste complet : code + désignation + contenant + poids."""
        result = _normaliser("654321 HUILE OLIVE VIERGE EXTRA LE BIDON 5L")
        assert result == "Huile Olive Vierge Extra"

    def test_combinaison_complexe(self) -> None:
        result = _normaliser("COCA COLA CHERRY BOITE 33CL X24")
        assert result == "Coca Cola Cherry"
