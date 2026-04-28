"""Endpoints admin — ETL, résolution conflits, supervision."""
from app.api.v1.endpoints.admin.etl_conflicts import router as etl_conflicts_router
from app.api.v1.endpoints.admin.etl_imports import router as etl_imports_router

__all__ = ["etl_conflicts_router", "etl_imports_router"]
