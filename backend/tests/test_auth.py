import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

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
    Base.metadata.drop_all(engine)


def _register(client, email="jane@example.com", password="hunter22", name="Jane Doe"):
    return client.post(
        "/auth/register", json={"email": email, "password": password, "name": name}
    )


def _login(client, email="jane@example.com", password="hunter22"):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_creates_user(client):
    resp = _register(client)

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "jane@example.com"
    assert body["name"] == "Jane Doe"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email_rejected(client):
    _register(client)

    resp = _register(client)

    assert resp.status_code == 409


def test_login_success_returns_jwt(client):
    _register(client)

    resp = _login(client)

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_wrong_password_rejected(client):
    _register(client)

    resp = _login(client, password="not-the-password")

    assert resp.status_code == 401


def test_login_unknown_email_rejected(client):
    resp = _login(client, email="nobody@example.com")

    assert resp.status_code == 401


def test_protected_route_with_valid_token(client):
    _register(client)
    token = _login(client).json()["access_token"]

    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.json()["email"] == "jane@example.com"


def test_protected_route_without_token_rejected(client):
    resp = client.get("/auth/me")

    assert resp.status_code == 401


def test_protected_route_with_garbage_token_rejected(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert resp.status_code == 401
