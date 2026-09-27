import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { Dashboard as D, Instrument } from "../api/types";
import { Badge, Empty, ErrorBox, LivePrice, Loading, Panel, SymbolLink } from "../components/ui";
import SignalGauge from "../components/SignalGauge";
import { money, pct, signedMoney, tone, when } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/useApi";
import { useLive, useLiveRefresh } from "../lib/live";

type MarketTab = "MOVERS" | "EQUITY" | "CRYPTO" | "INDEX";

export default function Dashboard() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useApi<D>("/dashboard");
  const { data: markets } = useApi<Instrument[]>("/markets");
  const { prices } = useLive();
  const [marketTab, setMarketTab] = useState<MarketTab>("MOVERS");

  useLiveRefresh(["order", "bot", "bar"], reload, 3000);

  // Top ticker items for quick pulse
  const topTickers = useMemo(() => {
    if (!markets) return [];
    const targets = ["NIFTY50", "SENSEX", "BANKNIFTY", "BTC", "ETH", "SOL", "RELIANCE", "TCS"];
    return targets
      .map((sym) => markets.find((m) => m.symbol === sym))
      .filter((m): m is Instrument => Boolean(m));
  }, [markets]);

  // Market glance rows for the active tab
  const marketRows = useMemo(() => {
    if (!markets) return [];
    if (marketTab === "MOVERS") {
      const getChg = (i: Instrument) => prices[i.symbol]?.change_pct ?? i.change_pct;
      return [...markets].sort((a, b) => Math.abs(getChg(b)) - Math.abs(getChg(a))).slice(0, 6);
    }
    return markets.filter((m) => (m.asset_type || "EQUITY") === marketTab).slice(0, 6);
  }, [markets, marketTab, prices]);

  if (loading) return <Loading />;
  if (error || !data) return <ErrorBox message={error ?? "Could not load"} onRetry={reload} />;

  const p = data.portfolio;
  const done = data.checklist.filter((c) => c.done).length;
  const leadBot =
    data.bots.items.find((b) => b.status === "RUNNING" && b.last_decision) ??
    data.bots.items.find((b) => b.last_decision);
  const hrefFor: Record<string, string> = {
    watchlist: "/watchlists",
    order: "/markets",
    backtest: "/backtests",
    bot: "/bots",
    alert: "/alerts",
  };

  // Capital allocation percentages
  const totalCap = Math.max(p.equity, 1);
  const cashPct = Math.min(100, Math.max(0, Math.round((p.cash / totalCap) * 100)));
  const investedPct = Math.min(100, Math.max(0, 100 - cashPct));

  // User role label
  const roleName = user?.role === "SUPER_ADMIN" ? "Super Admin" : user?.role === "ADMIN" ? "Admin" : "Trader";

  return (
    <>
      {/* ── Futuristic Hero Box with Pulse Tickers ───────────────────── */}
      <div className="dash-hero-box">
        <div className="dash-hero-top">
          <div className="dash-hero-welcome">
            <div className="dash-user-title">
              <span>Hello, {user?.full_name ? user.full_name.split(" ")[0] : "Trader"}</span>
              <span
                className={`dash-user-role-badge ${
                  user?.role === "SUPER_ADMIN"
                    ? "role-pill super"
                    : user?.role === "ADMIN"
                    ? "role-pill admin"
                    : "role-pill user"
                }`}
              >
                {user?.role === "SUPER_ADMIN" ? "👑 " : user?.role === "ADMIN" ? "🛡️ " : "💼 "}
                {roleName}
              </span>
            </div>
            <div className="dash-hero-sub">
              <span>Practice Account Active</span>
              <span>•</span>
              <span className="dash-pulse-badge">
                <span className="pulse-dot" />
                Live 24x7 Simulator (1 tick/s)
              </span>
              {data.kill_switch && (
                <span className="badge badge-bad" style={{ marginLeft: 6 }}>
                  ⚠️ Kill Switch Active
                </span>
              )}
            </div>
          </div>

          {/* Quick Action Commands */}
          <div className="dash-actions-bar">
            <Link to="/markets" className="dash-action-btn primary">
              <span>⚡</span> Trade Equities
            </Link>
            <Link to="/markets" className="dash-action-btn crypto">
              <span>₿</span> Trade Crypto
            </Link>
            <Link to="/bots" className="dash-action-btn">
              <span>🤖</span> Launch Bot
            </Link>
            <Link to="/strategy" className="dash-action-btn">
              <span>🧪</span> Strategy Lab
            </Link>
          </div>
        </div>

        {/* Live Mini Ticker Strip */}
        {topTickers.length > 0 && (
          <div className="dash-ticker-strip">
            {topTickers.map((m) => {
              const live = prices[m.symbol];
              const chg = live?.change ?? m.change;
              const chgPct = live?.change_pct ?? m.change_pct;
              return (
                <Link key={m.symbol} to={`/markets/${m.symbol}`} className="dash-ticker-pill">
                  <span className="dash-ticker-sym">{m.symbol}</span>
                  <span className="dash-ticker-price">
                    <LivePrice symbol={m.symbol} fallback={m.last_price} showChange={false} />
                  </span>
                  <span className={`small ${tone(chg)}`}>{pct(chgPct)}</span>
                </Link>
              );
            })}
          </div>
        )}
      </div>

      {/* ── 4 Modern Metric Stat Cards ───────────────────────────────── */}
      <div className="dash-stat-grid">
        {/* Net Equity */}
        <div className="dash-stat-card c-equity">
          <div className="dash-stat-card-head">
            <span className="dash-stat-title">
              <span>💎</span> Net Portfolio Equity
            </span>
            <span className="badge badge-info">Live</span>
          </div>
          <div className="dash-stat-value">{money(p.equity)}</div>
          <div className="dash-stat-sub">
            <span className={tone(p.total_pnl)}>
              <b>{signedMoney(p.total_pnl)}</b> ({pct(p.total_pnl_pct)}) overall
            </span>
            <span className="muted">• Start: {money(p.starting_cash, true)}</span>
          </div>
        </div>

        {/* Today's Return */}
        <div className={`dash-stat-card c-pnl ${p.day_pnl < 0 ? "loss" : ""}`}>
          <div className="dash-stat-card-head">
            <span className="dash-stat-title">
              <span>📈</span> Today's Return
            </span>
            <span className={`badge ${p.day_pnl >= 0 ? "badge-ok" : "badge-bad"}`}>
              {pct(p.day_pnl_pct)}
            </span>
          </div>
          <div className={`dash-stat-value ${tone(p.day_pnl)}`}>
            {signedMoney(p.day_pnl)}
          </div>
          <div className="dash-stat-sub">
            <span>Realized: {signedMoney(p.realized_pnl)}</span>
            <span className="muted">• {p.trades_today} trade(s) today</span>
          </div>
        </div>

        {/* Capital Deployment & Allocation */}
        <div className="dash-stat-card c-cash">
          <div className="dash-stat-card-head">
            <span className="dash-stat-title">
              <span>🪙</span> Available Cash
            </span>
            <span className="badge badge-muted">{cashPct}% Liquid</span>
          </div>
          <div className="dash-stat-value">{money(p.cash)}</div>
          <div>
            <div className="dash-alloc-bar">
              <div className="alloc-seg alloc-cash" style={{ width: `${cashPct}%` }} title={`Cash: ${cashPct}%`} />
              <div className="alloc-seg alloc-invested" style={{ width: `${investedPct}%` }} title={`Invested: ${investedPct}%`} />
            </div>
            <div className="dash-stat-sub" style={{ marginTop: 6 }}>
              <span>Invested: <b>{money(p.invested, true)}</b> ({investedPct}%)</span>
            </div>
          </div>
        </div>

        {/* Algorithmic Bots */}
        <div className="dash-stat-card c-bots">
          <div className="dash-stat-card-head">
            <span className="dash-stat-title">
              <span>🤖</span> Algorithmic Engine
            </span>
            {data.bots.running > 0 ? (
              <span className="dash-pulse-badge" style={{ padding: "2px 8px", fontSize: "0.7rem" }}>
                <span className="pulse-dot" /> Running
              </span>
            ) : (
              <span className="badge badge-muted">Idle</span>
            )}
          </div>
          <div className="dash-stat-value">
            {data.bots.running} <span style={{ fontSize: "1rem", fontWeight: 500, color: "var(--text-muted)" }}>/ {data.bots.total} Bots</span>
          </div>
          <div className="dash-stat-sub">
            {data.bots.error > 0 ? (
              <span className="loss">⚠️ {data.bots.error} need attention</span>
            ) : data.bots.running > 0 ? (
              <span className="gain">✓ All active bots executing v1.2</span>
            ) : (
              <Link to="/bots" className="link" style={{ color: "var(--color-primary)" }}>
                + Start your first automated bot
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* ── Main Dashboard Content Grid ──────────────────────────────── */}
      <div className="grid g-main-side">
        <div className="stack">
          {/* Onboarding Checklist */}
          {done < data.checklist.length && (
            <Panel title="Trader Setup Checklist">
              <div className="progress">
                <i style={{ width: `${(done / data.checklist.length) * 100}%` }} />
              </div>
              <ul className="checklist">
                {data.checklist.map((c) => (
                  <li key={c.key} className={c.done ? "done" : ""}>
                    <span className="box" aria-hidden>
                      {c.done ? "✓" : ""}
                    </span>
                    {c.done ? <span>{c.label}</span> : <Link to={hrefFor[c.key]}>{c.label}</Link>}
                  </li>
                ))}
              </ul>
            </Panel>
          )}

          {/* Current Portfolio Holdings */}
          <Panel
            title="Portfolio Holdings"
            action={<Link to="/portfolio" className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>Manage Portfolio</Link>}
          >
            {data.positions.length === 0 ? (
              <Empty
                title="No active holdings in your portfolio"
                action={
                  <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
                    <Link className="btn btn-primary" to="/markets">
                      Browse All Markets
                    </Link>
                  </div>
                }
              >
                Start building your practice portfolio. Pick a stock or cryptocurrency below to buy with simulated cash:
                <div className="quick-picks-grid">
                  <Link to="/markets/RELIANCE" className="quick-pick-chip">
                    <span className="quick-pick-sym">RELIANCE <span className="badge-asset equity">NSE</span></span>
                    <span className="quick-pick-sub">Energy Giant</span>
                  </Link>
                  <Link to="/markets/TCS" className="quick-pick-chip">
                    <span className="quick-pick-sym">TCS <span className="badge-asset equity">NSE</span></span>
                    <span className="quick-pick-sub">IT Services</span>
                  </Link>
                  <Link to="/markets/BTC" className="quick-pick-chip">
                    <span className="quick-pick-sym">BITCOIN <span className="badge-asset crypto">CRYPTO</span></span>
                    <span className="quick-pick-sub">Top Crypto Asset</span>
                  </Link>
                  <Link to="/markets/SOL" className="quick-pick-chip">
                    <span className="quick-pick-sym">SOLANA <span className="badge-asset crypto">CRYPTO</span></span>
                    <span className="quick-pick-sub">High Speed Layer 1</span>
                  </Link>
                </div>
              </Empty>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Asset</th>
                      <th className="num">Qty</th>
                      <th className="num">Avg Buy</th>
                      <th className="num">Live Price</th>
                      <th className="num">Unrealized P&L</th>
                      <th style={{ textAlign: "right" }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.positions.map((x) => {
                      const isCrypto = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"].includes(x.symbol);
                      return (
                        <tr key={x.symbol}>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <SymbolLink symbol={x.symbol} />
                              <span className={`badge-asset ${isCrypto ? "crypto" : "equity"}`}>
                                {isCrypto ? "CRYPTO" : "NSE"}
                              </span>
                            </div>
                            <span className="sub">{x.name}</span>
                          </td>
                          <td className="num">{x.quantity}</td>
                          <td className="num">{money(x.avg_price)}</td>
                          <td className="num">
                            <LivePrice symbol={x.symbol} fallback={x.last_price} showChange={false} />
                          </td>
                          <td className={`num ${tone(x.unrealized_pnl)}`}>
                            <b>{signedMoney(x.unrealized_pnl)}</b>
                            <div className="small">{pct(x.unrealized_pct)}</div>
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <Link
                              to={`/markets/${x.symbol}`}
                              className="btn btn-secondary"
                              style={{ padding: "3px 8px", fontSize: "0.75rem" }}
                            >
                              Trade
                            </Link>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Recent Orders Stream */}
          <Panel
            title="Recent Activity & Orders"
            action={<Link to="/orders" className="btn btn-secondary" style={{ padding: "4px 10px", fontSize: "0.8rem" }}>All Orders</Link>}
          >
            {data.recent_orders.length === 0 ? (
              <p className="muted" style={{ margin: "10px 0" }}>No orders placed yet. Place an order from the markets page.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Side</th>
                      <th>Symbol</th>
                      <th className="num">Qty</th>
                      <th className="num">Filled Price</th>
                      <th>Status</th>
                      <th className="muted small" style={{ textAlign: "right" }}>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recent_orders.map((o) => (
                      <tr key={o.id}>
                        <td>
                          <Badge value={o.side} />
                        </td>
                        <td>
                          <SymbolLink symbol={o.symbol} />
                          <span className="sub">
                            {o.source === "MANUAL" ? "Manual" : o.source === "BOT" ? "Bot" : "Stop/Target"}
                          </span>
                        </td>
                        <td className="num">{o.quantity}</td>
                        <td className="num">
                          {money(o.avg_fill_price ?? o.limit_price ?? o.stop_price)}
                        </td>
                        <td>
                          <Badge value={o.status} title={o.reject_reason ?? undefined} />
                        </td>
                        <td className="muted small" style={{ textAlign: "right" }}>
                          {when(o.created_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        {/* ── Sidebar Column ─────────────────────────────────────────── */}
        <div className="stack">
          {/* Algorithmic Bot Signal Spotlight */}
          <Panel
            title={leadBot ? `Bot Engine: ${leadBot.name}` : "Algorithmic Radar"}
            action={leadBot ? <Link to={`/bots/${leadBot.id}`}>Details</Link> : <Link to="/strategy">Lab</Link>}
          >
            {leadBot?.last_decision ? (
              <>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                    <SymbolLink symbol={leadBot.symbol} />
                  </span>
                  <Badge value={leadBot.last_decision.action} />
                </div>
                <SignalGauge
                  value={leadBot.last_decision.S}
                  entry={leadBot.params.entry_score ?? 0.55}
                  exit={leadBot.params.long_exit ?? -0.25}
                  action={leadBot.last_decision.action}
                  size={260}
                />
                <div
                  style={{
                    background: "rgba(255,255,255,0.03)",
                    padding: 10,
                    borderRadius: 8,
                    marginTop: 10,
                    fontSize: "0.8rem",
                    display: "flex",
                    justifyContent: "space-between",
                  }}
                >
                  <span className="muted">Regime:</span>
                  <b>{leadBot.last_decision.regime || "Trending"}</b>
                </div>
              </>
            ) : (
              <Empty
                title="No bot currently streaming"
                action={
                  <Link className="btn btn-primary" to="/strategy">
                    Open Strategy Lab
                  </Link>
                }
              >
                TradeBot uses the <b>Hybrid Algorithm v1.2</b> combining EMA trends, RSI momentum, and ATR volatility filters.
              </Empty>
            )}
          </Panel>

          {/* Interactive Market Glance with Tabs */}
          <Panel
            title="Market Glance"
            action={
              <Link to="/markets" style={{ fontSize: "0.8rem" }}>
                All ({markets?.length ?? 28}) →
              </Link>
            }
          >
            <div className="tabs" style={{ marginBottom: 10, fontSize: "0.8rem" }}>
              <button
                type="button"
                className={marketTab === "MOVERS" ? "on" : ""}
                onClick={() => setMarketTab("MOVERS")}
              >
                🔥 Movers
              </button>
              <button
                type="button"
                className={marketTab === "EQUITY" ? "on" : ""}
                onClick={() => setMarketTab("EQUITY")}
              >
                📈 Stocks
              </button>
              <button
                type="button"
                className={marketTab === "CRYPTO" ? "on" : ""}
                onClick={() => setMarketTab("CRYPTO")}
              >
                ₿ Crypto
              </button>
              <button
                type="button"
                className={marketTab === "INDEX" ? "on" : ""}
                onClick={() => setMarketTab("INDEX")}
              >
                📊 Indices
              </button>
            </div>

            <div className="table-wrap">
              <table>
                <tbody>
                  {marketRows.map((m) => {
                    const live = prices[m.symbol];
                    const chg = live?.change ?? m.change;
                    const chgPct = live?.change_pct ?? m.change_pct;
                    const isIndex = (m.asset_type || "EQUITY") === "INDEX";
                    return (
                      <tr key={m.symbol}>
                        <td>
                          <SymbolLink symbol={m.symbol} />
                          <span className="sub" style={{ fontSize: "0.72rem" }}>
                            {m.name.split(" ")[0]}
                          </span>
                        </td>
                        <td className="num">
                          <LivePrice symbol={m.symbol} fallback={m.last_price} showChange={false} />
                        </td>
                        <td className={`num ${tone(chg)}`}>
                          <b>{pct(chgPct)}</b>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <Link
                            to={`/markets/${m.symbol}`}
                            className="btn btn-secondary"
                            style={{ padding: "2px 8px", fontSize: "0.72rem" }}
                          >
                            {isIndex ? "View" : "Trade"}
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
