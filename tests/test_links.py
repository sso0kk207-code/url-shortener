from datetime import UTC, datetime, timedelta

from app import infra


def make(client, auth, **body):
    return client.post("/links", json={"url": "https://example.com/page", **body}, headers=auth)


def test_create_and_redirect(client, auth):
    r = make(client, auth)
    assert r.status_code == 201
    data = r.json()
    assert len(data["code"]) >= 6
    assert data["short_url"].endswith("/" + data["code"])

    r = client.get(f"/{data['code']}")
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/page"


def test_custom_code_and_conflict(client, auth):
    assert make(client, auth, custom_code="my-promo").json()["code"] == "my-promo"
    assert make(client, auth, custom_code="my-promo").status_code == 409


def test_reserved_and_invalid_codes(client, auth):
    assert make(client, auth, custom_code="docs").status_code == 422
    assert make(client, auth, custom_code="a b").status_code == 422
    assert make(client, auth, custom_code="ab").status_code == 422


def test_invalid_url_rejected(client, auth):
    r = client.post("/links", json={"url": "not-a-url"}, headers=auth)
    assert r.status_code == 422


def test_unknown_code_404(client):
    assert client.get("/zzzzzz").status_code == 404


def test_expired_link_returns_410(client, auth):
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    assert make(client, auth, custom_code="old", expires_at=past).status_code == 422
    # ссылка, которая успела истечь после создания
    code = make(client, auth, custom_code="soon", expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()).json()["code"]
    from app.db import SessionLocal
    from app.models import Link

    with SessionLocal() as db:
        link = db.query(Link).filter_by(code=code).one()
        link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    infra.cache.clear()
    assert client.get(f"/{code}").status_code == 410


def test_redirect_uses_cache(client, auth):
    code = make(client, auth).json()["code"]
    client.get(f"/{code}")
    assert infra.cache.get(f"link:{code}") == "https://example.com/page"


def test_list_is_scoped_to_owner(client, auth):
    make(client, auth)
    make(client, auth)
    other = client.post("/auth/register", json={"email": "other@example.com", "password": "supersecret1"}).json()
    other_h = {"Authorization": f"Bearer {other['access_token']}"}
    assert len(client.get("/links", headers=auth).json()) == 2
    assert client.get("/links", headers=other_h).json() == []


def test_cannot_delete_foreign_link(client, auth):
    code = make(client, auth).json()["code"]
    other = client.post("/auth/register", json={"email": "other@example.com", "password": "supersecret1"}).json()
    r = client.delete(f"/links/{code}", headers={"Authorization": f"Bearer {other['access_token']}"})
    assert r.status_code == 404


def test_delete_invalidates_cache(client, auth):
    code = make(client, auth).json()["code"]
    assert client.get(f"/{code}").status_code == 302
    assert client.delete(f"/links/{code}", headers=auth).status_code == 204
    assert client.get(f"/{code}").status_code == 404


def test_pagination(client, auth):
    for _ in range(5):
        make(client, auth)
    assert len(client.get("/links?limit=2", headers=auth).json()) == 2
    assert len(client.get("/links?limit=2&offset=4", headers=auth).json()) == 1


def test_create_rate_limit(client, auth):
    infra.create_limiter.limit = 3
    codes = [make(client, auth).status_code for _ in range(5)]
    assert codes == [201, 201, 201, 429, 429]
    infra.create_limiter.limit = 30
