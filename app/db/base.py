from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.core.config import Settings

Base = declarative_base()


def create_engine_and_session(settings: Settings):
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return engine, SessionLocal


# Session dependency factory is created in app.db.session
