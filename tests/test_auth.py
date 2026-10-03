def test_register_and_login(client):
    r = client.post("/auth/register", json={"email": "Bob@Example.com", "password": "supersecret1"})
    assert r.status_code == 201
    r = client.post("/auth/login", data={"username": "bob@example.com", "password": "supersecret1"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_duplicate_email_rejected(client):
    body = {"email": "a@example.com", "password": "supersecret1"}
    assert client.post("/auth/register", json=body).status_code == 201
    assert client.post("/auth/register", json=body).status_code == 409


def test_wrong_password(client):
    client.post("/auth/register", json={"email": "a@example.com", "password": "supersecret1"})
    r = client.post("/auth/login", data={"username": "a@example.com", "password": "nope-nope-1"})
    assert r.status_code == 401


def test_weak_password_validation(client):
    r = client.post("/auth/register", json={"email": "a@example.com", "password": "123"})
    assert r.status_code == 422


def test_links_require_token(client):
    assert client.get("/links").status_code == 401
    assert client.post("/links", json={"url": "https://example.com"}).status_code == 401
