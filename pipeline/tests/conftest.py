from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.settings import get_settings


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Postgres unavailable: {exc}")

    yield engine
    engine.dispose()
