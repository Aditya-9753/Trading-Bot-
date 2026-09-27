# 🤖 TradeBot — NSE Paper Trading + Hybrid Algorithm v1.2

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776ab?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?style=for-the-badge&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178c6?style=for-the-badge&logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ed?style=for-the-badge&logo=docker&logoColor=white)

**NSE stocks ka paper (virtual) trading platform — poora paisa simulated hai, koi asli order exchange tak nahi jaata.**

[Features](#-features) • [Quick Start](#-quick-start) • [Architecture](#-architecture) • [Algorithm](#-hybrid-algorithm-v12) • [Admin System](#-admin-role-system) • [API](#-api-documentation) • [Deploy](#-deployment)

</div>

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Tech Stack](#-tech-stack)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [Hybrid Algorithm v1.2](#-hybrid-algorithm-v12)
- [Admin Role System](#-admin-role-system)
- [Sell / Portfolio Flow](#-sell--portfolio-flow)
- [API Documentation](#-api-documentation)
- [Database Models](#-database-models)
- [Risk Management](#-risk-management)
- [Paper Broker Engine](#-paper-broker-engine)
- [Bot Lifecycle](#-bot-lifecycle)
- [Backtesting](#-backtesting)
- [Deployment](#-deployment)
- [CI/CD Pipeline](#-cicd-pipeline)
- [NSE Real Data Import](#-nse-real-data-import)
- [Known Limitations](#-known-limitations)
- [Demo Credentials](#-demo-credentials)

---

## 🌟 Project Overview

TradeBot ek **full-stack quantitative trading simulator** hai jo NSE (National Stock Exchange) stocks ke liye paper trading karne deta hai. Poora system virtual/simulated hai:

- **Asli paisa nahi lagta** — sab virtual practice money hai
- **Live prices simulated hain** — koi real-time NSE feed nahi, simulator har second tick generate karta hai
- **Asli exchange se koi connection nahi** — ek educational/practice platform hai

### Is Session Mein Kya Kiya

| Feature | Kya Add Kiya |
|---|---|
| **Sell Flow** | Portfolio se trade sell karne ka full flow — preview, amount estimation, "Sell All" button, realized P&L |
| **Admin Role System** | Admin ko meaningful power — Cash Top-up, Platform Broadcast, Instrument Toggle, gold visual identity |
| **Admin Visual Hierarchy** | Gold crown, role pills, glowing sidebar badge, animated crown icon |
| **Crypto Markets** | Bitcoin (BTC), Ethereum (ETH), Solana (SOL), BNB, Ripple (XRP), Dogecoin (DOGE), Cardano (ADA), Avalanche (AVAX) in ₹ INR with full trading |
| **Benchmark Indices** | NIFTY 50, BSE SENSEX, BANK NIFTY, NIFTY IT, NIFTY Midcap 100 — live index benchmarks with chart analysis and order protection |
| **Markets UI Redesign** | Live benchmark ticker cards (Nifty, Sensex, Bank Nifty, BTC), category tabs (All, Equities, Indices, Crypto), and asset badges |

---

## 🛠 Tech Stack

### Backend
| Library | Version | Purpose |
|---|---|---|
| **FastAPI** | >=0.110 | REST API + WebSocket |
| **SQLAlchemy 2** | >=2.0 | ORM, row-level locking |
| **Alembic** | >=1.13 | Database migrations |
| **Pydantic v2** | >=2.6 | Request/response validation |
| **PyJWT** | >=2.8 | JWT access + refresh tokens |
| **passlib[bcrypt]** | >=1.7 | Password hashing |
| **pandas + numpy** | latest | Indicators, backtesting |
| **Uvicorn** | >=0.29 | ASGI server |
| **SQLite** | built-in | Development database |
| **MySQL 8** | docker | Production database |

### Frontend
| Library | Version | Purpose |
|---|---|---|
| **React 18** | ^18.3 | UI framework |
| **TypeScript 5** | ^5.5 | Type safety |
| **Vite 5** | ^5.4 | Build tool + dev server |
| **React Router 6** | ^6.26 | Client-side routing |
| **Recharts** | ^2.12 | Equity curves, P&L charts |
| **Vitest** | ^2.0 | Unit testing |

### Infrastructure
- **Docker Compose** — MySQL + Backend + Nginx (frontend static serve)
- **GitHub Actions** — CI/CD (test, typecheck, build, deploy)
- **Dependabot** — Automatic dependency security updates

---

## Features

### 🔐 Authentication & Security
- **Register / Login** — email + bcrypt password
- **JWT Tokens** — 15-minute access token + 7-day rotating refresh token
- **Forgot / Reset Password** — token-based reset (link logged to server in dev)
- **Change Password** — authenticated endpoint
- **Login Throttling** — 5 failed attempts = 15-minute lockout (brute-force protection)
- **3 Roles** — `USER`, `ADMIN`, `SUPER_ADMIN` (granular permission control)
- **Audit Log** — har admin action database mein record hota hai

### 📈 Multi-Asset Markets (Equities, Indices & Crypto)
- **Indian Equities (NSE)** — 15 leading blue chips (Reliance, TCS, HDFC Bank, Infosys, ICICI Bank, SBI, ITC, L&T, Bharti Airtel, HUL, Axis Bank, Kotak Bank, Tata Motors, Maruti, Wipro)
- **Benchmark Indices** — NIFTY 50, BSE SENSEX, BANK NIFTY, NIFTY IT, NIFTY Midcap 100 with real-time price trends and chart analytics (benchmark indicators with order protection)
- **Crypto Markets** — Bitcoin (BTC), Ethereum (ETH), Solana (SOL), Binance Coin (BNB), Ripple (XRP), Dogecoin (DOGE), Cardano (ADA), Avalanche (AVAX) priced in ₹ INR
- **Category Filter Tabs** — One-click filtering for All Markets, Equities (NSE), Indices (Nifty/Sensex), and Crypto
- **Benchmark Ticker Cards** — Top live cards for NIFTY 50, SENSEX, BANK NIFTY, and BITCOIN with live ticks
- **Candlestick Charts** — OHLCV candles with EMA 20/50, RSI, MACD overlays for every asset
- **Live Price Feed** — WebSocket se real-time simulated ticks (1 tick/second per active instrument)
- **Watchlists** — Custom watchlists across stocks, indices, and crypto

### 💼 Paper Broker
- **3 Order Types** — Market (fill immediately), Limit (price ya better), Stop (trigger price)
- **Stop-Loss + Target** — position level protection (automatic system sell)
- **Indian Charges** — STT, Stamp Duty, Exchange fee, SEBI charges, GST, slippage
- **Cancel Orders** — OPEN orders cancel ho sakte hain
- **Order History** — har order + fill record hota hai

### 💰 Portfolio & Sell Flow (UPDATED)
- **Live P&L** — unrealized (live), realized (after sell), day P&L
- **Equity Curve** — time-series chart
- **Win Rate, Profit Factor** — closed trades analytics
- **P&L per Stock** — bar chart by symbol
- **Smart Sell Modal** — sell karne se pehle preview:
  - Current holdings + avg buy price + live price
  - "Sell All" one-click button
  - Exact "You will receive ₹X" calculation (value - charges)
  - Estimated realized P&L (green/red)
  - Post-sell toast: actual cash received + realized P&L
- **Practice Account Reset** — sab positions/orders clear, fresh start

### ⚠️ Risk Management
- **Daily Loss Limit** — equity <= (1 - limit%) of day-start equity -> buys blocked
- **Max Position %** — single stock exposure limit (% of total equity)
- **Max Open Positions** — kitne stocks mein position rakh sakte ho
- **Max Daily Trades** — din bhar mein kitne orders
- **Platform Kill Switch** — SUPER_ADMIN sab trading ek click mein pause kar sakta hai
- **Long-Only** — short selling nahi (NSE delivery segment rules)

> **Important:** Risk limits sirf **BUY** orders par lagte hain. **Sell/exit kabhi block nahi hota.**

### 🧠 Strategy Lab
- **Signal Gauge** — composite score S in [-1, +1]
- **Component Contributions** — Trend, Momentum, Reversion, Volume ka alag-alag contribution
- **200-bar S Chart** — historical signal series
- **10 Tunable Parameters** — range-validated sliders
- **v1.1 / v1.2 Switch** — dono versions compare kar sako

### 📊 Backtesting
- **Real Engine** — same algorithm jo live bots use karte hain
- **Buy & Hold Benchmark** — strategy vs passive comparison
- **Trades Table** — har simulated trade ka detail
- **Walk-Forward Analysis** — out-of-sample validation
- **Robustness Check** — +-20% parameter sweep (sensitivity analysis)

### 🤖 Bots
- **Lifecycle** — `DRAFT -> BACKTESTED -> RUNNING <-> PAUSED -> STOPPED / ERROR`
- **Backtest-First Gate** — start karne se pehle current parameters ka backtest zaroori
- **Sandboxed Evaluation** — har bar close par alag process (wall timeout + CPU + memory limits)
- **ATR Stop** — volatility-based stop loss (auto-calculated)
- **Trailing Stop** — profit lock-in karta hai
- **Stop -> Share** — bot stop hone par shares portfolio ko transfer hoti hain, apni stop/target ke saath
- **Activity Log** — har bot decision logged

### 🔔 Alerts & Notifications
- **Price Alerts** — ABOVE / BELOW triggers
- **In-App Notifications** — order fills, bot events, alerts
- **WebSocket Push** — real-time: ticks, order status, kill switch, bot logs
- **Read / Read-All** — notification management

### 👑 Admin Panel (UPDATED)
See [Admin Role System](#-admin-role-system) below.

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node 18+
- Git

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# Copy env file (optional — defaults work for dev)
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

> **Pehli baar start hone par auto-create hota hai:**
> - SQLite database (`tradebot.db`)
> - 12 simulated NSE stocks (600 historical bars each)
> - Demo users (admin + regular)

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Opens: http://localhost:5173
# /api aur /ws automatically proxy -> http://localhost:8000
```

### 3. Login

```
URL:   http://localhost:5173
Admin: admin@example.com / Admin@12345
User:  demo@example.com  / Demo@12345
```

---

## 📁 Project Structure

```
tradebot/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # Auth dependencies (require_admin etc.)
│   │   │   └── routers/
│   │   │       ├── auth.py          # Register, login, refresh, reset password
│   │   │       ├── markets.py       # Instruments, candles, watchlists
│   │   │       ├── trading.py       # Orders, trades, portfolio, risk limits
│   │   │       ├── strategy.py      # Bots, backtests, signal evaluation
│   │   │       └── misc.py          # Alerts, notifications, dashboard, admin, WebSocket
│   │   ├── bots/
│   │   │   ├── bot_sandbox.py       # Process-isolated bot evaluation
│   │   │   └── market_calendar.py   # NSE trading hours
│   │   ├── core/
│   │   │   ├── config.py            # Settings (pydantic-settings)
│   │   │   ├── db.py                # SQLAlchemy session
│   │   │   └── security.py          # JWT encode/decode, bcrypt
│   │   ├── services/
│   │   │   ├── broker.py            # Paper order engine (fill, risk checks, locks)
│   │   │   ├── bots.py              # Bot lifecycle management
│   │   │   ├── market_data.py       # Price settings, kill switch
│   │   │   ├── realtime.py          # WebSocket hub (pub/sub)
│   │   │   ├── simulator.py         # Tick generator (1/sec), bar close logic
│   │   │   └── events.py            # audit(), notify() helpers
│   │   ├── strategies/
│   │   │   ├── params.py            # HybridParams v1.1 / v1.2
│   │   │   ├── engine/              # signal_engine, regime_engine, strategy_engine
│   │   │   ├── built_in/            # Trend, Momentum, Reversion, Volume components
│   │   │   └── indicators/          # EMA, MACD, RSI, ATR, MeanRev, VolRatio
│   │   ├── backtesting/             # Walk-forward, robustness sweep
│   │   ├── risk/                    # Position sizing, daily loss
│   │   ├── trading/
│   │   │   └── execution/           # CostModel (STT, stamp, exchange, GST, slippage)
│   │   ├── models.py                # All SQLAlchemy ORM models
│   │   └── main.py                  # FastAPI app, startup, middleware
│   ├── migrations/                  # Alembic migration files
│   ├── scripts/
│   │   ├── import_bhavcopy.py       # NSE bhav copy importer (CSV/ZIP)
│   │   ├── corporate_actions.py     # Split/bonus back-adjustment
│   │   └── demo_backtest.py         # Quick CLI backtest on any CSV
│   ├── tests/                       # 87 backend tests (pytest)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts            # fetch wrapper, token refresh, error handling
│   │   │   └── types.ts             # All TypeScript interfaces
│   │   ├── components/
│   │   │   ├── Layout.tsx           # Sidebar nav, topbar, admin gold badge
│   │   │   ├── OrderTicket.tsx      # BUY/SELL order form with fee estimate
│   │   │   ├── CandleChart.tsx      # OHLCV + indicators chart
│   │   │   ├── SignalGauge.tsx      # Strategy signal visualizer
│   │   │   ├── charts.tsx           # EquityChart, PnlBars
│   │   │   └── ui.tsx               # Button, Modal, Panel, Stat, Badge, Field...
│   │   ├── lib/
│   │   │   ├── auth.tsx             # AuthProvider, useAuth, isAdmin
│   │   │   ├── live.tsx             # LiveProvider, useLive, useLiveRefresh (WebSocket)
│   │   │   ├── toast.tsx            # Toast notification system
│   │   │   ├── format.ts            # money(), pct(), dateTime() formatters
│   │   │   └── useApi.ts            # Data fetching hook
│   │   ├── pages/
│   │   │   ├── Auth.tsx             # Login / Register / Forgot password
│   │   │   ├── Dashboard.tsx        # Summary: portfolio, bots, movers, checklist
│   │   │   ├── Markets.tsx          # Stock list + search
│   │   │   ├── StockDetail.tsx      # Candle chart + order ticket
│   │   │   ├── Portfolio.tsx        # Holdings + SellModal + performance [UPDATED]
│   │   │   ├── Orders.tsx           # Order history
│   │   │   ├── Watchlists.tsx       # Custom watchlists
│   │   │   ├── Alerts.tsx           # Price alerts + notifications
│   │   │   ├── StrategyLab.tsx      # Signal inspection, parameter tuning
│   │   │   ├── Backtests.tsx        # Run + list backtests
│   │   │   ├── BacktestDetail.tsx   # Charts, metrics, walk-forward, robustness
│   │   │   ├── Bots.tsx             # Bot list + create
│   │   │   ├── BotDetail.tsx        # Bot control, logs, last decision
│   │   │   ├── Admin.tsx            # Admin Control Centre [UPDATED]
│   │   │   ├── Settings.tsx         # Risk limits, change password
│   │   │   └── Help.tsx             # How it works guide
│   │   └── styles.css               # Full design system (1900+ lines)
│   ├── index.html
│   └── Dockerfile
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                   # Test + typecheck + build pipeline
│   │   └── cd.yml                   # Docker build + push + deploy
│   └── dependabot.yml               # Weekly security updates
├── scripts/
│   └── deploy.sh                    # One-command server deployment
├── docker-compose.yml               # MySQL + backend + nginx
├── CHANGELOG_v1_2.md                # Algorithm v1.1 -> v1.2 change log
└── README.md                        # This file
```

---

## 🏗 Architecture

```
┌────────────────────────────────────────────────┐
│            BROWSER (React SPA)                 │
│  Port 5173 (dev) / 8080 (docker)               │
│                                                │
│  Pages → Components → Hooks → API Client      │
│  WebSocket → useLive() → prices/events        │
└──────────────┬────────────────┬────────────────┘
               │  REST /api/v1  │  WS /api/v1/ws
               ▼                ▼
┌────────────────────────────────────────────────┐
│          FastAPI Backend (port 8000)           │
│                                                │
│  auth │ markets │ trading │ strategy │ misc   │
│                                                │
│  services/broker     ← account lock + fills   │
│  services/simulator  ← 1 tick/sec loop        │
│  services/bots       ← lifecycle management   │
│  services/realtime   ← WebSocket hub          │
│                                                │
│  strategies/engine/                            │
│    signal_engine  → S in [-1, +1]             │
│    regime_engine  → TRENDING/SIDEWAYS/HIGHVOL │
│    strategy_engine → entry/exit decisions      │
└──────────────────────┬─────────────────────────┘
                       │ SQLAlchemy ORM
                       ▼
┌────────────────────────────────────────────────┐
│  SQLite (dev)  /  MySQL 8 (production)         │
│                                                │
│  Users, Accounts, Orders, Trades,             │
│  Positions, Bots, Backtests, Alerts,          │
│  Notifications, AuditLogs, Candles...         │
└────────────────────────────────────────────────┘
```

### Practice Market Engine

```
Simulator Loop (background thread):
  Every TICK_SECONDS (default: 1 second):
    → Generate new simulated price for each instrument
    → Match OPEN limit/stop orders (broker.match_open_orders)
    → Check stop-loss / target exits (broker.check_protective_exits)
    → Check price alerts (trigger notifications)
    → Push WebSocket ticks to all connected clients

  Every TICKS_PER_BAR ticks (default: 30 ticks = 1 "bar"):
    → Save candle to database
    → Evaluate all RUNNING bots (sandboxed subprocess)
    → Take equity snapshots for all accounts
```

> **Speed note:** 30 ticks = 1 practice bar = ~30 seconds real time.
> Bots decide every bar. `TICK_SECONDS` aur `TICKS_PER_BAR` se speed adjust ho sakti hai.

---

## 🧠 Hybrid Algorithm v1.2

### Signal Score S

```
S = Σ (weight_i × component_score_i)   ∈ [-1.0, +1.0]

Components (v1.2):
  Trend     — EMA20/EMA50 slope + crossover
  Momentum  — tanh(R_20 / (STD(R,20) × sqrt(20)))   [v1.2: horizon scaling]
  Reversion — 0.5 × RSI_score + 0.5 × MeanRev        [v1.2: merged correlated]
  Volume    — relative volume vs 20-bar average
```

### Regime Detection

```
TRENDING        → trend strength > trend_threshold (0.35)
HIGH_VOLATILITY → VolRatio > highvol_threshold (1.5)  [entries BLOCKED]
SIDEWAYS        → neither of above
WARMUP          → insufficient history bars
```

### Regime Weights (v1.2)

| Component | Trending | Sideways | High Vol |
|---|---|---|---|
| Trend | 0.45 | 0.10 | 0.30 |
| Momentum | 0.35 | 0.10 | 0.25 |
| Reversion | 0.05 | 0.65 | 0.30 |
| Volume | 0.15 | 0.15 | 0.15 |

### Entry / Exit Rules

```
ENTRY:   S >= +0.55  AND  regime = TRENDING or SIDEWAYS
CONFIRM: S >= +0.30  (position hold karo)
EXIT:    S <= -0.25  OR   stop_loss hit  OR  target hit  OR  bot stopped
```

### Position Sizing

```
Risk per trade = risk_budget × equity = 1% of equity
ATR stop       = atr_stop_mult × ATR14 = 2.0 × ATR
Qty            = risk_amount / (entry_price × ATR_stop_pct)
Cap at:          max_buying_power_use (98%) of available cash
```

### v1.1 → v1.2 Changes

| # | Problem (v1.1) | Fix (v1.2) |
|---|---|---|
| 1 | Entry score ±0.55 structurally unreachable | New regime weights — reversion low in TRENDING |
| 2 | Momentum formula saturated 69.5% of bars | Added horizon scaling: divide by STD×sqrt(20) |
| 3 | High volatility incorrectly added to directional S | Volatility removed from S |
| 4 | Short conviction formula broken | Mirror formula: short_CF = 1 − CF |
| 5 | RSI + MeanRev 0.87 correlated, double-counted | Merged into single "Reversion" component |
| 6 | Bot sandbox insecure | Process-isolated with wall/CPU/memory limits |

---

## 👑 Admin Role System

### 3 Roles, 3 Levels of Power

```
USER          → Normal trader (paper trading, bots, alerts, portfolio)
ADMIN         → 🛡 Platform manager (user management + admin tools)
SUPER_ADMIN   → ⭐ Supreme control (everything + kill switch + role changes)
```

### Admin-Exclusive Powers

| Feature | ADMIN | SUPER_ADMIN | USER |
|---|---|---|---|
| View admin panel | ✅ | ✅ | ❌ |
| View all users | ✅ | ✅ | ❌ |
| Enable / Disable users | ✅ | ✅ | ❌ |
| **Cash Top-up** | ✅ | ✅ | ❌ |
| **Platform Broadcast** | ✅ | ✅ | ❌ |
| **Instrument Toggle** | ✅ | ✅ | ❌ |
| View all platform bots | ✅ | ✅ | ❌ |
| Full audit log | ✅ | ✅ | ❌ |
| Change user roles | ❌ | ✅ | ❌ |
| **Kill Switch** | ❌ | ✅ | ❌ |

### Admin Control Centre Tabs

1. **Users Tab** — email, role, equity, bot count, status, per-user `₹ Top-up` button
2. **Bots Tab** — all platform bots with owner email, status, position
3. **Instruments Tab** (NEW) — enable/disable any stock for trading platform-wide
4. **Audit Log Tab** — every admin action with timestamp, actor, target, detail

### Cash Top-up

```
Admin → User row → "₹ Top-up" → Modal:
  Amount (+ add, - deduct)
  Admin note (shown to user)
  → POST /admin/users/{uid}/topup
  → acc.cash += amount (signed)
  → Audit log entry
  → User gets in-app notification
```

### Platform Broadcast

```
Admin → "📢 Broadcast" → Modal:
  Kind: Info / Warning / Critical
  Title + Body
  → POST /admin/broadcast
  → Notification for EVERY active user
  → WebSocket push (instant, real-time)
  → Audit log entry
```

### Visual Identity (Gold Tier)

| Who | Avatar | Role Label | Special |
|---|---|---|---|
| User | Blue gradient (initial) | "Trader" (muted) | — |
| Admin | 🛡 Gold gradient | "🛡 Admin" (amber glow) | Gold border on profile card |
| Super Admin | ⭐ Bright gold | "⭐ Super Admin" (gold text-shadow) | Stronger glow |

- Admin nav link: gold left-border accent + gold icon + bold text
- Admin page: 👑 crown with pulsing CSS animation
- Role pills in user table: shimmer gradient for Super Admin

---

## 💸 Sell / Portfolio Flow

### Sell Modal (Portfolio Page)

Position par **"Sell"** click karo:

```
Position Summary:
  Stock name | Unrealized P&L (green/red)
  Holding: X shares | Avg buy: ₹Y | Live: ₹Z

Quantity:
  [Input]  [Sell All ← one click]
  Max: N shares (bot-held excluded)

Amount Breakdown:
  Sell value (qty × live price):         ₹ X
  Est. charges (STT + exchange + GST):  -₹ Y
  ─────────────────────────────────────────
  You will receive:                      ₹ Z  (bold)
  Est. realized P&L:                    +₹ W  (green/red)

[Cancel]  [Sell N SYMBOL]
```

**Post-sell toast:**
```
"Sold 50 RELIANCE — received ₹1,23,456"
"Realised P&L: +₹4,200 · Charges: ₹185"
```

### Backend: Cash Return Logic

```python
# broker.py — fill() on SELL
acc.cash += value - fee           # cash wapas account mein
realized = (px - pos.avg_price) * qty - fee
acc.realized_pnl += realized      # realized P&L track
pos.quantity -= qty               # position reduce
```

---

## 📡 API Documentation

**Interactive Docs:** `http://localhost:8000/docs`

### Endpoints Reference

```
AUTH
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/refresh
  POST /api/v1/auth/logout
  POST /api/v1/auth/forgot-password
  POST /api/v1/auth/reset-password
  GET  /api/v1/auth/me

MARKETS
  GET  /api/v1/instruments
  GET  /api/v1/instruments/{symbol}
  GET  /api/v1/instruments/{symbol}/chart
  CRUD /api/v1/watchlists...

TRADING
  POST /api/v1/orders
  GET  /api/v1/orders
  POST /api/v1/orders/{id}/cancel
  GET  /api/v1/trades
  GET  /api/v1/portfolio
  GET  /api/v1/portfolio/equity
  GET  /api/v1/portfolio/analytics
  PATCH /api/v1/portfolio/positions/{symbol}
  GET/PUT /api/v1/portfolio/risk-limits
  POST /api/v1/portfolio/reset

STRATEGY
  GET  /api/v1/strategy/meta
  POST /api/v1/strategy/evaluate
  GET  /api/v1/strategy/signal/{symbol}/latest
  CRUD /api/v1/backtests...
  CRUD /api/v1/bots...

ALERTS
  CRUD /api/v1/alerts...
  GET  /api/v1/notifications
  POST /api/v1/notifications/read-all

ADMIN (require_admin / require_super_admin)
  GET  /api/v1/admin/stats
  GET  /api/v1/admin/users
  PATCH /api/v1/admin/users/{id}
  POST /api/v1/admin/users/{id}/topup       [NEW]
  POST /api/v1/admin/broadcast              [NEW]
  GET  /api/v1/admin/instruments            [NEW]
  POST /api/v1/admin/instruments/{s}/toggle
  GET  /api/v1/admin/bots
  GET  /api/v1/admin/audit
  POST /api/v1/admin/kill-switch            (super admin only)

WEBSOCKET
  WS /api/v1/ws?token=...
  Messages: ticks | order | notification | kill_switch | bot_event
```

---

## 🗄 Database Models

```
User            email, password_hash, role, is_active
RefreshToken    user_id, token_hash, expires_at, revoked_at
Account         user_id, cash, starting_cash, realized_pnl, risk_limits
Instrument      symbol, name, exchange, last_price, prev_close
Candle          instrument_id, ts, open, high, low, close, volume
Watchlist       user_id, name
WatchlistItem   watchlist_id, instrument_id
Order           account_id, instrument_id, side, order_type, qty, status
Trade           order_id, account_id, side, qty, price, fees, realized_pnl
Position        account_id, instrument_id, qty, avg_price, stop_loss, target
EquitySnapshot  account_id, ts, equity, cash
Bot             user_id, instrument_id, params, status, position_qty, pnl
BotLog          bot_id, ts, level, event, message
Backtest        user_id, params, metrics, equity_curve, trades, walk_forward
Alert           user_id, instrument_id, condition (ABOVE/BELOW), price
Notification    user_id, kind, title, body, is_read
AuditLog        user_id, action, target, detail, ip
PlatformSetting key, value (JSON) — kill_switch etc.
```

> **Note:** Money `DOUBLE` mein store hota hai — virtual money ke liye theek hai.
> Asli paise ke liye `Numeric(18, 4)` mein migrate karna padega.

---

## ⚖️ Risk Management

### Pre-Trade Checks (BUY only)

```
1. Platform kill switch active?                         → REJECT
2. Daily loss limit breached?
   equity <= day_start_equity × (1 - daily_loss_limit) → REJECT
3. Daily trade count exceeded?                          → REJECT
4. Max open positions reached? (new stock)              → REJECT
5. Position would exceed max_position_pct of equity?    → REJECT
6. Insufficient cash?                                   → REJECT
```

### Concurrency Safety

```python
with account_lock(account_id):           # in-process threading lock
    acc = lock_account(db, account_id)   # SELECT ... FOR UPDATE (MySQL)
    # ... checks + fill atomically
    db.commit()
```

Manual + bot order simultaneously aane par kabhi overdraft nahi hoga.

---

## 💹 Paper Broker Engine

### Indian Delivery Charges

```
STT        = 0.1% of sell value
Exchange   = 0.00297% + SEBI 0.0001%
GST        = 18% on exchange fees
Stamp Duty = 0.015% on buy value  (buy side only)
Slippage   = 0.07% (market orders)
```

### Fill Logic

```
MARKET → fills immediately at last_price ± slippage
LIMIT  → waits; fills when price <= limit (buy) or >= limit (sell)
STOP   → waits; triggers when price >= stop (buy) or <= stop (sell)
```

---

## 🤖 Bot Lifecycle

```
DRAFT ──[run backtest]──► BACKTESTED
                                │
                    [start, params match backtest]
                                │
                           RUNNING <──────────────┐
                                │                  │
                          [pause]             [resume]
                                │                  │
                           PAUSED ────────────────►┘
                                │
                     [stop] or [error]
                    ┌───────────┴───────────┐
                    ▼                       ▼
                STOPPED                   ERROR
```

**Sandbox per bar:**
```python
subprocess.run([...], timeout=10, cpu_limit=5s, memory_limit=512MB)
```
Crash/timeout/OOM sab gracefully caught → bot ERROR state mein jaata hai.

---

## 📊 Backtesting

```bash
cd backend
python -m scripts.demo_backtest path/to/nse_data.csv
# CSV: date,open,high,low,close,volume
```

**Pipeline:**
1. Historical candles load
2. Bar-by-bar strategy simulation (no look-ahead bias)
3. Fill at next bar open (realistic)
4. Metrics: Sharpe, Calmar, Max Drawdown, Win Rate, Profit Factor
5. Walk-forward: in-sample train → out-of-sample test
6. Robustness: +-20% parameter sweep

---

## 🐳 Deployment

### Docker Compose

```bash
cp .env.example .env
# .env mein set karo:
# JWT_SECRET=32+ char random string
# MYSQL_PASSWORD=...
# MYSQL_ROOT_PASSWORD=...
# SEED_DEMO=false          ← PRODUCTION MEIN ZAROORI
# PUBLIC_URL=https://your-domain.com

docker compose up --build -d
# http://localhost:8080
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | SQLite | `mysql+pymysql://user:pass@host/db` |
| `JWT_SECRET` | *required* | Min 32 chars |
| `STARTING_CASH` | 1000000 | Virtual starting money (₹10 lakh) |
| `SEED_DEMO` | true | Create demo users on startup |
| `ENABLE_SIMULATOR` | true | Start tick generator |
| `TICK_SECONDS` | 1 | Seconds per tick |
| `TICKS_PER_BAR` | 30 | Ticks per practice bar |
| `CORS_ORIGINS` | localhost | Allowed origins |

---

## ⚙️ CI/CD Pipeline

### GitHub Actions

**CI (`ci.yml`) — Every push/PR:**
```
Backend:
  Python 3.12 + pip cache
  Ruff linter
  pytest (87 tests)

Frontend:
  Node 22 + npm cache
  TypeScript typecheck (tsc -b)
  Vitest (10 tests)
  Vite production build

Docker:
  Build backend + frontend images
  docker compose config validate
```

**CD (`cd.yml`) — Push to main:**
```
Build Docker images
Push to ghcr.io with tags: latest + sha-{commit}
If SSH secrets set:
  → SSH to server
  → Pull new images
  → docker compose up -d
  → Wait for healthchecks
```

**Dependabot — Weekly:**
- pip, npm, GitHub Actions versions update

---

## 📥 NSE Real Data Import

```bash
cd backend

# NSE → All Reports → Equities → Bhavcopy download
python -m scripts.import_bhavcopy ~/Downloads/bhav/*.zip \
    --symbols RELIANCE,TCS,INFY,HDFC

# Corporate actions (split/bonus back-adjustment)
python -m scripts.corporate_actions RELIANCE \
    --ex-date 2024-10-28 --bonus 1:1

# Supported: .zip, .csv (legacy + UDiFF format)
```

> Import ke baad us stock ki simulated history delete hoti hai.
> Live ticks abhi bhi simulated rehte hain.

---

## ⚠️ Known Limitations

| Area | Limitation |
|---|---|
| **Scale** | Single worker — simulator + WebSocket same process |
| **Email** | Reset link sirf server log mein (SMTP configure nahi) |
| **Money type** | `DOUBLE` — asli paise ke liye `Numeric(18,4)` chahiye |
| **Charges** | Approximate — actual rates verify karo |
| **Calendar** | Holidays config se — practice market 24x7 hai |
| **Short Selling** | `allow_short=False` by default |
| **Fonts** | Google Fonts CDN se — offline = system fonts |
| **Real-time** | Simulated ticks only — asli NSE feed ke liye vendor chahiye |

---

## 🎭 Demo Credentials

| Role | Email | Password | Access |
|---|---|---|---|
| **Super Admin** | `admin@example.com` | `Admin@12345` | Everything + kill switch |
| **Regular User** | `demo@example.com` | `Demo@12345` | Trading, bots, portfolio |

> **PRODUCTION MEIN `SEED_DEMO=false` RAKHNA ZAROORI HAI!**

---

## 🧪 Tests

```bash
# Backend
cd backend
python -m pytest -q
# → 87 passed, 1 skipped

# Frontend
cd frontend
npm test              # 10 tests
npm run typecheck     # tsc -b
npm run build         # full production build
```

---

## 📝 Algorithm Disclaimer

> **Strategy profitable hai ya nahi — pata nahi.**
>
> v1.2 weights entry threshold reachable karne ke liye tune kiye gaye hain — profit ke liye nahi.
> Synthetic data par results flat ya negative hain, jo expected hai.
>
> Paper trading se pehle:
> 1. `demo_backtest.py` kai NSE stocks par chalaiye
> 2. Robustness check (+-20% sweep)
> 3. Walk-forward validation
> 4. Holdout data sirf **ek baar, sabse aakhir mein**

---

## 📜 License

MIT — Educational / practice use ke liye.
Asli trading mein use karne se pehle proper financial advice lo.

---

<div align="center">

**TradeBot v1.2** — Built for learning quantitative trading

*Sab paisa virtual hai. Koi asli financial advice nahi.*

</div>
