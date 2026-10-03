import os

os.environ["DATABASE_URL"] = "sqlite://"  # in-memory

import pytest
from fastapi.testclient import TestClient

from app import infra
from app.db import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    infra.cache.clear()
    infra.create_limiter.reset()
    infra.redirect_limiter.reset()
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture()
def auth(client):
    r = client.post("/auth/register", json={"email": "anna@example.com", "password": "supersecret1"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
