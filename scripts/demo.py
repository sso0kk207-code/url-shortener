"""Демо-сценарий: python scripts/demo.py http://127.0.0.1:8000"""
import time

from _demo import section, show

section("1. Регистрация и токен")
r = show("POST", "/auth/register", json_body={"email": "demo@example.com", "password": "supersecret1"})
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

section("2. Создаём короткую ссылку с кастомным кодом")
show("POST", "/links", json_body={"url": "https://example.com/very/long/landing?utm_source=telegram", "custom_code": "promo"}, headers=h)

section("3. Редирект (302) + запись статистики в фоне")
show("GET", "/promo", headers={"referer": "https://t.me/mychannel", "user-agent": "Mozilla/5.0"})
show("GET", "/promo", headers={"user-agent": "curl/8.0"})

time.sleep(0.7)  # клики пишутся в фоне
section("4. Аналитика по ссылке")
show("GET", "/links/promo/stats", headers=h)
