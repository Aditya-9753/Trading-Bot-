import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { get, post } from "../api/client";
import type { Alert, ChartData, Evaluation, Instrument, Portfolio, Watchlist } from "../api/types";
import CandleChart, { Oscillator } from "../components/CandleChart";
import OrderTicket from "../components/OrderTicket";
import SignalGauge from "../components/SignalGauge";
import { Button, ErrorBox, Field, LivePrice, Loading, Panel, Tabs } from "../components/ui";
import { money, n, regimeLabel } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

const RANGES = [{ value: "120", label: "120 bars" }, { value: "250", label: "250 bars" }, { value: "500", label: "500 bars" }] as const;
type Range = (typeof RANGES)[number]["value"];

export default function StockDetail() {
  const { symbol = "" } = useParams();
  const toast = useToast();
  const [range, setRange] = useState<Range>("120");
  const [osc, setOsc] = useState<"rsi" | "macd">("rsi");
  const info = useApi<Instrument>(`/markets/${symbol}`);
  const chart = useApi<ChartData>(`/markets/${symbol}/candles?bars=${range}`);
  const pf = useApi<Portfolio>("/portfolio");
  const alerts = useApi<Alert[]>("/alerts");
  const [signal, setSignal] = useState<Evaluation | null>(null);
  const [lists, setLists] = useState<Watchlist[]>([]);
  const [alertPrice, setAlertPrice] = useState("");
  const [alertBusy, setAlertBusy] = useState(false);

  const loadSignal = () => post<Evaluation>("/strategy/evaluate", { symbol, bars: 60 }).then(setSignal).catch(() => setSignal(null));
  useEffect(() => { void loadSignal(); get<Watchlist[]>("/watchlists").then(setLists).catch(() => undefined); }, [symbol]); // eslint-disable-line
  useLiveRefresh(["bar"], () => { void chart.reload(); void loadSignal(); }, 2000);
  useLiveRefresh(["order"], () => void pf.reload(), 800);

  if (info.loading) return <Loading />;
  if (info.error || !info.data) return <ErrorBox message={info.error ?? "Not found"} onRetry={info.reload} />;
  const i = info.data;
  const pos = pf.data?.positions.find((p) => p.symbol === i.symbol);
  const myAlerts = (alerts.data ?? []).filter((a) => a.symbol === i.symbol && a.is_active);
  const lines = [
    ...(pos ? [{ price: pos.avg_price, label: `Avg ${n(pos.avg_price)}`, kind: "entry" as const }] : []),
    ...(pos?.stop_loss ? [{ price: pos.stop_loss, label: `Stop ${n(pos.stop_loss)}`, kind: "stop" as const }] : []),
    ...(pos?.target ? [{ price: pos.target, label: `Target ${n(pos.target)}`, kind: "target" as const }] : []),
    ...myAlerts.map((a) => ({ price: a.price, label: `Alert ${n(a.price)}`, kind: "alert" as const })),
  ];

  async function addAlert() {
    const px = Number(alertPrice);
    if (!px) return;
    setAlertBusy(true);
    try {
      await post("/alerts", { symbol: i.symbol, condition: px > i.last_price ? "ABOVE" : "BELOW", price: px });
      toast(`Alert set at ${money(px)}`, "success");
      setAlertPrice("");
      void alerts.reload();
    } catch (e) { toast("Couldn't set alert", "error", (e as Error).message); } finally { setAlertBusy(false); }
  }
  async function addToList(id: number) {
    try { await post(`/watchlists/${id}/items`, { symbol: i.symbol }); toast(`${i.symbol} added to watchlist`, "success"); }
    catch (e) { toast("Couldn't add", "error", (e as Error).message); }
  }

  return (
    <>
      <div className="page-head">
        <div className="symbol-head">
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <h1 style={{ margin: 0 }}>{i.symbol}</h1>
              <span
                className={`badge-asset ${
                  i.asset_type === "INDEX" ? "index" : i.asset_type === "CRYPTO" ? "crypto" : "equity"
                }`}
              >
                {i.asset_type === "INDEX" ? "BENCHMARK INDEX" : i.asset_type === "CRYPTO" ? "CRYPTO" : i.exchange || "NSE"}
              </span>
            </div>
            <p style={{ marginTop: 4 }}>{i.name}, {i.sector}</p>
          </div>
          <div className="big"><LivePrice symbol={i.symbol} fallback={i.last_price} /></div>
        </div>
        {lists.length > 0 && (
          <select style={{ width: "auto" }} value="" onChange={(e) => e.target.value && void addToList(Number(e.target.value))} aria-label="Add to watchlist">
            <option value="">Add to watchlist…</option>{lists.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
          </select>
        )}
      </div>
      <div className="grid g-main-side">
        <div className="stack">
          <Panel title="Price" action={<Tabs value={range} onChange={setRange} options={RANGES.map((r) => ({ ...r }))} />}>
            {chart.loading ? <Loading /> : chart.error || !chart.data ? <ErrorBox message={chart.error ?? ""} onRetry={chart.reload} /> : (
              <>
                <CandleChart data={chart.data} lines={lines} />
                <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
                  <Tabs value={osc} onChange={setOsc} options={[{ value: "rsi", label: "RSI 14" }, { value: "macd", label: "MACD histogram" }]} />
                </div>
                <Oscillator kind={osc} values={osc === "rsi" ? chart.data.rsi : chart.data.macd_hist} />
              </>
            )}
            <p className="small muted" style={{ marginTop: 8 }}>
              {i.data_source === "SIMULATED" ? "Simulated history." : "History from NSE bhav copies."} Each new practice bar is one simulated session compressed into a few seconds.
            </p>
          </Panel>
          <div className="grid g2">
            <Panel title="Key numbers">
              <dl className="kv">
                <dt>Previous close</dt><dd>{money(i.prev_close)}</dd>
                <dt>52-bar high</dt><dd>{money(i.high_52w)}</dd>
                <dt>52-bar low</dt><dd>{money(i.low_52w)}</dd>
                <dt>Avg volume (20)</dt><dd>{n(i.avg_volume_20, 0)}</dd>
                {pos && <><dt>You hold</dt><dd>{pos.quantity} @ {money(pos.avg_price)}</dd></>}
              </dl>
            </Panel>
            <Panel title="Price alert">
              <Field label="Notify me when the price reaches" hint={`Now ${money(i.last_price)}`}>
                <input type="number" step="0.05" value={alertPrice} onChange={(e) => setAlertPrice(e.target.value)} />
              </Field>
              <Button onClick={addAlert} busy={alertBusy} disabled={!alertPrice}>Set alert</Button>
              {myAlerts.length > 0 && <p className="small muted" style={{ marginTop: 10 }}>{myAlerts.length} active alert(s). <Link to="/alerts">Manage</Link></p>}
            </Panel>
          </div>
        </div>
        <div className="stack">
          {i.asset_type === "INDEX" ? (
            <Panel title="Benchmark Index">
              <div style={{ textAlign: "center", padding: "16px 8px" }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>📊</div>
                <h3 style={{ margin: "0 0 8px 0" }}>{i.symbol} Benchmark Index</h3>
                <p className="muted" style={{ fontSize: 13, lineHeight: 1.5, margin: "0 0 16px 0" }}>
                  Market indices like Nifty 50 and Sensex are benchmark indicators. They cannot be bought or sold directly. Trade individual equities or crypto to take positions.
                </p>
                <div className="card" style={{ background: "rgba(255,255,255,0.03)", padding: 14, borderRadius: 8, fontSize: 12, textAlign: "left", marginBottom: 16 }}>
                  <div style={{ marginBottom: 6 }}><b>Exchange:</b> {i.exchange}</div>
                  <div style={{ marginBottom: 6 }}><b>Category:</b> Benchmark Index Indicator</div>
                  <div><b>Update Frequency:</b> Real-time (1 tick / sec)</div>
                </div>
                <Link to="/markets" className="btn btn-primary" style={{ width: "100%", justifyContent: "center" }}>
                  Explore Tradeable Stocks & Crypto
                </Link>
              </div>
            </Panel>
          ) : (
            <Panel title="Trade" className="ticket">
              <OrderTicket symbol={i.symbol} lastPrice={i.last_price} held={pos?.quantity ?? 0} onPlaced={() => void pf.reload()} />
            </Panel>
          )}
          <Panel title="Hybrid signal" action={<Link to={`/strategy?symbol=${i.symbol}`}>Open in lab</Link>}>
            {signal ? (
              <>
                <SignalGauge value={signal.latest.S} entry={signal.thresholds.entry} exit={signal.thresholds.long_exit} action={signal.decision.action} compact size={260} />
                <p className="small muted" style={{ textAlign: "center", marginTop: 6 }}>Regime: {regimeLabel[signal.latest.regime] ?? signal.latest.regime}. Default v1.2 parameters.</p>
              </>
            ) : <Loading label="Scoring" />}
          </Panel>
        </div>
      </div>
    </>
  );
}
