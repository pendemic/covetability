from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

from app.settings import get_settings


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine]:
    settings = get_settings()
    test_url = settings.test_database_url

    # Hard guard: these tests truncate/rematch listings, so they must NEVER run
    # against the main database. Require an explicit, distinct TEST_DATABASE_URL.
    if not test_url:
        pytest.skip(
            "TEST_DATABASE_URL is not set. Tests mutate data and must use a dedicated "
            "database (see tests/README or Makefile 'db-test-up'). Refusing to run "
            "against the main DATABASE_URL."
        )
    if test_url == settings.database_url:
        pytest.fail("TEST_DATABASE_URL must differ from DATABASE_URL — tests would destroy live data.")

    engine = create_engine(test_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(f"Test Postgres unavailable: {exc}")

    yield engine
    engine.dispose()
