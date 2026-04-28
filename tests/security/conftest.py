"""Conftest pour tests security — auto-mark asyncio + fixture async_db."""
import inspect

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker


def pytest_collection_modifyitems(items):
    """Auto-marque @pytest.mark.asyncio sur tous les tests async sans marqueur.

    En pytest-asyncio 0.24.0 strict mode, @pytest.mark.asyncio sur une classe
    ne propage pas aux méthodes. Ce hook comble ce comportement pour les tests
    security, équivalent à asyncio_mode="auto" mais localisé à tests/security/.
    """
    for item in items:
        if hasattr(item, "obj") and inspect.iscoroutinefunction(item.obj):
            if item.get_closest_marker("asyncio") is None:
                item.add_marker(pytest.mark.asyncio)


@pytest.fixture
async def async_db(async_test_engine):
    """Fixture AsyncSession pour les tests security services async."""
    async_session = async_sessionmaker(async_test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
