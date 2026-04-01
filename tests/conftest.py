from __future__ import annotations

import os
import tempfile

import pytest

from app.core.config import Settings
from app.db.session import init_db, get_session


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    # reload settings and recreate DB for each test
    s = Settings()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")
    # Ensure working storage path
    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "storage"))
    yield


@pytest.fixture()
def session():
    with get_session() as s:
        init_db()
        yield s
