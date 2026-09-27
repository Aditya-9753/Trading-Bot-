"""FastAPI application: REST API under /api/v1, WebSocket at /api/v1/ws."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api.routers import auth, markets, misc, strategy, trading
from .core.config import settings
from .core.db import Base, SessionLocal, engine
from .core.security import hash_password
from .models import Role, User
from .services.broker import create_account
from .services.market_data import seed_instruments
from .services.realtime import hub
from .services.simulator import simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tradebot")

DEMO_USERS = [("demo@example.com", "Demo@12345", "Demo Trader", Role.USER),
              ("admin@example.com", "Admin@12345", "Platform Admin", Role.SUPER_ADMIN)]


def bootstrap():
    if not settings.is_sqlite and (settings.JWT_SECRET.startswith("dev-secret") or len(settings.JWT_SECRET) < 32):
        raise RuntimeError("Set JWT_SECRET to a random string of at least 32 characters before using MySQL/production")
    if settings.is_sqlite:  # MySQL: use `alembic upgrade head`
        Base.metadata.create_all(engine)
        from sqlalchemy import text
        with engine.begin() as conn:
            try:
                cols = [row[1] for row in conn.execute(text("PRAGMA table_info(instruments)")).fetchall()]
                if cols and "asset_type" not in cols:
                    conn.execute(text("ALTER TABLE instruments ADD COLUMN asset_type VARCHAR(16) DEFAULT 'EQUITY'"))
            except Exception as ex:
                log.warning("schema check note: %s", ex)
    if not settings.SEED_DEMO:
        return
    with SessionLocal() as db:
        n = seed_instruments(db, settings.HISTORY_BARS)
        if n:
            log.info("seeded %s SIMULATED instruments with %s bars each", n, settings.HISTORY_BARS)
        for email, pw, name, role in DEMO_USERS:
            if not db.scalar(select(User).where(User.email == email)):
                u = User(email=email, full_name=name, password_hash=hash_password(pw), role=role)
                db.add(u)
                db.flush()
                create_account(db, u, settings.STARTING_CASH)
                log.info("created demo user %s", email)
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap()
    hub.bind(asyncio.get_running_loop())
    task = asyncio.create_task(simulator.run()) if settings.ENABLE_SIMULATOR else None
    yield
    simulator.stop()
    if task:
        task.cancel()


app = FastAPI(title="TradeBot API", version="1.0.0", lifespan=lifespan,
              description="Paper-trading platform with the Hybrid Algorithm v1.2. All money is virtual.")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errs = exc.errors()
    first = errs[0] if errs else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:])
    msg = f"{field}: {first.get('msg')}" if field else first.get("msg", "Invalid request")
    return JSONResponse(status_code=422, content={"detail": msg, "errors": [
        {k: v for k, v in e.items() if k in ("loc", "msg", "type")} for e in errs]})


for r in (auth.router, markets.router, trading.router, strategy.router, misc.router):
    app.include_router(r, prefix="/api/v1")


@app.get("/api/health")
def health():
    return {"status": "ok", "simulator": settings.ENABLE_SIMULATOR}
