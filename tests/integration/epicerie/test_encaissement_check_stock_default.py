"""S1.T3 — Tests F870/EPI-CHECKSTK-01.

Spec : docs/architecture-audit-2026-04-26/execution-plan/10-sprint-1-PROD-FIRE-DRILL.md
       L838-989 (Story S1.T3).

Avant : `EncaissementRequest.check_stock: bool = False` -> caissier oubliait,
vente passait check service-level, atteignait phase 7 (creation mouvement stock),
et PostgreSQL CHECK `stock_apres >= 0` raise IntegrityError 500. UX caissier
degradee : "Erreur serveur 500" au lieu de "Stock insuffisant" (409 propre).

Apres : default True. Phase 5 verifie et raise 409 STOCK_INSUFFISANT propre.
Override `check_stock=False` reste possible pour cas admin (force-validate +
backfill manuel ulterieur).
"""
import pytest
from pydantic import ValidationError

from app.schemas.epicerie.vente import EncaissementRequest, LigneEncaissement


def _mk_ligne(quantite: float = 1.0):
    return LigneEncaissement(
        produit_id=1,
        quantite=quantite,
        prix_unitaire_cts=100,
    )


# ----------------------------------------------------------------------------
# F870 fix : default True
# ----------------------------------------------------------------------------

def test_encaissement_request_check_stock_default_is_true():
    """F870 fix : sans champ check_stock dans le payload -> default True (safe)."""
    req = EncaissementRequest(
        lignes=[_mk_ligne()],
        mode_paiement="ESPECES",
        montant_especes=100,
    )
    assert req.check_stock is True
    # Critique : ce default a change. Avant le fix c'etait False.
    assert req.check_stock is not False


def test_encaissement_request_check_stock_explicit_true_remains_true():
    """Non-regression : explicit True reste True."""
    req = EncaissementRequest(
        lignes=[_mk_ligne()],
        mode_paiement="ESPECES",
        montant_especes=100,
        check_stock=True,
    )
    assert req.check_stock is True


def test_encaissement_request_check_stock_explicit_false_admin_override():
    """Override admin (force-validate) : explicit False est toujours accepte.
    Cas exceptionnel ou l'admin fait un backfill stock manuel ulterieur."""
    req = EncaissementRequest(
        lignes=[_mk_ligne()],
        mode_paiement="ESPECES",
        montant_especes=100,
        check_stock=False,
    )
    assert req.check_stock is False


def test_encaissement_request_check_stock_serializes_correctly_with_default():
    """Le default True est serialize/deserialize correctement (round-trip)."""
    req = EncaissementRequest(
        lignes=[_mk_ligne()],
        mode_paiement="CB",
        montant_cb=100,
    )
    dumped = req.model_dump()
    assert dumped["check_stock"] is True

    req2 = EncaissementRequest(**dumped)
    assert req2.check_stock is True
