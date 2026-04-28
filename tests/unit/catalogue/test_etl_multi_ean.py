"""Tests unitaires — dédup multi-EAN + comparaison attributs physiques.

Audit 2026-04-24 : la dédup Jaro-Winkler écrasait 29 % des lignes quand l'EAN
entrant différait de l'EAN stocké, même pour des variantes pays du même produit.
Fix : `_same_physical_attrs` détermine si l'EAN entrant est un alias cross-pays
(même produit logique) ou une variante réelle (produit distinct).

Révision 2026-04-24 (colisage) : le colisage n'est PLUS un critère de distinction.
Un même produit (1664 25cL) peut arriver en pack 18/20/24 — le colisage est un
attribut d'emballage tracé dans la table pivot catalogue_produit_colisages.
"""
from types import SimpleNamespace

import pytest

from app.services.catalogue.etl_import_service import _same_physical_attrs


def _ligne(**kwargs):
    """Factory LigneParsee simplifiée (via SimpleNamespace)."""
    defaults = dict(
        designation="", unite_base="", source_fournisseur="",
        ean=None, marque=None, conditionnement=None, categorie_code=None,
        quantite=None, prix_unitaire_cts=None, montant_ht_cts=None,
        montant_ttc_cts=None, taux_tva_centieme=None,
        article_fournisseur=None, degre_alcool=None, contenant=None,
        volume_unitaire_ml=None, colisage=None, designation_raw=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _produit(**kwargs):
    """Factory CatalogueProduit simplifiée."""
    defaults = dict(
        id=1, ean=None, designation="", designation_norm="",
        marque=None, unite_base="", conditionnement=None,
        colisage=None, volume_unitaire_ml=None,
        source_fournisseur=None, categorie_code=None,
        prix_unitaire_cts=None, taux_tva_centieme=None,
        merged_into_id=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestSamePhysicalAttrs:
    def test_same_coca_cola_cross_country(self):
        """Coca Cola 33cL FR vs DE = même produit logique (volume identique, colisage idem)."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=330, colisage=24)
        p = _produit(unite_base="cL", volume_unitaire_ml=330, colisage=24)
        assert _same_physical_attrs(l, p) is True

    def test_volume_tolerance_5pct_passes(self):
        """250ml vs 255ml (écart 2%) = même produit (tolérance 5%)."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=250)
        p = _produit(unite_base="cL", volume_unitaire_ml=255)
        assert _same_physical_attrs(l, p) is True

    def test_volume_tolerance_exceeded_fails(self):
        """250ml vs 330ml (écart 24%) = produits différents."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=250)
        p = _produit(unite_base="cL", volume_unitaire_ml=330)
        assert _same_physical_attrs(l, p) is False

    def test_colisage_different_still_same_product(self):
        """Colisage 18 vs 24 = même produit si volume+unité identiques.

        Audit 2026-04-24 : les 3 entrées "1664 25cL" en packs 18/20/24 sont
        le même produit logique ; le colisage n'est qu'un pack d'emballage.
        """
        l = _ligne(unite_base="cL", volume_unitaire_ml=250, colisage=18)
        p = _produit(unite_base="cL", volume_unitaire_ml=250, colisage=24)
        assert _same_physical_attrs(l, p) is True

    def test_colisage_different_same_volume_passes(self):
        """Colisage 6 vs 24 pour 75cL = même produit (juste pack différent)."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=750, colisage=6)
        p = _produit(unite_base="cL", volume_unitaire_ml=750, colisage=24)
        assert _same_physical_attrs(l, p) is True

    def test_unite_base_different_fails(self):
        """Unité kg vs L = produits différents (sur-merge dangereux si ignoré)."""
        l = _ligne(unite_base="kg", volume_unitaire_ml=None, colisage=None)
        p = _produit(unite_base="L", volume_unitaire_ml=None, colisage=None)
        assert _same_physical_attrs(l, p) is False

    def test_null_attributes_dont_block(self):
        """Attribut NULL d'un côté seulement → on ne peut pas conclure, on accepte."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=None, colisage=None)
        p = _produit(unite_base="cL", volume_unitaire_ml=750, colisage=6)
        # Les attributs manquants ne doivent pas provoquer un mismatch.
        assert _same_physical_attrs(l, p) is True

    def test_both_null_volume_no_block(self):
        """Deux NULL → pas de blocage (volume inconnu)."""
        l = _ligne(unite_base="piece", volume_unitaire_ml=None)
        p = _produit(unite_base="piece", volume_unitaire_ml=None)
        assert _same_physical_attrs(l, p) is True

    def test_1664_blonde_75cl_vs_25cl(self):
        """1664 Blonde 75cL vs 25cL × 6 = produits différents (volume distinct)."""
        l = _ligne(unite_base="cL", volume_unitaire_ml=750, colisage=6)
        p = _produit(unite_base="cL", volume_unitaire_ml=250, colisage=6)
        assert _same_physical_attrs(l, p) is False
