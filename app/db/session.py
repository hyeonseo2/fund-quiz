from __future__ import annotations

from contextlib import contextmanager
from typing import Tuple
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import Engine

from app.core.config import Settings
from app.db.base import Base, create_engine_and_session


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
_db_url: str | None = None


def get_engine_and_session() -> Tuple[Engine, sessionmaker]:
    global _engine, _SessionLocal, _db_url
    settings = Settings()
    if _engine is None or _db_url != settings.database_url:
        _engine, _SessionLocal = create_engine_and_session(settings)
        _db_url = settings.database_url
    assert _SessionLocal is not None
    return _engine, _SessionLocal


def init_db() -> None:
    engine, _ = get_engine_and_session()
    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session() -> Session:
    _, SessionLocal = get_engine_and_session()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
