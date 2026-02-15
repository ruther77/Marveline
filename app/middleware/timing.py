"""Middleware de mesure du temps de reponse pour CaroCorp API.

Ajoute le header X-Response-Time (en ms) a chaque reponse.
Log un WARNING si le temps depasse le seuil configure.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

RESPONSE_TIME_HEADER = "X-Response-Time"


class TimingMiddleware(BaseHTTPMiddleware):
    """Mesure et expose le temps de traitement de chaque requete.

    Args:
        app: Application ASGI.
        slow_threshold_ms: Seuil en ms au-dela duquel un WARNING est emis (defaut: 1000).
    """

    def __init__(self, app, slow_threshold_ms: int = 1000):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[RESPONSE_TIME_HEADER] = f"{elapsed_ms:.1f}ms"

        if elapsed_ms > self.slow_threshold_ms:
            logger.warning(
                "Requete lente: %s %s — %.1fms (seuil: %dms)",
                request.method,
                request.url.path,
                elapsed_ms,
                self.slow_threshold_ms,
            )

        return response
