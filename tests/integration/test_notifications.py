"""Tests intégration — Notifications."""
import pytest
from fastapi.testclient import TestClient

from app.repositories.notification import NotificationRepository


@pytest.fixture
def notif_repo(test_db):
    return NotificationRepository(test_db)


def _seed(notif_repo, tenant_id: int, user_id: int, count: int = 3):
    for i in range(count):
        notif_repo.create(
            tenant_id=tenant_id,
            type="test",
            title=f"Notif {i + 1}",
            message=f"Message {i + 1}",
            user_id=user_id,
        )
    notif_repo.db.commit()


class TestListNotifications:
    def test_list_empty(self, client: TestClient, auth_headers_real: dict):
        resp = client.get("/api/v1/notifications", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["unread_count"] == 0

    def test_list_returns_notifications(
        self, client: TestClient, auth_headers_real: dict, test_user, notif_repo
    ):
        _seed(notif_repo, test_user.tenant_id, test_user.id, 3)
        resp = client.get("/api/v1/notifications", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["unread_count"] == 3
        assert len(data["items"]) == 3

    def test_unread_only_filter(
        self, client: TestClient, auth_headers_real: dict, test_user, notif_repo
    ):
        _seed(notif_repo, test_user.tenant_id, test_user.id, 3)
        items, _, _ = notif_repo.list(test_user.tenant_id, test_user.id)
        notif_repo.mark_read(items[0].id, test_user.tenant_id)
        notif_repo.db.commit()

        resp = client.get("/api/v1/notifications?unread_only=true", headers=auth_headers_real)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2

    def test_tenant_isolation(
        self, client: TestClient, auth_headers_real: dict, test_user, notif_repo
    ):
        # Créer notif pour autre tenant
        notif_repo.create(tenant_id=9999, type="test", title="Autre tenant")
        notif_repo.db.commit()
        _seed(notif_repo, test_user.tenant_id, test_user.id, 2)

        resp = client.get("/api/v1/notifications", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["total"] == 2


class TestMarkRead:
    def test_mark_single_read(
        self, client: TestClient, auth_headers_real: dict, test_user, notif_repo
    ):
        _seed(notif_repo, test_user.tenant_id, test_user.id, 1)
        items, _, _ = notif_repo.list(test_user.tenant_id, test_user.id)
        nid = items[0].id

        resp = client.post(f"/api/v1/notifications/{nid}/read", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True
        assert resp.json()["read_at"] is not None

    def test_mark_read_not_found(self, client: TestClient, auth_headers_real: dict):
        resp = client.post("/api/v1/notifications/99999/read", headers=auth_headers_real)
        assert resp.status_code == 404

    def test_mark_read_cross_tenant(
        self, client: TestClient, auth_headers_real: dict, notif_repo
    ):
        n = notif_repo.create(tenant_id=9999, type="test", title="Autre")
        notif_repo.db.commit()
        resp = client.post(f"/api/v1/notifications/{n.id}/read", headers=auth_headers_real)
        assert resp.status_code == 404


class TestMarkAllRead:
    def test_mark_all_read(
        self, client: TestClient, auth_headers_real: dict, test_user, notif_repo
    ):
        _seed(notif_repo, test_user.tenant_id, test_user.id, 4)
        resp = client.post("/api/v1/notifications/read-all", headers=auth_headers_real)
        assert resp.status_code == 200
        assert resp.json()["marked_read"] == 4

        # Vérifier que tout est lu
        resp2 = client.get("/api/v1/notifications", headers=auth_headers_real)
        assert resp2.json()["unread_count"] == 0
