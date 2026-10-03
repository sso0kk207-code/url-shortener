from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import Base, engine
from app.routers import auth, links, redirect


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # в проде вместо этого - миграции Alembic
    yield


app = FastAPI(
    title="URL Shortener API",
    version="1.0.0",
    description="Сервис коротких ссылок: JWT-авторизация, кастомные коды, срок жизни, аналитика переходов, кэш и rate limiting.",
    lifespan=lifespan,
)


@app.get("/health", tags=["service"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(links.router)
app.include_router(redirect.router)  # последним: /{code} не должен перекрывать остальные маршруты
