"""ISO-APP-01 — Tests du champ Tenant.app_code et de sa check constraint."""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.tenant import Tenant


def _mk_tenant(app_code: str) -> Tenant:
    token = uuid.uuid4().hex[:8]
    return Tenant(
        external_id=str(uuid.uuid4()),
        name=f"Test {token}",
        domain=f"test-{token}.local",
        contact_email=f"ops-{token}@test.local",
        app_code=app_code,
    )


class TestTenantAppCode:
    def test_app_codes_constant(self) -> None:
        assert Tenant.APP_CODES == ("marveline", "epicerie", "restaurant")

    @pytest.mark.parametrize("code", ["marveline", "epicerie", "restaurant"])
    def test_accepts_valid_code(self, test_db, code: str) -> None:
        tenant = _mk_tenant(code)
        test_db.add(tenant)
        test_db.commit()
        assert tenant.app_code == code

    def test_rejects_invalid_code(self, test_db) -> None:
        tenant = _mk_tenant("invalid_app")
        test_db.add(tenant)
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()

    def test_app_code_required(self, test_db) -> None:
        token = uuid.uuid4().hex[:8]
        tenant = Tenant(
            external_id=str(uuid.uuid4()),
            name=f"NoApp {token}",
            domain=f"noapp-{token}.local",
            contact_email=f"ops-{token}@test.local",
        )
        test_db.add(tenant)
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()
