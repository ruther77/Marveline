"""Router principal v1 du microservice WireGuard."""

from fastapi import APIRouter

from app.api.v1.config import router as config_router
from app.api.v1.ip_pools import router as ip_pools_router
from app.api.v1.peers import router as peers_router
from app.api.v1.status import router as status_router

api_v1_router = APIRouter(prefix="/wg/v1")

api_v1_router.include_router(peers_router)
api_v1_router.include_router(config_router)
api_v1_router.include_router(status_router)
api_v1_router.include_router(ip_pools_router)
