"""Schemas Pydantic — ETL Conflicts (tableau de bord opérateur).

Références :
    §6.4   : schéma SQL etl_conflicts validé
    ADR-07 : déduplication Jaro-Winkler, seuils ETL_SEUIL_MATCH / CONFLIT
    ADR-15 : etl_import_id nullable (SET NULL si import supprimé)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EtlConflictRead(BaseModel):
    """Représentation complète d'un conflit ETL pour le tableau de bord."""

    id: int
    etl_import_id: Optional[int]
    catalogue_produit_id: Optional[int]
    designation_entrante: str
    designation_existante: Optional[str]
    ean_a: Optional[str]
    ean_b: Optional[str]
    score_similarite: Optional[float]
    type_conflit: Optional[str]
    resolution: str
    suggestion: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EtlConflictListResponse(BaseModel):
    items: list[EtlConflictRead]
    total: int


class EtlConflictStats(BaseModel):
    """Compteurs agrégés pour la barre de KPIs du tableau de bord."""

    total: int
    pending: int
    merged: int
    kept_separate: int
    by_type: dict[str, int]


class EtlConflictResolveRequest(BaseModel):
    ids: list[int] = Field(..., min_length=1, description="IDs des conflits à résoudre")
    resolution: str = Field(
        ..., description="MERGED | KEPT_SEPARATE"
    )


class EtlConflictResolveResponse(BaseModel):
    resolved: int
    all_resolved: bool = False
    etl_import_id: Optional[int] = None
