import secrets
import string
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import infra
from app.db import get_db
from app.deps import current_user
from app.models import Click, Link, User
from app.schemas import DayStat, LinkCreate, LinkOut, LinkStats, RefererStat

router = APIRouter(prefix="/links", tags=["links"])
ALPHABET = string.ascii_letters + string.digits


def _gen_code(length: int = 6) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _out(link: Link, request: Request) -> LinkOut:
    out = LinkOut.model_validate(link)
    out.short_url = f"{str(request.base_url).rstrip('/')}/{link.code}"
    return out


def _owned(db: Session, code: str, user: User) -> Link:
    link = db.scalar(select(Link).where(Link.code == code, Link.owner_id == user.id))
    if not link:
        raise HTTPException(404, "Link not found")
    return link


@router.post(
    "",
    response_model=LinkOut,
    status_code=201,
    dependencies=[Depends(infra.limit_by_ip(lambda: infra.create_limiter))],
)
def create_link(data: LinkCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if data.expires_at and data.expires_at.astimezone(UTC) <= datetime.now(UTC):
        raise HTTPException(422, "expires_at must be in the future")
    for attempt in range(5):
        code = data.custom_code or _gen_code(6 + attempt // 2)
        link = Link(code=code, url=str(data.url), owner_id=user.id, expires_at=data.expires_at)
        db.add(link)
        try:
            db.commit()
            return _out(link, request)
        except IntegrityError:
            db.rollback()
            if data.custom_code:
                raise HTTPException(409, "This custom code is already taken")
    raise HTTPException(503, "Could not generate a unique code, try again")


@router.get("", response_model=list[LinkOut])
def my_links(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    rows = db.scalars(select(Link).where(Link.owner_id == user.id).order_by(Link.id.desc()).limit(limit).offset(offset))
    return [_out(link, request) for link in rows]


@router.get("/{code}/stats", response_model=LinkStats)
def stats(code: str, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = _owned(db, code, user)
    since = datetime.now(UTC) - timedelta(days=days)
    base = (Click.link_id == link.id, Click.ts >= since)
    unique = db.scalar(select(func.count(func.distinct(Click.visitor))).where(*base)) or 0
    by_day = db.execute(select(func.date(Click.ts), func.count()).where(*base).group_by(func.date(Click.ts)).order_by(func.date(Click.ts))).all()
    refs = db.execute(
        select(func.coalesce(Click.referer, "(direct)"), func.count().label("n")).where(*base).group_by(func.coalesce(Click.referer, "(direct)")).order_by(func.count().desc()).limit(5)
    ).all()
    return LinkStats(
        code=code,
        clicks_total=link.clicks_total,
        unique_visitors=unique,
        by_day=[DayStat(day=str(d), clicks=n) for d, n in by_day],
        top_referers=[RefererStat(referer=r, clicks=n) for r, n in refs],
    )


@router.delete("/{code}", status_code=204)
def delete_link(code: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    link = _owned(db, code, user)
    db.delete(link)
    db.commit()
    infra.cache.delete(f"link:{code}")
