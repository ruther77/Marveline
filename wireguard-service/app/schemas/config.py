"""Schemas Pydantic pour la configuration client WireGuard."""

from pydantic import BaseModel


class ClientConfigResponse(BaseModel):
    """Reponse contenant la configuration client WireGuard."""

    peer_name: str
    config_text: str
    filename: str
