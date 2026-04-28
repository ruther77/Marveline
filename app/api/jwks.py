"""Endpoint JWKS — /.well-known/jwks.json (CaroCorp §1.5).

Expose les cles publiques RSA au format JWK (RFC 7517).
Permet aux services consommateurs de verifier les JWT sans secret partage.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.kms import get_jwks_response

router = APIRouter(tags=["JWKS"])


@router.get(
    "/.well-known/jwks.json",
    response_class=JSONResponse,
    summary="JWKS public keys",
    description="Retourne les cles publiques RSA pour verification JWT (RFC 7517).",
)
async def jwks() -> dict:
    """Retourne le JWKS (JSON Web Key Set) contenant les cles publiques RSA."""
    return get_jwks_response()
