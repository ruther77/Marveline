"""Slow query logging + N+1 detection via SQLAlchemy events.

Enregistre un WARNING pour toute requete SQL > SLOW_QUERY_THRESHOLD_MS.
Compte les requetes par request pour detecter les N+1 (> MAX_QUERIES_PER_REQUEST).
"""
import logging
import time
import contextvars
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger("app.slow_query")

SLOW_QUERY_THRESHOLD_MS = 100  # WARNING si query > 100ms
MAX_QUERIES_PER_REQUEST = 20   # WARNING si > 20 queries dans une requete HTTP

# Compteur queries par request (via ContextVar)
_query_count: contextvars.ContextVar[int] = contextvars.ContextVar("_query_count", default=0)
_query_start: contextvars.ContextVar[float] = contextvars.ContextVar("_query_start", default=0.0)


def reset_query_counter() -> None:
    """Reset le compteur au debut de chaque requete HTTP (appele par middleware)."""
    _query_count.set(0)


def get_query_count() -> int:
    """Retourne le nombre de queries SQL dans la requete courante."""
    return _query_count.get()


def install_slow_query_listener(engine: Engine) -> None:
    """Installe les event listeners pour slow query + N+1 detection."""

    @event.listens_for(engine, "before_cursor_execute")
    def _before_execute(conn, cursor, statement, parameters, context, executemany):
        _query_start.set(time.perf_counter())

    @event.listens_for(engine, "after_cursor_execute")
    def _after_execute(conn, cursor, statement, parameters, context, executemany):
        elapsed_ms = (time.perf_counter() - _query_start.get()) * 1000

        # Slow query
        if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            # Tronquer le statement pour le log
            stmt_short = statement[:200].replace("\n", " ") if statement else "?"
            logger.warning(
                "SLOW QUERY (%.1fms): %s",
                elapsed_ms, stmt_short,
            )

        # N+1 counter
        count = _query_count.get() + 1
        _query_count.set(count)
        if count == MAX_QUERIES_PER_REQUEST:
            logger.warning(
                "N+1 DETECTED: %d queries in single request (threshold=%d)",
                count, MAX_QUERIES_PER_REQUEST,
            )
