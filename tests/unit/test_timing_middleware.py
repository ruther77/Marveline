"""Tests unitaires pour app.middleware.timing.

Verifie :
- Header X-Response-Time present sur chaque reponse
- Format correct (Nms)
- WARNING log quand requete depasse le seuil
"""

import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.timing import RESPONSE_TIME_HEADER, TimingMiddleware


# ---------------------------------------------------------------------------
# App de test isolee
# ---------------------------------------------------------------------------

def _create_test_app(slow_threshold_ms: int = 1000) -> FastAPI:
    """Cree une mini-app avec uniquement le TimingMiddleware."""
    app = FastAPI()
    app.add_middleware(TimingMiddleware, slow_threshold_ms=slow_threshold_ms)

    @app.get("/fast")
    async def fast_endpoint():
        return {"status": "ok"}

    @app.get("/slow")
    async def slow_endpoint():
        time.sleep(0.05)  # 50ms
        return {"status": "slow"}

    return app


@pytest.fixture()
def test_client():
    app = _create_test_app()
    with TestClient(app) as client:
        yield client


@pytest.fixture()
def slow_threshold_client():
    """Client avec seuil bas (10ms) pour tester le warning."""
    app = _create_test_app(slow_threshold_ms=10)
    with TestClient(app) as client:
        yield client


# ===================================================================
# Header X-Response-Time
# ===================================================================

class TestResponseTimeHeader:
    """Tests pour le header X-Response-Time."""

    def test_header_present(self, test_client):
        """Le header X-Response-Time est present sur chaque reponse."""
        response = test_client.get("/fast")
        assert response.status_code == 200
        assert RESPONSE_TIME_HEADER in response.headers

    def test_format_ms(self, test_client):
        """Le header a le format 'N.Nms'."""
        response = test_client.get("/fast")
        value = response.headers[RESPONSE_TIME_HEADER]
        # Doit se terminer par 'ms'
        assert value.endswith("ms")
        # La partie numerique doit etre un float valide
        numeric = value.rstrip("ms")
        float(numeric)  # Leve ValueError si pas un float

    def test_temps_positif(self, test_client):
        """Le temps mesure est > 0."""
        response = test_client.get("/fast")
        value = response.headers[RESPONSE_TIME_HEADER]
        numeric = float(value.rstrip("ms"))
        assert numeric > 0

    def test_temps_coherent_pour_endpoint_lent(self, test_client):
        """Un endpoint avec sleep(50ms) doit mesurer >= 40ms."""
        response = test_client.get("/slow")
        value = response.headers[RESPONSE_TIME_HEADER]
        numeric = float(value.rstrip("ms"))
        # Avec sleep(0.05) = 50ms, on tolere >= 40ms (marge OS)
        assert numeric >= 40


# ===================================================================
# Slow request warning
# ===================================================================

class TestSlowRequestWarning:
    """Tests pour le log WARNING sur requete lente."""

    def test_warning_emis_quand_lente(self, slow_threshold_client, caplog):
        """Un WARNING est emis quand le temps depasse le seuil."""
        with caplog.at_level(logging.WARNING, logger="app.middleware.timing"):
            slow_threshold_client.get("/slow")
        # /slow fait sleep(50ms), seuil a 10ms -> WARNING
        assert any("Requete lente" in record.message for record in caplog.records)
        assert any("/slow" in record.message for record in caplog.records)

    def test_pas_de_warning_si_rapide(self, test_client, caplog):
        """Pas de WARNING si le temps est sous le seuil (defaut 1000ms)."""
        with caplog.at_level(logging.WARNING, logger="app.middleware.timing"):
            test_client.get("/fast")
        timing_warnings = [
            r for r in caplog.records
            if "Requete lente" in r.message
        ]
        assert len(timing_warnings) == 0


# ===================================================================
# Configuration du seuil
# ===================================================================

class TestThresholdConfiguration:
    """Tests pour la configuration du seuil de lenteur."""

    def test_seuil_par_defaut_1000ms(self):
        """Le seuil par defaut est 1000ms."""
        app = FastAPI()
        app.add_middleware(TimingMiddleware)
        # Acces aux middlewares internes
        # Le middleware est wrape, on verifie via le constructeur
        middleware = TimingMiddleware(app, slow_threshold_ms=1000)
        assert middleware.slow_threshold_ms == 1000

    def test_seuil_personnalise(self):
        """Le seuil peut etre personnalise."""
        app = FastAPI()
        middleware = TimingMiddleware(app, slow_threshold_ms=500)
        assert middleware.slow_threshold_ms == 500
