#!/usr/bin/env python3
"""
Script pour créer/réinitialiser les utilisateurs de test (dev).

Usage (Docker) :
    docker compose exec api python scripts/create_test_user.py
    docker compose exec api python scripts/create_test_user.py --admin-only
    docker compose exec api python scripts/create_test_user.py --staff-only

Utilisateurs créés :
    admin@marveline.fr  /  Admin123!   (role=admin)
    test@carocorp.com   /  testpass123  (role=staff)
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.account import Account
from app.models.tenant import Tenant
from app.models.tenant_membership import TenantMembership
from app.core.security import get_password_hash

DATABASE_URL = "postgresql://caro:6L9dVl9hxpWylE8YQfNUNA@db:5432/CaroCorp"

DEFAULT_TENANT_ID = 1
DEFAULT_TENANT_EXTERNAL_ID = "00000000-0000-0000-0000-000000000001"


def _ensure_tenant(db, tenant_id: int) -> Tenant:
    """Retourne le tenant existant ou le crée avec id=tenant_id."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant:
        return tenant
    tenant = Tenant(
        external_id=DEFAULT_TENANT_EXTERNAL_ID,
        name="CaroCorp Dev",
        domain="carocorp.local",
        contact_email="admin@marveline.fr",
        app_code="marveline",
        status="active",
        is_active=True,
    )
    db.add(tenant)
    db.flush()
    return tenant


def create_or_reset_user(db, *, email: str, password: str, role: str,
                         first_name: str, last_name: str, tenant_id: int = DEFAULT_TENANT_ID) -> None:
    """Crée le compte et la membership s'ils n'existent pas, sinon réinitialise le mot de passe."""
    tenant = _ensure_tenant(db, tenant_id)

    account = db.query(Account).filter(Account.email == email).first()

    if account:
        account.hashed_password = get_password_hash(password)
        account.is_active = True
        # S'assurer que la membership existe
        membership = db.query(TenantMembership).filter(
            TenantMembership.account_id == account.id,
            TenantMembership.tenant_id == tenant.id,
        ).first()
        if not membership:
            membership = TenantMembership(
                account_id=account.id,
                tenant_id=tenant.id,
                role_name=role,
                status="active",
            )
            db.add(membership)
        db.commit()
        print(f"✓ Mot de passe réinitialisé : {email} (id={account.id}, role={role})")
        return

    account = Account(
        email=email,
        hashed_password=get_password_hash(password),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
    )
    db.add(account)
    db.flush()

    membership = TenantMembership(
        account_id=account.id,
        tenant_id=tenant.id,
        role_name=role,
        status="active",
    )
    db.add(membership)
    db.commit()
    db.refresh(account)
    print(f"✓ Utilisateur créé : {email} (id={account.id}, role={role})")


def main():
    args = sys.argv[1:]
    admin_only = "--admin-only" in args
    staff_only = "--staff-only" in args

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        if not staff_only:
            create_or_reset_user(
                db,
                email="admin@marveline.fr",
                password="Admin123!",
                role="admin",
                first_name="Admin",
                last_name="Marveline",
            )
        if not admin_only:
            create_or_reset_user(
                db,
                email="test@carocorp.com",
                password="testpass123",
                role="staff",
                first_name="Test",
                last_name="User",
            )
    except Exception as e:
        print(f"✗ Erreur : {e}")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
