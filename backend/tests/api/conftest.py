import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def register(client, password="Passw0rd!x"):
    email = f"u{uuid.uuid4().hex[:10]}@example.com"
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Test"})
    assert r.status_code == 201, r.text
    d = r.json()
    return {"email": email, "password": password, "token": d["access_token"], "refresh": d["refresh_token"],
            "h": {"Authorization": f"Bearer {d['access_token']}"}, "id": d["user"]["id"]}


def login(client, email, password):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def user(client):
    return register(client)


@pytest.fixture
def admin_h(client):
    return login(client, "admin@example.com", "Admin@12345")
