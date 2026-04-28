"""S1.T11 — tenants.rp_id + frontend_url (F368 WebAuthn multi-tenant).

Revision ID: s1t11rpid01
Revises: x4y5z6a7b8c9
Create Date: 2026-04-28

Hotfix Sprint 1 — résout F368/WEBAUTHN-RPID-MULTITENANT-01.

Avant : RP_ID hardcodé `settings.JWT_ISSUER` ("marveline.com") → toute credential
WebAuthn lie cryptographiquement à marveline.com, impossible d'enrôler/auth depuis
splendid.events ou epicerie.carocorp.fr.

Après : `tenants.rp_id` et `tenants.frontend_url` per-tenant, lus via
`request.state.tenant` dans WebAuthnService.

Migration expand-only (NULLABLE) — aucun risque de rupture.
Backfill conditionnel pour les 3 tenants existants (marveline, epicerie, restaurant).
"""
from typing import Sequence, Union

from alembic import op


revision: str = "s1t11rpid01"
down_revision: Union[str, None] = "x4y5z6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ADD COLUMNS — nullable pour rétrocompat (fallback settings.* si NULL)
    op.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS rp_id VARCHAR(253)")
    op.execute(
        "ALTER TABLE tenants ADD COLUMN IF NOT EXISTS frontend_url VARCHAR(512)"
    )

    op.execute(
        "COMMENT ON COLUMN tenants.rp_id IS "
        "'WebAuthn Relying Party ID (domaine sans protocole, ex: marveline.com, "
        "splendid.events). NULL = fallback settings.JWT_ISSUER.'"
    )
    op.execute(
        "COMMENT ON COLUMN tenants.frontend_url IS "
        "'URL frontend per-tenant pour expected_origin WebAuthn et emails. "
        "NULL = fallback settings.FRONTEND_URL.'"
    )

    # 2. Backfill tenants existants (idempotent — ne touche que les rp_id NULL)
    op.execute(
        """
        UPDATE tenants
        SET rp_id = 'marveline.com',
            frontend_url = 'https://marveline.com'
        WHERE app_code = 'marveline' AND rp_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE tenants
        SET rp_id = 'epicerie.carocorp.fr',
            frontend_url = 'https://epicerie.carocorp.fr'
        WHERE app_code = 'epicerie' AND rp_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE tenants
        SET rp_id = 'restaurant.carocorp.fr',
            frontend_url = 'https://restaurant.carocorp.fr'
        WHERE app_code = 'restaurant' AND rp_id IS NULL
        """
    )
    # Splendid : provisionné manuellement avec rp_id='splendid.events' lors du
    # provisioning Bloc 2 — pas de backfill ici (pas de tenant Splendid en base).


def downgrade() -> None:
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS frontend_url")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS rp_id")
