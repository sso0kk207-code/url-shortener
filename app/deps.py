from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(creds.credentials) if creds else None
    user = db.get(User, int(payload["sub"])) if payload else None
    if not user:
        raise HTTPException(401, "Invalid or missing token", headers={"WWW-Authenticate": "Bearer"})
    return user
