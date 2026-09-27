import logging
import re

from .conftest import register

API = "/api/v1"


def test_register_login_me(client, user):
    r = client.get(f"{API}/auth/me", headers=user["h"])
    assert r.status_code == 200 and r.json()["email"] == user["email"] and r.json()["role"] == "USER"
    r = client.post(f"{API}/auth/login", json={"email": user["email"].upper(), "password": user["password"]})
    assert r.status_code == 200


def test_weak_password_and_duplicate(client, user):
    r = client.post(f"{API}/auth/register", json={"email": "weak@example.com", "password": "short"})
    assert r.status_code == 422 and "8 characters" in r.json()["detail"]
    r = client.post(f"{API}/auth/register", json={"email": user["email"], "password": "Passw0rd!x"})
    assert r.status_code == 409


def test_refresh_rotation_and_logout(client, user):
    r = client.post(f"{API}/auth/refresh", json={"refresh_token": user["refresh"]})
    assert r.status_code == 200
    new = r.json()["refresh_token"]
    # old refresh token cannot be reused
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": user["refresh"]}).status_code == 401
    assert client.post(f"{API}/auth/logout", json={"refresh_token": new}).status_code == 200
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": new}).status_code == 401


def test_unauthenticated_and_bad_token(client):
    assert client.get(f"{API}/portfolio").status_code == 401
    assert client.get(f"{API}/portfolio", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_login_throttle(client):
    u = register(client)
    for _ in range(5):
        assert client.post(f"{API}/auth/login", json={"email": u["email"], "password": "Wrong123A"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": u["email"], "password": u["password"]}).status_code == 429


def test_forgot_and_reset_password(client, caplog):
    u = register(client)
    with caplog.at_level(logging.WARNING, logger="tradebot.auth"):
        r = client.post(f"{API}/auth/forgot-password", json={"email": u["email"]})
    assert r.status_code == 200
    token = re.search(r"token=([\w-]+)", caplog.text).group(1)
    # unknown email answers identically (no account enumeration)
    assert client.post(f"{API}/auth/forgot-password", json={"email": "nobody@example.com"}).json() == r.json()
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd"}).status_code == 200
    assert client.post(f"{API}/auth/reset-password", json={"token": token, "new_password": "NewPassw0rd"}).status_code == 400
    assert client.post(f"{API}/auth/login", json={"email": u["email"], "password": "NewPassw0rd"}).status_code == 200
    # all sessions were revoked
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": u["refresh"]}).status_code == 401


def test_change_password(client, user):
    r = client.post(f"{API}/auth/change-password", headers=user["h"],
                    json={"current_password": "wrong", "new_password": "Another1Pass"})
    assert r.status_code == 400
    r = client.post(f"{API}/auth/change-password", headers=user["h"],
                    json={"current_password": user["password"], "new_password": "Another1Pass"})
    assert r.status_code == 200
