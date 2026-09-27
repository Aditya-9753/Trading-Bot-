import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.security import decode_access_token
from ..models import Account, Instrument, Role, User

bearer = HTTPBearer(auto_error=False)


def user_from_token(db: Session, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None
    user = db.get(User, int(payload["sub"]))
    return user if user and user.is_active else None


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = user_from_token(db, creds.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def current_account(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Account:
    acc = db.scalar(select(Account).where(Account.user_id == user.id))
    if acc is None:
        raise HTTPException(500, "Account missing")
    return acc


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role not in (Role.ADMIN, Role.SUPER_ADMIN):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user


def require_super_admin(user: User = Depends(current_user)) -> User:
    if user.role != Role.SUPER_ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Super-admin access required")
    return user


def instrument_or_404(db: Session, symbol: str) -> Instrument:
    inst = db.scalar(select(Instrument).where(Instrument.symbol == symbol.upper()))
    if inst is None:
        raise HTTPException(404, f"Unknown symbol {symbol}")
    return inst


def client_ip(request: Request) -> str:
    return request.client.host if request.client else ""
