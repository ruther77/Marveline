"""Tests securite — isolation tenant sur les endpoints ETL imports admin.

Les imports ETL n'ont pas de `tenant_id` propre. Quand une facture finance
est liee, son tenant devient la source de verite d'acces. Un tenant etranger
ne doit donc ni voir l'import, ni ouvrir son detail, ni executer `reopen`.
"""

from datetime import date, datetime, timezone

import pytest

from app.models.catalogue.etl_import import EtlImport
from app.models.finance.invoice import FinanceInvoice


@pytest.fixture
def reverted_import_tenant1(test_db, test_tenant_record):
    """Import REVERTED rattache au tenant 1 via une facture annulee."""
    etl_import = EtlImport(
        fichier_source="metro_t1.pdf",
        statut="REVERTED",
        numero_facture="016-283345",
        vendor_code="METRO",
        nb_lignes_total=1,
        nb_lignes_ok=1,
        lignes_data=[],
        reverted_at=datetime.now(timezone.utc),
        reverted_by_id=1,
    )
    test_db.add(etl_import)
    test_db.flush()

    invoice = FinanceInvoice(
        tenant_id=test_tenant_record.id,
        type="FOURNISSEUR",
        numero="FAC-20260411-0001",
        date_facture=date(2026, 4, 11),
        montant_ht=100,
        montant_tva=20,
        montant_ttc=120,
        statut="ANNULEE",
        etl_import_id=etl_import.id,
        reference="016-283345",
    )
    test_db.add(invoice)
    test_db.commit()
    test_db.refresh(etl_import)
    return etl_import


def test_tenant2_cannot_get_tenant1_linked_etl_import(
    client,
    auth_headers_admin_tenant2,
    reverted_import_tenant1,
):
    """Le tenant 2 ne peut pas lire le detail d'un import lie au tenant 1."""
    response = client.get(
        f"/api/v1/admin/etl/imports/{reverted_import_tenant1.id}",
        headers=auth_headers_admin_tenant2,
    )

    assert response.status_code == 404


def test_tenant2_list_hides_tenant1_linked_etl_import(
    client,
    auth_headers_admin_tenant2,
    reverted_import_tenant1,
):
    """La liste ETL du tenant 2 ne doit pas exposer un import du tenant 1."""
    response = client.get(
        "/api/v1/admin/etl/imports",
        headers=auth_headers_admin_tenant2,
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert reverted_import_tenant1.id not in ids


def test_tenant2_cannot_reopen_tenant1_linked_etl_import(
    client,
    auth_headers_admin_tenant2,
    reverted_import_tenant1,
):
    """Le tenant 2 ne peut pas relancer `reopen` sur un import du tenant 1."""
    response = client.post(
        f"/api/v1/admin/etl/imports/{reverted_import_tenant1.id}/reopen",
        headers=auth_headers_admin_tenant2,
    )

    assert response.status_code == 404


def test_tenant1_can_reopen_its_linked_etl_import(
    client,
    auth_headers_admin,
    reverted_import_tenant1,
):
    """Le tenant proprietaire conserve l'acces normal au workflow `reopen`."""
    response = client.post(
        f"/api/v1/admin/etl/imports/{reverted_import_tenant1.id}/reopen",
        headers=auth_headers_admin,
    )

    assert response.status_code == 200
    assert response.json()["statut"] == "PREVIEW"
