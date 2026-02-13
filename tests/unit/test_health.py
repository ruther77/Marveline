"""Tests unitaires pour l'endpoint health."""
import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    """Test de l'endpoint /health (liveness probe)."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_api_v1_root(client: TestClient):
    """Test de l'endpoint racine API v1."""
    response = client.get("/api/v1/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "CaroCorp API v1"
    assert data["status"] == "operational"
    assert "endpoints" in data
