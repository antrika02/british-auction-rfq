import os
import pathlib
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.clock import get_clock
from app.db import get_db
from app.main import app

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://auction:auction_dev_password@localhost:5433/auction_test",
)
SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "db" / "schema.sql"

T0 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """A clock the tests control. Calling it returns 'now'."""

    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        # Build the schema from the same schema.sql the real database uses,
        # so the CHECK constraints are tested too
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.exec_driver_sql(SCHEMA.read_text())
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def clean_db(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "TRUNCATE activity_log, standings, bids, rfqs, suppliers RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def clock():
    return FakeClock(T0)


@pytest.fixture
def client(engine, clock):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
