# Plan d'Amélioration Couverture Tests
**Objectif** : 84.79% → 90%+ (ajouter ~100 lignes de tests)

## État Actuel (214 tests, 84.79%)

### Modules Sous-Testés

#### P1 - Critical Business Logic
1. **app/repositories/reservation.py** : 41% (40 lignes manquantes)
   - ❌ `reference_exists()` - lignes 84-100
   - ❌ `list_by_status()` - lignes 102+
   - ❌ `list_by_date_range()` - lignes 153-184
   - ❌ `list_by_customer()` - lignes 186-217

2. **app/repositories/invoice.py** : 45% (36 lignes manquantes)
   - ❌ `get_by_id_with_relations()` - lignes 41-51
   - ❌ `get_by_invoice_number()` - lignes 53-81
   - ❌ `invoice_number_exists()` - lignes 83-109
   - ❌ `list_unpaid()` - lignes 224-236
   - ❌ `list_by_date_range()` - lignes 238-279

3. **app/services/auth.py** : 58% (30 lignes manquantes)
   - ❌ Refresh token logic
   - ❌ Password reset flow
   - ❌ User lockout mechanism

#### P2 - Infrastructure
4. **app/repositories/product.py** : 68% (21 lignes manquantes)
   - ❌ `list_by_category()` - méthode spécialisée
   - ❌ Edge cases dans `check_availability()`

5. **app/repositories/base.py** : 70% (38 lignes manquantes)
   - ❌ Méthodes soft delete complexes
   - ❌ Edge cases filtres

---

## Plan d'Exécution (3 phases)

### Phase 1 : Repositories Business Logic (85% → 88%)
**Estimation** : 2h | **Impact** : +3%

#### Fichier : `tests/unit/test_reservation_repository.py`
```python
def test_reference_exists_true(test_db, test_reservation):
    """Vérifie qu'une référence existante est détectée."""
    repo = ReservationRepository(test_db)
    assert repo.reference_exists(test_reservation.reference) is True

def test_reference_exists_false(test_db):
    """Vérifie qu'une référence inexistante retourne False."""
    repo = ReservationRepository(test_db)
    assert repo.reference_exists("RES-9999-9999") is False

def test_list_by_status_draft(test_db, test_reservation):
    """Liste les réservations par statut 'draft'."""
    repo = ReservationRepository(test_db)
    results, total = repo.list_by_status("draft", tenant_id=1)
    assert total >= 1
    assert all(r.status == "draft" for r in results)

def test_list_by_date_range(test_db, test_reservation):
    """Liste les réservations dans une plage de dates."""
    repo = ReservationRepository(test_db)
    start_date = date.today()
    end_date = date.today() + timedelta(days=30)
    results, total = repo.list_by_date_range(start_date, end_date, tenant_id=1)
    assert all(start_date <= r.event_date <= end_date for r in results)

def test_list_by_customer(test_db, test_reservation, test_customer):
    """Liste les réservations d'un client spécifique."""
    repo = ReservationRepository(test_db)
    results = repo.list_by_customer(test_customer.id, tenant_id=1)
    assert all(r.customer_id == test_customer.id for r in results)
```

**Tests à ajouter** : 8 tests (reference_exists, list_by_status, list_by_date_range, list_by_customer + edge cases)

#### Fichier : `tests/unit/test_invoice_repository.py`
```python
def test_get_by_id_with_relations(test_db, test_invoice):
    """Récupère une facture avec relations chargées (reservation + customer)."""
    repo = InvoiceRepository(test_db)
    invoice = repo.get_by_id_with_relations(test_invoice.id, tenant_id=1)
    assert invoice is not None
    assert invoice.reservation is not None
    assert invoice.reservation.customer is not None

def test_get_by_invoice_number_found(test_db, test_invoice):
    """Récupère une facture par son numéro."""
    repo = InvoiceRepository(test_db)
    invoice = repo.get_by_invoice_number(test_invoice.invoice_number, tenant_id=1)
    assert invoice is not None
    assert invoice.id == test_invoice.id

def test_get_by_invoice_number_not_found(test_db):
    """Recherche d'un numéro inexistant retourne None."""
    repo = InvoiceRepository(test_db)
    invoice = repo.get_by_invoice_number("INV-9999-9999", tenant_id=1)
    assert invoice is None

def test_invoice_number_exists_true(test_db, test_invoice):
    """Vérifie qu'un numéro existant est détecté."""
    repo = InvoiceRepository(test_db)
    assert repo.invoice_number_exists(test_invoice.invoice_number, tenant_id=1) is True

def test_invoice_number_exists_false(test_db):
    """Vérifie qu'un numéro inexistant retourne False."""
    repo = InvoiceRepository(test_db)
    assert repo.invoice_number_exists("INV-9999-9999", tenant_id=1) is False

def test_list_unpaid(test_db, test_invoice_unpaid, test_invoice_paid):
    """Liste les factures impayées."""
    repo = InvoiceRepository(test_db)
    results = repo.list_unpaid(tenant_id=1)
    assert all(i.paid_amount < i.total_amount for i in results)
    assert test_invoice_unpaid.id in [i.id for i in results]
    assert test_invoice_paid.id not in [i.id for i in results]

def test_list_by_date_range(test_db, test_invoice):
    """Liste les factures dans une plage de dates."""
    repo = InvoiceRepository(test_db)
    start_date = date.today() - timedelta(days=7)
    end_date = date.today() + timedelta(days=7)
    results = repo.list_by_date_range(start_date, end_date, tenant_id=1)
    assert all(start_date <= i.issue_date <= end_date for i in results)
```

**Tests à ajouter** : 10 tests (méthodes spécialisées + edge cases)

---

### Phase 2 : AuthService Security (88% → 89%)
**Estimation** : 1.5h | **Impact** : +1%

#### Fichier : `tests/unit/test_auth_service.py`
```python
def test_refresh_token_valid(test_db, test_user):
    """Refresh d'un token valide génère un nouveau access token."""
    service = AuthService(test_db)
    refresh_token = create_refresh_token({"sub": test_user.id})

    new_access_token = service.refresh_access_token(refresh_token)

    assert new_access_token is not None
    payload = decode_token(new_access_token)
    assert payload["sub"] == test_user.id

def test_refresh_token_invalid(test_db):
    """Refresh d'un token invalide lève une exception."""
    service = AuthService(test_db)

    with pytest.raises(HTTPException) as exc:
        service.refresh_access_token("invalid_token")

    assert exc.value.status_code == 401

def test_refresh_token_expired(test_db, test_user):
    """Refresh d'un token expiré lève une exception."""
    service = AuthService(test_db)
    expired_token = create_refresh_token(
        {"sub": test_user.id},
        expires_delta=timedelta(seconds=-1)  # Déjà expiré
    )

    with pytest.raises(HTTPException) as exc:
        service.refresh_access_token(expired_token)

    assert exc.value.status_code == 401

def test_user_lockout_after_max_attempts(test_db, test_user):
    """Verrouillage d'un compte après X tentatives échouées."""
    service = AuthService(test_db)

    # Simuler N tentatives échouées
    for _ in range(5):
        try:
            service.login("test@example.com", "wrong_password")
        except HTTPException:
            pass

    # Tentative suivante doit échouer avec "locked"
    with pytest.raises(HTTPException) as exc:
        service.login("test@example.com", "correct_password")

    assert "locked" in str(exc.value.detail).lower()
```

**Tests à ajouter** : 6 tests (refresh token, lockout, password reset flow)

---

### Phase 3 : Product Repository Edge Cases (89% → 90%+)
**Estimation** : 1h | **Impact** : +1%

#### Fichier : `tests/unit/test_product_repository.py`
```python
def test_list_by_category_chaises(test_db):
    """Liste les produits par catégorie 'chaises'."""
    # Créer produits de catégories différentes
    product1 = Product(tenant_id=1, name="Chaise Napoléon", sku="CHAISE-01", category="chaises", ...)
    product2 = Product(tenant_id=1, name="Table", sku="TABLE-01", category="tables", ...)
    test_db.add_all([product1, product2])
    test_db.commit()

    repo = ProductRepository(test_db)
    results = repo.list_by_category("chaises", tenant_id=1)

    assert all(p.category == "chaises" for p in results)
    assert product1.id in [p.id for p in results]
    assert product2.id not in [p.id for p in results]

def test_check_availability_insufficient_stock(test_db):
    """Vérifier la disponibilité avec stock insuffisant."""
    product = Product(tenant_id=1, ..., available_quantity=5)
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db)
    assert repo.check_availability(product.id, quantity=10, tenant_id=1) is False

def test_check_availability_exact_stock(test_db):
    """Vérifier la disponibilité avec stock exact."""
    product = Product(tenant_id=1, ..., available_quantity=10)
    test_db.add(product)
    test_db.commit()

    repo = ProductRepository(test_db)
    assert repo.check_availability(product.id, quantity=10, tenant_id=1) is True
```

**Tests à ajouter** : 5 tests (list_by_category, check_availability edge cases)

---

## Résumé

**Estimation Totale** : ~4.5 heures
**Impact** : +5% (84.79% → 90%+)
**Tests à Ajouter** : ~30 tests unitaires

### Priorisation
1. **Phase 1 (P1)** : Repositories → Impact business le plus fort
2. **Phase 2 (P2)** : AuthService → Sécurité critique
3. **Phase 3 (P3)** : Edge cases → Robustesse

### Objectif Final
- **214 → 244 tests** (+30)
- **84.79% → 90%+** de couverture
- **100% des repositories critiques > 85%**
