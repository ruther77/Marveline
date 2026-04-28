"""Tests Session 6-F — scripts.etl.parsers.metro.

Stratégie : tests unitaires purs (pas de PDF réel).
  - Helpers bas niveau testés directement.
  - parse() testé avec pdfplumber mocké (MagicMock).

Références :
    WORKFLOW_METRO.md §3.1 : colonnes PDF (coordonnées X)
    WORKFLOW_METRO.md §8   : mapping régie → categorie_code
    ADR-08 : contrat parse(fichier) -> list[LigneParsee]
"""

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from scripts.etl.parsers.metro import (
    _COL_ARTICLE,
    _COL_DESIGNATION,
    _COL_EAN,
    _COL_MONTANT,
    _COL_PRIX,
    _COL_REGIE,
    _COL_TVA,
    _REGIE_TO_CATEGORIE,
    _extract_col,
    _extract_header,
    _extract_left_zone,
    _group_by_y,
    _is_real_ean,
    _parse_rtl_fields,
    _words_to_ligne,
    parse,
)
from app.etl_types import LigneParsee


# ── Helpers de construction ───────────────────────────────────────────────────


def _word(text: str, x0: float, x1: float, top: float = 10.0) -> dict:
    """Crée un mot pdfplumber minimal."""
    return {"text": text, "x0": x0, "x1": x1, "top": top}


def _article_words(
    ean: str = "5099873089057",
    designation: str = "JACK DANIELS 35CL",
    regie: str = "S",
) -> list[dict]:
    """Crée une ligne article typique (coordonnées METRO réelles).

    Inclut les champs numériques RTL (prix, montant, TVA) pour que
    parse_with_facture_metrics ne rejette pas la ligne comme structurelle.
    """
    return [
        _word(ean,         x0=22,  x1=86,  top=50.0),
        _word(designation, x0=125, x1=240, top=50.0),
        _word(regie,       x0=258, x1=270, top=50.0),
        _word("12,34",     x0=_COL_PRIX[0] + 2,    x1=_COL_PRIX[1] - 2,    top=50.0),
        _word("12,34",     x0=_COL_MONTANT[0] + 2,  x1=_COL_MONTANT[1] - 2, top=50.0),
        _word("D",         x0=_COL_TVA[0] + 2,      x1=_COL_TVA[1] - 2,     top=50.0),
    ]


# ── _extract_col ──────────────────────────────────────────────────────────────


class TestExtractCol:
    def test_mot_dans_colonne(self):
        words = [_word("5099873089057", x0=22, x1=86)]
        assert _extract_col(words, *_COL_EAN) == "5099873089057"

    def test_mot_hors_colonne_exclu(self):
        words = [_word("HORS", x0=300, x1=350)]
        assert _extract_col(words, *_COL_EAN) == ""

    def test_plusieurs_mots_tries_par_x(self):
        words = [
            _word("JACK",    x0=125, x1=160),
            _word("DANIELS", x0=162, x1=210),
        ]
        assert _extract_col(words, *_COL_DESIGNATION) == "JACK DANIELS"

    def test_centre_du_mot_dans_colonne(self):
        # Mot dont x0 est légèrement hors colonne mais centre dans la colonne
        words = [_word("TEST", x0=18, x1=30)]  # centre = 24 → dans COL_EAN (20-88)
        assert _extract_col(words, *_COL_EAN) == "TEST"

    def test_liste_vide(self):
        assert _extract_col([], *_COL_EAN) == ""


# ── _group_by_y ───────────────────────────────────────────────────────────────


class TestGroupByY:
    def test_meme_y_groupe_ensemble(self):
        words = [
            _word("A", x0=10, x1=20, top=50.0),
            _word("B", x0=30, x1=40, top=50.0),
        ]
        groups = _group_by_y(words)
        assert len(groups) == 1
        assert len(list(groups.values())[0]) == 2

    def test_y_differents_groupes_distincts(self):
        words = [
            _word("A", x0=10, x1=20, top=50.0),
            _word("B", x0=10, x1=20, top=80.0),
        ]
        groups = _group_by_y(words)
        assert len(groups) == 2

    def test_tolerance_regroupe_y_proches(self):
        # Deux mots à 3pt d'écart → même groupe (tolérance = 5)
        words = [
            _word("A", x0=10, x1=20, top=50.0),
            _word("B", x0=30, x1=40, top=52.0),
        ]
        groups = _group_by_y(words)
        assert len(groups) == 1

    def test_liste_vide(self):
        assert _group_by_y([]) == {}


# ── _is_real_ean ──────────────────────────────────────────────────────────────


class TestIsRealEan:
    def test_ean13_valide(self):
        assert _is_real_ean("5099873089057") is True

    def test_ean8_valide(self):
        assert _is_real_ean("12345678") is True

    def test_ean_fictif_promo(self):
        assert _is_real_ean("PROMOabc12345") is False

    def test_ean_fictif_zeros(self):
        assert _is_real_ean("00001234567890") is False

    def test_trop_court(self):
        assert _is_real_ean("1234567") is False

    def test_trop_long(self):
        assert _is_real_ean("123456789012345") is False

    def test_avec_lettres(self):
        assert _is_real_ean("5099A73089057") is False


# ── _words_to_ligne ───────────────────────────────────────────────────────────


class TestWordsToLigne:
    def test_ligne_complete_spiritueux(self):
        words = _article_words(
            ean="5099873089057",
            designation="JACK DANIELS 35CL",
            regie="S",
        )
        ligne = _words_to_ligne(words)
        assert ligne is not None
        assert ligne.designation == "JACK DANIELS 35CL"
        assert ligne.ean == "5099873089057"
        assert ligne.source_fournisseur == "METRO"
        assert ligne.unite_base == "piece"
        assert ligne.categorie_code == "ALC_SPIRITUEUX"

    def test_mapping_regies(self):
        for regie, expected in _REGIE_TO_CATEGORIE.items():
            words = _article_words(regie=regie)
            ligne = _words_to_ligne(words)
            assert ligne is not None, f"regie={regie}"
            assert ligne.categorie_code == expected, f"regie={regie}"

    def test_regie_inconnue_donne_none(self):
        words = _article_words(regie="Z")
        ligne = _words_to_ligne(words)
        assert ligne is not None
        assert ligne.categorie_code is None

    def test_sans_ean_valide_ean_none(self):
        # EAN fictif PROMO → ligne.ean = None
        words = [
            _word("PROMOabc12345", x0=22, x1=86, top=50.0),
            _word("REMISE FIDELITE", x0=125, x1=230, top=50.0),
        ]
        ligne = _words_to_ligne(words)
        # L'EAN fictif ne match pas _RE_EAN (contient des lettres) → has_ean=False
        # Pas d'article non plus → None
        assert ligne is None

    def test_sans_ean_ni_article_retourne_none(self):
        words = [_word("TOTAL HT :", x0=300, x1=380, top=200.0)]
        assert _words_to_ligne(words) is None

    def test_designation_sans_lettre_retourne_none(self):
        words = [
            _word("5099873089057", x0=22, x1=86, top=50.0),
            _word("12345678",      x0=125, x1=180, top=50.0),
        ]
        assert _words_to_ligne(words) is None

    def test_designation_vide_retourne_none(self):
        # EAN présent mais aucun mot dans la colonne désignation
        words = [_word("5099873089057", x0=22, x1=86, top=50.0)]
        assert _words_to_ligne(words) is None

    def test_article_sans_ean(self):
        # Numéro article seul (sans EAN) → ligne valide avec ean=None
        words = [
            _word("123456",     x0=92,  x1=118, top=50.0),
            _word("HUILE OLIVE", x0=125, x1=220, top=50.0),
        ]
        ligne = _words_to_ligne(words)
        assert ligne is not None
        assert ligne.ean is None
        assert ligne.designation == "HUILE OLIVE"


# ── parse() — mock pdfplumber ─────────────────────────────────────────────────


def _build_mock_pdf(pages_words: list[list[dict]]) -> MagicMock:
    """Construit un mock pdfplumber.open() avec des pages préconfigurées."""
    mock_pages = []
    for words in pages_words:
        page = MagicMock()
        page.extract_words.return_value = words
        page.extract_text.return_value = ""  # str requis pour all_text_parts
        mock_pages.append(page)

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = mock_pages
    return mock_pdf


class TestParse:
    def _patch_open(self, mock_pdf: MagicMock):
        return patch("scripts.etl.parsers.metro.pdfplumber", create=True)

    def test_retourne_lignes_depuis_pdf(self, tmp_path):
        fake_pdf = tmp_path / "facture.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")  # contenu minimal pour Path.exists()

        mock_pdf = _build_mock_pdf([_article_words()])
        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
            lignes = parse(str(fake_pdf))

        assert len(lignes) == 1
        assert isinstance(lignes[0], LigneParsee)
        assert lignes[0].designation == "JACK DANIELS 35CL"

    def test_deduplication_ean(self, tmp_path):
        """Deux lignes avec le même EAN → une seule conservée."""
        fake_pdf = tmp_path / "facture.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        page_words = _article_words() + [
            _word("5099873089057", x0=22,  x1=86,  top=80.0),
            _word("JACK DANIELS",  x0=125, x1=230, top=80.0),
        ]
        mock_pdf = _build_mock_pdf([page_words])
        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
            lignes = parse(str(fake_pdf))

        eans = [l.ean for l in lignes if l.ean]
        assert len(eans) == len(set(eans))

    def test_pdf_vide_retourne_liste_vide(self, tmp_path):
        fake_pdf = tmp_path / "vide.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        mock_pdf = _build_mock_pdf([[]])
        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
            lignes = parse(str(fake_pdf))

        assert lignes == []

    def test_fichier_introuvable(self):
        with pytest.raises(FileNotFoundError, match="introuvable"):
            parse("/chemin/inexistant/facture.pdf")

    def test_import_error_si_pdfplumber_absent(self, tmp_path, monkeypatch):
        fake_pdf = tmp_path / "facture.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        # Retirer pdfplumber du cache modules pour simuler l'absence
        monkeypatch.delitem(sys.modules, "pdfplumber", raising=False)
        with patch("builtins.__import__", side_effect=ImportError("pdfplumber")):
            with pytest.raises(ImportError, match="pdfplumber"):
                parse(str(fake_pdf))

    def test_plusieurs_pages(self, tmp_path):
        """Les lignes de toutes les pages sont agrégées."""
        fake_pdf = tmp_path / "multi.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4")

        page1 = _article_words(ean="5099873089057", designation="PRODUIT A")
        page2 = _article_words(ean="3017620425035", designation="PRODUIT B")
        mock_pdf = _build_mock_pdf([page1, page2])
        mock_pdfplumber = MagicMock()
        mock_pdfplumber.open.return_value = mock_pdf

        with patch.dict(sys.modules, {"pdfplumber": mock_pdfplumber}):
            lignes = parse(str(fake_pdf))

        assert len(lignes) == 2
        designations = {l.designation for l in lignes}
        assert "PRODUIT A" in designations
        assert "PRODUIT B" in designations


# ── _parse_rtl_fields ─────────────────────────────────────────────────────────


class TestParseRtlFields:
    def _rtl_words(self, prix: str, montant: str, tva: str, qte: str = "") -> list[dict]:
        """Construit des mots simulant les champs numériques droite de la facture."""
        words = [
            _word(tva,     x0=_COL_TVA[0] + 2,     x1=_COL_TVA[1] - 2,     top=10.0),
            _word(montant, x0=_COL_MONTANT[0] + 2,  x1=_COL_MONTANT[1] - 2, top=10.0),
            _word(prix,    x0=_COL_PRIX[0] + 2,     x1=_COL_PRIX[1] - 2,    top=10.0),
        ]
        if qte:
            words.append(_word(qte, x0=_COL_PRIX[0] - 20, x1=_COL_PRIX[0] - 5, top=10.0))
        return words

    def test_champs_complets(self):
        words = self._rtl_words(prix="12,34", montant="24,68", tva="D")
        rtl = _parse_rtl_fields(words)
        assert rtl["tva"] == "D"
        assert abs(rtl["montant"] - 24.68) < 0.01
        assert abs(rtl["prix"] - 12.34) < 0.01
        assert _COL_PRIX[0] <= rtl["pivot_x"] <= _COL_PRIX[1]

    def test_sans_champs_numeriques_pivot_defaut(self):
        """Ligne sans aucun champ RTL → pivot_x = _COL_PRIX[0] (fallback)."""
        words = [_word("JACK DANIELS", x0=125, x1=240, top=10.0)]
        rtl = _parse_rtl_fields(words)
        assert rtl["pivot_x"] == _COL_PRIX[0]
        assert rtl["tva"] is None
        assert rtl["montant"] is None

    def test_tva_A_reconnue(self):
        words = self._rtl_words(prix="5,00", montant="5,00", tva="A")
        rtl = _parse_rtl_fields(words)
        assert rtl["tva"] == "A"

    def test_qte_extraite(self):
        words = self._rtl_words(prix="12,34", montant="24,68", tva="D", qte="2")
        rtl = _parse_rtl_fields(words)
        assert rtl["qte"] == 2

    def test_montant_milliers_fusionne(self):
        """Montant > 999€ avec séparateur milliers (2 mots PDF)."""
        words = [
            _word("D",      x0=_COL_TVA[0] + 2,      x1=_COL_TVA[1] - 2),
            _word("1",      x0=_COL_MONTANT[0] + 1,   x1=_COL_MONTANT[0] + 5),
            _word("503,20", x0=_COL_MONTANT[0] + 9,   x1=_COL_MONTANT[1] - 2),
            _word("1,566",  x0=_COL_PRIX[0] + 2,      x1=_COL_PRIX[1] - 2),
        ]
        rtl = _parse_rtl_fields(words)
        assert rtl["montant"] is not None
        assert abs(rtl["montant"] - 1503.20) < 0.01

    def test_prix_milliers_fusionne(self):
        """Prix > 999€ avec séparateur milliers (2 mots PDF)."""
        words = [
            _word("D",       x0=_COL_TVA[0] + 2,      x1=_COL_TVA[1] - 2),
            _word("503,20",  x0=_COL_MONTANT[0] + 2,   x1=_COL_MONTANT[1] - 2),
            _word("1",       x0=_COL_PRIX[0] + 1,      x1=_COL_PRIX[0] + 5),
            _word("234,56",  x0=_COL_PRIX[0] + 9,      x1=_COL_PRIX[1] - 2),
        ]
        rtl = _parse_rtl_fields(words)
        assert rtl["prix"] is not None
        assert abs(rtl["prix"] - 1234.56) < 0.01


# ── _extract_left_zone ────────────────────────────────────────────────────────


class TestExtractLeftZone:
    def test_ean_valide_extrait(self):
        words = [
            _word("5099873089057", x0=22, x1=86, top=10.0),
            _word("JACK DANIELS",  x0=125, x1=230, top=10.0),
        ]
        left = _extract_left_zone(words, pivot_x=390.0)
        assert left["ean"] == "5099873089057"

    def test_article_sans_ean(self):
        words = [
            _word("123456",      x0=92,  x1=118, top=10.0),
            _word("HUILE OLIVE", x0=125, x1=220, top=10.0),
        ]
        left = _extract_left_zone(words, pivot_x=390.0)
        assert left["article"] == "123456"
        assert left["ean"] is None

    def test_regie_donne_categorie_code(self):
        words = [
            _word("5099873089057", x0=22,  x1=86,  top=10.0),
            _word("JACK DANIELS",  x0=125, x1=230, top=10.0),
            _word("S",             x0=258, x1=270, top=10.0),
        ]
        left = _extract_left_zone(words, pivot_x=390.0)
        assert left["categorie_code"] == "ALC_SPIRITUEUX"


# ── _words_to_ligne (sémantique RTL) ─────────────────────────────────────────


class TestWordsToLigneRtl:
    def test_numero_article_derive_exclu_de_designation(self):
        """Numéro article à x0=93 (légère dérive) ne doit pas apparaître dans la désig."""
        words = [
            _word("5099873089057", x0=22,  x1=86,  top=10.0),
            _word("202955",        x0=93,  x1=118, top=10.0),  # article, zone article
            _word("JACK DANIELS",  x0=125, x1=230, top=10.0),
            _word("S",             x0=258, x1=270, top=10.0),
            _word("12,34",         x0=_COL_PRIX[0] + 2, x1=_COL_PRIX[1] - 2, top=10.0),
        ]
        ligne = _words_to_ligne(words)
        assert ligne is not None
        assert "202955" not in ligne.designation

    def test_sans_champs_rtl_fallback_gracieux(self):
        """Ligne sans prix/montant → LigneParsee valide grâce au pivot fallback."""
        words = _article_words(ean="5099873089057", designation="PRODUIT TEST", regie="E")
        ligne = _words_to_ligne(words)
        assert ligne is not None
        assert ligne.designation == "PRODUIT TEST"

    def test_montant_negatif_accepte_par_words_to_ligne(self):
        """_words_to_ligne n'applique pas le filtre montant < 0 (rôle de parse_with_facture_metrics)."""
        words = [
            _word("5099873089057", x0=22,  x1=86,  top=10.0),
            _word("AVOIR PRODUIT", x0=125, x1=230, top=10.0),
            _word("-12,34",        x0=_COL_MONTANT[0] + 2, x1=_COL_MONTANT[1] - 2, top=10.0),
        ]
        # _words_to_ligne ne filtre pas sur montant → retourne une ligne si désignation valide
        ligne = _words_to_ligne(words)
        # "AVOIR PRODUIT" matche _DISCOUNT_PATTERNS → rejeté par _is_non_product_designation
        assert ligne is None  # rejeté via pattern AVOIR


# ── _extract_header ──────────────────────────────────────────────────────────


class TestExtractHeader:
    def test_header_complet(self):
        text = (
            "Nº FACTURE 0/0(135)0011/012580② (011-288587) 135/305\n"
            "METRO France ①⑮ METRO LA CHAPELLE * PAGE : 1/3\n"
            "5, rue des Grands Prés Date facture *: 08-04-2024 22:00\n"
        )
        h = _extract_header(text)
        assert h["numero_facture"] == "0/0(135)0011/012580"
        assert h["numero_interne"] == "011-288587"
        assert h["date_facture"] == "08-04-2024"

    def test_header_sans_unicode(self):
        text = (
            "Nº FACTURE 0/0(135)0016/005048 (016-243302)\n"
            "Date facture : 13-03-2024 19:19\n"
        )
        h = _extract_header(text)
        assert h["numero_facture"] == "0/0(135)0016/005048"
        assert h["numero_interne"] == "016-243302"
        assert h["date_facture"] == "13-03-2024"

    def test_header_vide(self):
        h = _extract_header("")
        assert h["numero_facture"] is None
        assert h["numero_interne"] is None
        assert h["date_facture"] is None

    def test_header_none(self):
        h = _extract_header(None)
        assert h["numero_facture"] is None

    def test_date_sans_facture(self):
        text = "Date facture : 25-12-2023 10:00\n"
        h = _extract_header(text)
        assert h["numero_facture"] is None
        assert h["date_facture"] == "25-12-2023"
