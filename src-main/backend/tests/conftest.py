from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app import models  # noqa: F401


@pytest.fixture
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    database_path = tmp_path / "test.db"
    engine = create_db_engine(f"sqlite:///{database_path.as_posix()}")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()
