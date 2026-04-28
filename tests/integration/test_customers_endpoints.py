"""Tests d'intégration pour les endpoints clients."""
import pytest
from fastapi.testclient import TestClient
from app.models.customer import Customer
from app.constants import CustomerType


@pytest.fixture
def test_customer(test_db):
    """Client de test (individual) pour tenant_id=1."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Jean",
        last_name="Dupont",
        email="jean.dupont@example.com",
        phone="+33612345678",
        address="10 rue de la Paix",
        city="Paris",
        postal_code="75001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


@pytest.fixture
def test_company_customer(test_db):
    """Client de test (company) pour tenant_id=1."""
    customer = Customer(
        tenant_id=1,
        customer_type=CustomerType.COMPANY,
        company_name="EventPro SARL",
        email="contact@eventpro.fr",
        phone="+33987654321",
        address="25 avenue des Champs",
        city="Lyon",
        postal_code="69001",
        is_active=True
    )
    test_db.add(customer)
    test_db.commit()
    test_db.refresh(customer)
    return customer


def test_list_customers_success(client: TestClient, test_customer, auth_headers_real):
    """Test liste clients avec pagination."""
    response = client.get("/api/v1/customers?skip=0&limit=20", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_list_customers_filter_by_type(client: TestClient, test_customer, test_company_customer, auth_headers_real):
    """Test filtrer clients par type (individual/company)."""
    response = client.get("/api/v1/customers?customer_type=company", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["customer_type"] == "company"


def test_list_customers_search_by_name(client: TestClient, test_customer, auth_headers_real):
    """Test rechercher clients par nom/prénom."""
    response = client.get("/api/v1/customers?search_query=Dupont", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    # Vérifier que "Dupont" est dans les résultats
    names = [f"{item.get('first_name', '')} {item.get('last_name', '')}" for item in data["items"]]
    assert any("Dupont" in name for name in names)


def test_get_customer_success(client: TestClient, test_customer, auth_headers_real):
    """Test récupérer détails d'un client."""
    response = client.get(f"/api/v1/customers/{test_customer.id}", headers=auth_headers_real)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_customer.id
    assert data["customer_type"] == "individual"
    assert data["first_name"] == "Jean"
    assert data["last_name"] == "Dupont"
    assert data["email"] == "jean.dupont@example.com"
    assert data["phone"] == "+33612345678"


def test_get_customer_not_found(client: TestClient, auth_headers_real):
    """Test récupérer client inexistant → 404."""
    response = client.get("/api/v1/customers/999999", headers=auth_headers_real)

    assert response.status_code == 404


def test_create_customer_individual_success(client: TestClient, auth_headers_real):
    """Test créer client individual → 201."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Marie",
        "last_name": "Martin",
        "email": "marie.martin@example.com",
        "phone": "+33687654321",
        "address": "25 boulevard Voltaire",
        "city": "Marseille",
        "postal_code": "13001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 201
    data = response.json()
    assert data["first_name"] == "Marie"
    assert data["last_name"] == "Martin"
    assert data["customer_type"] == "individual"
    assert data["is_active"] is True


def test_create_customer_company_success(client: TestClient, auth_headers_real):
    """Test créer client company → 201."""
    customer_data = {
        "customer_type": "company",
        "company_name": "TechEvents SAS",
        "email": "contact@techevents.fr",
        "phone": "+33123456789",
        "address": "100 rue de Rivoli",
        "city": "Paris",
        "postal_code": "75004"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 201
    data = response.json()
    assert data["company_name"] == "TechEvents SAS"
    assert data["customer_type"] == "company"


def test_create_customer_duplicate_email(client: TestClient, test_customer, auth_headers_real):
    """Test créer client avec email déjà existant → 400."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Autre",
        "last_name": "Personne",
        "email": "jean.dupont@example.com",  # Email déjà utilisé
        "phone": "+33600000000",
        "address": "Autre adresse",
        "city": "Lyon",
        "postal_code": "69001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_customer_invalid_individual_missing_names(client: TestClient, auth_headers_real):
    """Test créer client individual sans first_name/last_name → 422."""
    customer_data = {
        "customer_type": "individual",
        # Manque first_name et last_name (requis pour individual)
        "email": "invalid@example.com",
        "phone": "+33600000000",
        "address": "Adresse",
        "city": "Paris",
        "postal_code": "75001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 422  # Validation Pydantic


def test_create_customer_invalid_company_missing_company_name(client: TestClient, auth_headers_real):
    """Test créer client company sans company_name → 422."""
    customer_data = {
        "customer_type": "company",
        # Manque company_name (requis pour company)
        "siret": "12345678901234",
        "email": "invalid@company.fr",
        "phone": "+33600000000",
        "address": "Adresse",
        "city": "Paris",
        "postal_code": "75001"
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 422  # Validation Pydantic


def test_update_customer_success(client: TestClient, test_customer, auth_headers_real):
    """Test mettre à jour client (PATCH partiel)."""
    update_data = {
        "phone": "+33699999999",
        "address": "Nouvelle adresse"
    }

    response = client.patch(
        f"/api/v1/customers/{test_customer.id}",
        json=update_data,
        headers=auth_headers_real
    )

    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+33699999999"
    assert data["address"] == "Nouvelle adresse"
    assert data["first_name"] == "Jean"  # Inchangé


def test_update_customer_duplicate_email(client: TestClient, test_db, test_customer, auth_headers_real):
    """Test mettre à jour client avec email déjà utilisé par autre client → 400."""
    # Créer second client
    customer2 = Customer(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Pierre",
        last_name="Durand",
        email="pierre.durand@example.com",
        phone="+33600000000",
        city="Lyon",
        postal_code="69001",
        is_active=True
    )
    test_db.add(customer2)
    test_db.commit()

    # Tenter de changer email de test_customer vers email de customer2
    update_data = {
        "email": "pierre.durand@example.com"
    }

    response = client.patch(
        f"/api/v1/customers/{test_customer.id}",
        json=update_data,
        headers=auth_headers_real
    )

    assert response.status_code == 400
    assert "already used" in response.json()["detail"]


def test_delete_customer_soft_delete(client: TestClient, test_customer, auth_headers_admin):
    """Test supprimer client (soft delete par défaut). Requiert CUSTOMERS_DELETE = manager+."""
    response = client.delete(
        f"/api/v1/customers/{test_customer.id}?hard_delete=false",
        headers=auth_headers_admin
    )

    assert response.status_code == 204

    # Vérifier que client est is_active=False
    get_response = client.get(f"/api/v1/customers/{test_customer.id}", headers=auth_headers_admin)
    assert get_response.status_code == 404  # Exclu par défaut


def test_delete_customer_not_found(client: TestClient, auth_headers_admin):
    """Test supprimer client inexistant → 404. Requiert CUSTOMERS_DELETE = manager+."""
    response = client.delete("/api/v1/customers/999999", headers=auth_headers_admin)

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Nouveaux tests (corrections audit 2026-03-02)
# ---------------------------------------------------------------------------

def test_create_customer_with_notes(client: TestClient, auth_headers_real):
    """BUG-CUST-05 : notes doit être sauvegardé et retourné à la création."""
    customer_data = {
        "customer_type": "individual",
        "first_name": "Note",
        "last_name": "Tester",
        "email": "note.tester@example.com",
        "notes": "Client VIP — préfère les livraisons le matin",
    }

    response = client.post("/api/v1/customers", json=customer_data, headers=auth_headers_real)

    assert response.status_code == 201
    data = response.json()
    assert data["notes"] == "Client VIP — préfère les livraisons le matin"


def test_search_customer_by_email(client: TestClient, test_customer, auth_headers_real):
    """BUG-CUST-01 : search_query doit trouver les clients par email."""
    response = client.get(
        f"/api/v1/customers?search_query={test_customer.email}",
        headers=auth_headers_real,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    emails = [item["email"] for item in data["items"]]
    assert test_customer.email in emails


def test_list_customers_inactive(client: TestClient, test_db, auth_headers_real):
    """BUG-CUST-02 : is_active=false doit inclure les clients soft-deleted."""
    from app.models.customer import Customer as CustomerModel
    from app.constants import CustomerType

    inactive = CustomerModel(
        tenant_id=1,
        customer_type=CustomerType.INDIVIDUAL,
        first_name="Inactif",
        last_name="Soft",
        email="inactif.soft@example.com",
        is_active=False,
    )
    test_db.add(inactive)
    test_db.commit()

    # Sans filtre → exclu par défaut
    response = client.get("/api/v1/customers", headers=auth_headers_real)
    assert response.status_code == 200
    emails_active_only = [i["email"] for i in response.json()["items"]]
    assert "inactif.soft@example.com" not in emails_active_only

    # is_active=false → inclut les inactifs
    response_all = client.get("/api/v1/customers?is_active=false", headers=auth_headers_real)
    assert response_all.status_code == 200
    emails_all = [i["email"] for i in response_all.json()["items"]]
    assert "inactif.soft@example.com" in emails_all


def test_list_customers_combined_search_and_type(
    client: TestClient, test_customer, test_company_customer, auth_headers_real
):
    """BUG-CUST-03 : search_query + customer_type doivent être combinables."""
    # Jean Dupont est individual — doit être trouvé
    response = client.get(
        "/api/v1/customers?search_query=Dupont&customer_type=individual",
        headers=auth_headers_real,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    for item in data["items"]:
        assert item["customer_type"] == "individual"

    # Jean Dupont est individual — filtre company doit l'exclure
    response_company = client.get(
        "/api/v1/customers?search_query=Dupont&customer_type=company",
        headers=auth_headers_real,
    )
    assert response_company.status_code == 200
    names = [f"{i.get('first_name','')} {i.get('last_name','')}".strip() for i in response_company.json()["items"]]
    assert "Jean Dupont" not in names


def test_import_csv_invalid_type_error_message(client: TestClient, auth_headers_real):
    """BUG-CUST-05 (CSV) : erreur de validation doit être lisible, sans stacktrace Pydantic."""
    import io
    csv_content = "customer_type,email,first_name,last_name\nbad_type,test@example.com,Test,User\n"
    csv_file = io.BytesIO(csv_content.encode("utf-8"))

    response = client.post(
        "/api/v1/customers/import",
        headers=auth_headers_real,
        files={"file": ("test.csv", csv_file, "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created"] == 0
    assert len(data["errors"]) >= 1
    error_msg = data["errors"][0]["message"]
    # Le message ne doit PAS contenir de stacktrace Pydantic brute
    assert "validation error for CustomerCreate" not in error_msg
    assert "For further information visit" not in error_msg
    # Il doit contenir une indication lisible sur le problème
    assert len(error_msg) < 200
