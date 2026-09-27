import logging
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.config import settings
from ...core.db import get_db
from ...core.security import (create_access_token, hash_password, new_opaque_token, password_problems, sha256,
                              verify_password)
from ...models import PasswordResetToken, RefreshToken, User, utcnow
from ...services.broker import create_account
from ...services.events import audit
from ..deps import client_ip, current_user

router = APIRouter(prefix="/auth", tags=["auth"])
log = logging.getLogger("tradebot.auth")

_FAILS: dict[str, deque] = defaultdict(deque)
MAX_FAILS, WINDOW_S = 5, 900


def _throttled(key: str) -> bool:
    q, now = _FAILS[key], time.monotonic()
    while q and now - q[0] > WINDOW_S:
        q.popleft()
    return len(q) >= MAX_FAILS


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    full_name: str = Field(default="", max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    new_password: str


class ChangeIn(BaseModel):
    current_password: str
    new_password: str


class ProfileIn(BaseModel):
    full_name: str = Field(max_length=120)


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
            "created_at": u.created_at.isoformat() + "Z"}


def _check_password(pw: str):
    problems = password_problems(pw)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems))


def issue_tokens(db: Session, user: User) -> dict:
    raw = new_opaque_token()
    db.add(RefreshToken(user_id=user.id, token_hash=sha256(raw),
                        expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_DAYS)))
    db.commit()
    return {"access_token": create_access_token(user.id, user.role), "refresh_token": raw,
            "token_type": "bearer", "expires_in": settings.ACCESS_TOKEN_MINUTES * 60, "user": user_out(user)}


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    _check_password(body.password)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    create_account(db, user, settings.STARTING_CASH)
    audit(db, user.id, "auth.register", email, ip=client_ip(request))
    return issue_tokens(db, user)


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = body.email.lower()
    key = f"{client_ip(request)}|{email}"
    if _throttled(key):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(body.password, user.password_hash):
        _FAILS[key].append(time.monotonic())
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been disabled")
    _FAILS.pop(key, None)
    user.last_login_at = utcnow()
    audit(db, user.id, "auth.login", email, ip=client_ip(request))
    return issue_tokens(db, user)


@router.post("/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    """Rotating refresh tokens: each refresh token works once."""
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    if rt is None or rt.revoked_at is not None or rt.expires_at < utcnow():
        raise HTTPException(401, "Session expired, please log in again")
    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Session expired, please log in again")
    rt.revoked_at = utcnow()
    return issue_tokens(db, user)


@router.post("/logout")
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256(body.refresh_token)))
    if rt and rt.revoked_at is None:
        rt.revoked_at = utcnow()
        db.commit()
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Always answers the same way so the endpoint can't be used to discover accounts.
    No email provider is configured: the reset link is written to the server log."""
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active:
        raw = new_opaque_token()
        db.add(PasswordResetToken(user_id=user.id, token_hash=sha256(raw),
                                  expires_at=utcnow() + timedelta(minutes=settings.RESET_TOKEN_MINUTES)))
        audit(db, user.id, "auth.forgot_password", user.email, ip=client_ip(request))
        db.commit()
        log.warning("PASSWORD RESET LINK for %s: %s/reset-password?token=%s", user.email, settings.FRONTEND_URL, raw)
    return {"ok": True, "message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    prt = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == sha256(body.token)))
    if prt is None or prt.used_at is not None or prt.expires_at < utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired")
    _check_password(body.new_password)
    user = db.get(User, prt.user_id)
    user.password_hash = hash_password(body.new_password)
    prt.used_at = utcnow()
    for rt in db.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):
        rt.revoked_at = utcnow()  # log out everywhere
    audit(db, user.id, "auth.reset_password", user.email)
    db.commit()
    return {"ok": True}


@router.post("/change-password")
def change_password(body: ChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, user.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    _check_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    audit(db, user.id, "auth.change_password", user.email)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user = db.get(User, user.id)
    user.full_name = body.full_name.strip()
    db.commit()
    return user_out(user)
