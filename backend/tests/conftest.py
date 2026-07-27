import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(_engine):
    TestingSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(_engine):
    """A raw session on the same in-memory DB `client` uses in this test, for
    seeding rows there's no endpoint for yet (e.g. marking_reports pre-Phase 3).
    """
    TestingSessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    session: Session = TestingSessionLocal()
    yield session
    session.close()
