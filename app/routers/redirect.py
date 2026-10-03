import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from app import infra
from app.db import SessionLocal
from app.models import Click, Link

router = APIRouter(tags=["redirect"])


def _aware(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt and dt.tzinfo is None else dt


def _record_click(code: str, referer: str | None, ua: str | None, ip: str) -> None:
    """Выполняется после ответа клиенту - редирект не ждёт запись статистики."""
    with SessionLocal() as db:
        link_id = db.scalar(select(Link.id).where(Link.code == code))
        if link_id is None:
            return
        visitor = hashlib.sha256(f"{ip}|{ua}".encode()).hexdigest()
        db.add(Click(link_id=link_id, referer=(referer or None) and referer[:512], user_agent=(ua or None) and ua[:512], visitor=visitor))
        db.execute(update(Link).where(Link.id == link_id).values(clicks_total=Link.clicks_total + 1))
        db.commit()


@router.get(
    "/{code}",
    status_code=302,
    summary="Redirect to the original URL",
    dependencies=[Depends(infra.limit_by_ip(lambda: infra.redirect_limiter))],
)
def follow(code: str, request: Request, background: BackgroundTasks):
    url = infra.cache.get(f"link:{code}")
    if url is None:
        with SessionLocal() as db:
            link = db.scalar(select(Link).where(Link.code == code))
            if not link:
                raise HTTPException(404, "Link not found")
            exp = _aware(link.expires_at)
            if exp and exp <= datetime.now(UTC):
                raise HTTPException(410, "Link expired")
            url = link.url
            # TTL кэша не длиннее оставшейся жизни ссылки
            ttl = 300 if not exp else max(1, min(300, int((exp - datetime.now(UTC)).total_seconds())))
            infra.cache.set(f"link:{code}", url, ttl=ttl)
    background.add_task(_record_click, code, request.headers.get("referer"), request.headers.get("user-agent"), infra.client_ip(request))
    return RedirectResponse(url, status_code=302)
