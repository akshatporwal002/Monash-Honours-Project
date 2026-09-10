from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    database_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        # SQLite's legacy mode otherwise commits each schema statement separately.
        with engine.begin() as connection:
            connection.exec_driver_sql("BEGIN")
            Base.metadata.create_all(connection)
        session_factory = create_session_factory(engine)

        with session_factory() as session:
            yield session
    finally:
        # tmp_path gives each test its own file; no later test reuses this schema.
        engine.dispose()
