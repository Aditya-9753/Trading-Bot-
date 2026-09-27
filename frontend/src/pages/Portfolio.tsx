import { useState } from "react";
import { patch, post } from "../api/client";
import type { Analytics, EquityPoint, Order, Portfolio as P, Position } from "../api/types";
import { EquityChart, PnlBars } from "../components/charts";
import { Button, Empty, ErrorBox, Field, LivePrice, Loading, Modal, Panel, Stat, SymbolLink, Tabs } from "../components/ui";
import { money, n, pct, signedMoney, tone } from "../lib/format";
import { useLive, useLiveRefresh } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

// Cost model mirrors backend (approximate)
const STT = 0.001, EXCH = 0.0000297 + 0.000001, GST = 0.18;
const estSellFees = (value: number) => value * STT + value * EXCH * (1 + GST);

export default function Portfolio() {
  const [tab, setTab] = useState<"holdings" | "performance">("holdings");
  const pf = useApi<P>("/portfolio");
  const an = useApi<Analytics>(tab === "performance" ? "/portfolio/analytics" : null);
  const eq = useApi<EquityPoint[]>(tab === "performance" ? "/portfolio/equity?limit=1000" : null);
  useLiveRefresh(["order", "bar"], () => { void pf.reload(); if (tab === "performance") { void an.reload(); void eq.reload(); } }, 2000);
  const [protect, setProtect] = useState<Position | null>(null);
  const [sell, setSell] = useState<Position | null>(null);

  if (pf.loading) return <Loading />;
  if (pf.error || !pf.data) return <ErrorBox message={pf.error ?? ""} onRetry={pf.reload} />;
  const p = pf.data;
  return (
    <>
      <div className="page-head"><div><h1>Portfolio</h1><p>Holdings are valued at live simulated prices.</p></div></div>
      <div className="stats" style={{ marginBottom: 18 }}>
        <Stat label="Equity" value={money(p.equity)} sub={`Started with ${money(p.starting_cash, true)}`} />
        <Stat label="Total P&L" value={<span className={tone(p.total_pnl)}>{signedMoney(p.total_pnl)}</span>} sub={pct(p.total_pnl_pct)} />
        <Stat label="Unrealised" value={<span className={tone(p.unrealized_pnl)}>{signedMoney(p.unrealized_pnl)}</span>} sub={`Realised ${signedMoney(p.realized_pnl)}`} />
        <Stat label="Cash" value={money(p.cash)} sub={`Charges paid ${money(p.fees_paid)}`} />
        <Stat label="Drawdown" value={`${n(p.drawdown_pct)}%`} sub="From peak equity" />
      </div>
      <Tabs value={tab} onChange={setTab} options={[{ value: "holdings", label: `Holdings (${p.positions.length})` }, { value: "performance", label: "Performance" }]} />
      {tab === "holdings" ? (
        <Panel>
          {p.positions.length === 0 ? <Empty title="You don't hold any stocks">Buy something from the markets page, or start a bot.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Stock</th><th className="num">Qty</th><th className="num">Avg price</th><th className="num">Live price</th><th className="num">Value</th><th className="num">P&L</th><th>Stop / target</th><th /></tr></thead>
              <tbody>{p.positions.map((x) => (
                <tr key={x.symbol}>
                  <td><SymbolLink symbol={x.symbol} />{x.bot_quantity > 0 && <span className="sub">{x.bot_quantity} held by a bot</span>}</td>
                  <td className="num">{x.quantity}</td><td className="num">{money(x.avg_price)}</td>
                  <td className="num"><LivePrice symbol={x.symbol} fallback={x.last_price} showChange={false} /></td>
                  <td className="num">{money(x.market_value)}</td>
                  <td className={`num ${tone(x.unrealized_pnl)}`}>{signedMoney(x.unrealized_pnl)}<span className="sub">{pct(x.unrealized_pct)}</span></td>
                  <td className="small">{x.stop_loss || x.target ? `${money(x.stop_loss)} / ${money(x.target)}` : <span className="muted">None</span>}</td>
                  <td className="num"><div className="row" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                    <Button variant="ghost" onClick={() => setProtect(x)}>Stop/target</Button>
                    <Button variant="ghost" onClick={() => setSell(x)}>Sell</Button></div></td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Panel>
      ) : (
        <div className="stack">
          <Panel title="Equity over time">
            {eq.loading ? <Loading /> : (eq.data?.length ?? 0) < 2 ? <p className="muted">Equity is recorded each time a practice bar closes. Check back in a minute.</p> :
              <EquityChart data={eq.data!.map((e) => ({ t: e.t, v: e.equity }))} />}
          </Panel>
          {an.loading ? <Loading /> : an.data && (
            <div className="grid g2">
              <Panel title="Closed trades">
                {an.data.closed_trades === 0 ? <p className="muted">No closed trades yet. Stats appear after your first sell.</p> : (
                  <dl className="kv">
                    <dt>Closed trades</dt><dd>{an.data.closed_trades}</dd>
                    <dt>Win rate</dt><dd>{an.data.win_rate ?? "—"}%</dd>
                    <dt>Average win</dt><dd className="gain">{signedMoney(an.data.avg_win)}</dd>
                    <dt>Average loss</dt><dd className="loss">{signedMoney(an.data.avg_loss)}</dd>
                    <dt>Profit factor</dt><dd>{an.data.profit_factor ?? "—"}</dd>
                    <dt>Largest win</dt><dd>{signedMoney(an.data.largest_win)}</dd>
                    <dt>Largest loss</dt><dd>{signedMoney(an.data.largest_loss)}</dd>
                    <dt>Max drawdown</dt><dd>{n(an.data.max_drawdown_pct)}%</dd>
                  </dl>
                )}
              </Panel>
              <Panel title="Realised P&L by stock">
                {an.data.by_symbol.length ? <PnlBars data={an.data.by_symbol.map((s) => ({ label: s.symbol, value: s.pnl }))} /> : <p className="muted">Nothing realised yet.</p>}
                {an.data.by_source.length > 0 && <p className="small muted">{an.data.by_source.map((s) => `${s.source === "BOT" ? "Bots" : "You"}: ${signedMoney(s.pnl)}`).join(". ")}.</p>}
              </Panel>
            </div>
          )}
        </div>
      )}
      <ProtectModal pos={protect} onClose={() => setProtect(null)} onSaved={() => { setProtect(null); void pf.reload(); }} />
      <SellModal pos={sell} onClose={() => setSell(null)} onSold={() => { setSell(null); void pf.reload(); }} />
    </>
  );
}

// ── Sell Modal ────────────────────────────────────────────────────────────────
function SellModal({ pos, onClose, onSold }: { pos: Position | null; onClose(): void; onSold(): void }) {
  const toast = useToast();
  const live = useLive();
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [key, setKey] = useState<string | null>(null);

  // Reset form when position changes
  if (pos && key !== pos.symbol) {
    setKey(pos.symbol);
    setQty(String(pos.quantity));
    setErr(null);
  }

  if (!pos) return null;

  const livePrice = live.prices[pos.symbol]?.price ?? pos.last_price;
  const q = Math.min(Math.max(1, Math.floor(Number(qty) || 0)), pos.quantity);
  const sellValue = q * livePrice * (1 - 0.0007); // after slippage
  const fees = estSellFees(sellValue);
  const youReceive = sellValue - fees;
  const costBasis = q * pos.avg_price;
  const estPnl = youReceive - costBasis;

  async function executeSell() {
    if (q <= 0) return setErr("Quantity must be at least 1.");
    setErr(null);
    setBusy(true);
    try {
      const o = await post<Order>("/orders", {
        symbol: pos!.symbol,
        side: "SELL",
        order_type: "MARKET",
        quantity: q,
      });
      const received = o.avg_fill_price ? o.avg_fill_price * q - (o.fees ?? 0) : youReceive;
      const pnlApprox = received - q * pos!.avg_price;
      toast(
        `Sold ${q} ${pos!.symbol} — received ${money(received)}`,
        "success",
        `Realised P&L: ${pnlApprox >= 0 ? "+" : ""}${money(pnlApprox)} · Charges: ${money(o.fees ?? fees)}`
      );
      onSold();
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const freeQty = pos.quantity - pos.bot_quantity;

  return (
    <Modal title={`Sell ${pos.symbol}`} open={!!pos} onClose={onClose}>
      {/* Position summary */}
      <div style={{
        background: "var(--surface-2, rgba(255,255,255,0.04))",
        border: "1px solid var(--border, rgba(255,255,255,0.08))",
        borderRadius: 10,
        padding: "14px 16px",
        marginBottom: 16,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ fontWeight: 600, fontSize: "1.05rem" }}>{pos.name}</span>
          <span className={tone(pos.unrealized_pnl)} style={{ fontWeight: 600 }}>{signedMoney(pos.unrealized_pnl)} ({pct(pos.unrealized_pct)})</span>
        </div>
        <div style={{ display: "flex", gap: 24, fontSize: "0.85rem", color: "var(--muted, #888)" }}>
          <span>Holding: <b style={{ color: "var(--text)" }}>{pos.quantity}</b> shares</span>
          <span>Avg buy: <b style={{ color: "var(--text)" }}>{money(pos.avg_price)}</b></span>
          <span>Live: <b style={{ color: "var(--text)" }}>{money(livePrice)}</b></span>
        </div>
        {pos.bot_quantity > 0 && (
          <p style={{ marginTop: 8, fontSize: "0.82rem", color: "var(--warn, #f5a623)" }}>
            ⚠ {pos.bot_quantity} shares managed by a bot. Max sellable: {freeQty}.
          </p>
        )}
      </div>

      {/* Quantity input */}
      <Field label="Quantity to sell" hint={`Max: ${freeQty} shares`}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            id="sell-qty-input"
            type="number"
            inputMode="numeric"
            min={1}
            max={freeQty}
            step={1}
            value={qty}
            onChange={(e) => { setQty(e.target.value); setErr(null); }}
            style={{ flex: 1 }}
          />
          <button
            type="button"
            className="btn-ghost"
            style={{
              padding: "0 14px",
              borderRadius: 8,
              border: "1px solid var(--border, rgba(255,255,255,0.12))",
              background: "transparent",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "0.82rem",
              whiteSpace: "nowrap",
              color: "var(--accent, #6c63ff)",
            }}
            onClick={() => { setQty(String(freeQty)); setErr(null); }}
          >
            Sell All
          </button>
        </div>
      </Field>

      {/* Amount breakdown */}
      <div style={{
        background: "var(--surface-2, rgba(255,255,255,0.03))",
        border: "1px solid var(--border, rgba(255,255,255,0.07))",
        borderRadius: 10,
        padding: "14px 16px",
        marginTop: 4,
        marginBottom: 16,
      }}>
        <dl className="kv" style={{ margin: 0 }}>
          <dt>Sell value ({q} × {money(livePrice)})</dt><dd>{money(sellValue)}</dd>
          <dt>Est. charges (STT + exchange + GST)</dt><dd style={{ color: "var(--loss, #ef4444)" }}>−{money(fees)}</dd>
          <dt style={{ fontWeight: 700 }}>You will receive</dt>
          <dd style={{ fontWeight: 700, fontSize: "1.1rem", color: "var(--text)" }}>{money(youReceive)}</dd>
          <dt style={{ borderTop: "1px solid var(--border, rgba(255,255,255,0.07))", paddingTop: 10, marginTop: 8 }}>
            Est. realised P&L
          </dt>
          <dd style={{
            borderTop: "1px solid var(--border, rgba(255,255,255,0.07))",
            paddingTop: 10,
            marginTop: 8,
            fontWeight: 700,
            color: estPnl >= 0 ? "var(--gain, #22c55e)" : "var(--loss, #ef4444)",
          }}>
            {estPnl >= 0 ? "+" : ""}{money(estPnl)}
          </dd>
        </dl>
      </div>

      {err && <ErrorBox message={err} />}

      <div className="row-end" style={{ gap: 10 }}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button
          variant="sell"
          busy={busy}
          onClick={executeSell}
          style={{ minWidth: 160 }}
        >
          Sell {q} {pos.symbol}
        </Button>
      </div>
    </Modal>
  );
}

// ── Protect Modal ─────────────────────────────────────────────────────────────
function ProtectModal({ pos, onClose, onSaved }: { pos: Position | null; onClose(): void; onSaved(): void }) {
  const toast = useToast();
  const [sl, setSl] = useState("");
  const [tg, setTg] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [key, setKey] = useState<string | null>(null);
  if (pos && key !== pos.symbol) { setKey(pos.symbol); setSl(pos.stop_loss?.toString() ?? ""); setTg(pos.target?.toString() ?? ""); setErr(null); }
  async function save() {
    setBusy(true); setErr(null);
    try {
      await patch(`/portfolio/positions/${pos!.symbol}`, { stop_loss: sl ? Number(sl) : null, target: tg ? Number(tg) : null });
      toast("Stop-loss and target saved", "success"); onSaved();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Modal title={`Protect ${pos?.symbol ?? ""}`} open={!!pos} onClose={() => { setKey(null); onClose(); }}>
      {pos && <>
        <p className="muted">When the live price crosses either level, your free shares are sold at market. Leave a box empty to remove that level. Live price {money(pos.last_price)}.</p>
        {err && <ErrorBox message={err} />}
        <div className="grid g2" style={{ gap: 12 }}>
          <Field label="Stop-loss" hint="Below the live price"><input type="number" step="0.05" value={sl} onChange={(e) => setSl(e.target.value)} /></Field>
          <Field label="Target" hint="Above the live price"><input type="number" step="0.05" value={tg} onChange={(e) => setTg(e.target.value)} /></Field>
        </div>
        <div className="row-end"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" busy={busy} onClick={save}>Save levels</Button></div>
      </>}
    </Modal>
  );
}
