def test_stats_count_clicks_referers_and_unique_visitors(client, auth):
    code = client.post("/links", json={"url": "https://example.com"}, headers=auth).json()["code"]

    client.get(f"/{code}", headers={"referer": "https://t.me/channel", "user-agent": "UA-1"})
    client.get(f"/{code}", headers={"referer": "https://t.me/channel", "user-agent": "UA-1"})
    client.get(f"/{code}", headers={"user-agent": "UA-2"})

    s = client.get(f"/links/{code}/stats", headers=auth).json()
    assert s["clicks_total"] == 3
    assert s["unique_visitors"] == 2
    assert sum(d["clicks"] for d in s["by_day"]) == 3
    assert s["top_referers"][0] == {"referer": "https://t.me/channel", "clicks": 2}
    assert {"referer": "(direct)", "clicks": 1} in s["top_referers"]


def test_stats_of_foreign_link_is_404(client, auth):
    code = client.post("/links", json={"url": "https://example.com"}, headers=auth).json()["code"]
    other = client.post("/auth/register", json={"email": "x@example.com", "password": "supersecret1"}).json()
    r = client.get(f"/links/{code}/stats", headers={"Authorization": f"Bearer {other['access_token']}"})
    assert r.status_code == 404


def test_redirect_rate_limit(client, auth):
    from app import infra

    code = client.post("/links", json={"url": "https://example.com"}, headers=auth).json()["code"]
    infra.redirect_limiter.limit = 2
    statuses = [client.get(f"/{code}").status_code for _ in range(4)]
    assert statuses == [302, 302, 429, 429]
    infra.redirect_limiter.limit = 300
