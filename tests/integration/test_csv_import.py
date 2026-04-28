"""Tests intégration — POST /products/import (import CSV produits)."""
import io
import pytest


def _csv_bytes(*rows, header=None):
    """Construit un CSV en bytes à partir d'un header et de lignes."""
    if header is None:
        header = ["name", "sku", "category", "price_per_day_cents", "deposit_amount_cents", "stock_quantity"]
    lines = [",".join(header)]
    for row in rows:
        lines.append(",".join(row))
    return "\n".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_import_csv_creates_products(client, auth_headers_admin):
    """3 produits valides -> created=3, errors=[], skipped=0."""
    csv_data = _csv_bytes(
        ["Chaise Thonet", "CSV-CHT-001", "mobilier", "150", "50", "20"],
        ["Table ronde", "CSV-TBL-001", "mobilier", "350", "100", "10"],
        ["Nappage blanc", "CSV-NAP-001", "nappes", "80", "20", "50"],
    )
    resp = client.post(
        "/api/v1/products/import",
        files={"file": ("produits.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["created"] == 3
    assert data["skipped"] == 0
    assert data["errors"] == []


@pytest.mark.asyncio
async def test_import_csv_partial_errors(client, auth_headers_admin):
    """3 valides + 1 invalide (price non entier) -> created=3, errors=[1]."""
    csv_data = _csv_bytes(
        ["Produit A", "CSV-PA-001", "mobilier", "200", "0", "5"],
        ["Produit B", "CSV-PB-001", "mobilier", "abc", "0", "5"],
        ["Produit C", "CSV-PC-001", "nappes", "120", "0", "3"],
        ["Produit D", "CSV-PD-001", "vaisselle", "60", "10", "100"],
    )
    resp = client.post(
        "/api/v1/products/import",
        files={"file": ("produits.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["created"] == 3
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 2


@pytest.mark.asyncio
async def test_import_csv_skips_duplicate_sku(client, auth_headers_admin):
    """SKU deja present dans le tenant -> skipped+1, pas de doublon cree."""
    csv_data = _csv_bytes(
        ["Produit Unique", "CSV-UNIQ-001", "mobilier", "100", "0", "1"],
    )
    r1 = client.post(
        "/api/v1/products/import",
        files={"file": ("p.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth_headers_admin,
    )
    assert r1.status_code == 200
    assert r1.json()["created"] == 1

    r2 = client.post(
        "/api/v1/products/import",
        files={"file": ("p.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth_headers_admin,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["created"] == 0
    assert d2["skipped"] == 1


@pytest.mark.asyncio
async def test_import_csv_missing_required_column(client, auth_headers_admin):
    """CSV sans colonne obligatoire -> 422."""
    csv_data = _csv_bytes(
        ["Produit X", "100"],
        header=["name", "price_per_day_cents"],
    )
    resp = client.post(
        "/api/v1/products/import",
        files={"file": ("p.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth_headers_admin,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_csv_requires_auth(client):
    """Sans auth -> 401/403."""
    csv_data = _csv_bytes(
        ["Produit Z", "CSV-Z-001", "mobilier", "100", "0", "1"],
    )
    resp = client.post(
        "/api/v1/products/import",
        files={"file": ("p.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert resp.status_code in (401, 403)
