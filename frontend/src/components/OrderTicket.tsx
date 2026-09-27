import { useEffect, useState } from "react";
import { post } from "../api/client";
import type { Order, OrderType, Side } from "../api/types";
import { money } from "../lib/format";
import { useLive } from "../lib/live";
import { useToast } from "../lib/toast";
import { Button, ErrorBox, Field } from "./ui";

// Mirrors the backend CostModel defaults (approximate; the server computes the real fill).
const SLIP = 0.0007, STT = 0.001, EXCH = 0.0000297 + 0.000001, GST = 0.18, STAMP = 0.00015;
const estFees = (value: number, buy: boolean) => value * STT + value * EXCH * (1 + GST) + (buy ? value * STAMP : 0);

export default function OrderTicket({ symbol, lastPrice, held = 0, defaultSide = "BUY", onPlaced }: {
  symbol: string; lastPrice: number; held?: number; defaultSide?: Side; onPlaced?: (o: Order) => void;
}) {
  const live = useLive().prices[symbol]?.price ?? lastPrice;
  const toast = useToast();
  const [side, setSide] = useState<Side>(defaultSide);
  const [type, setType] = useState<OrderType>("MARKET");
  const [qty, setQty] = useState("1");
  const [limit, setLimit] = useState("");
  const [stop, setStop] = useState("");
  const [protect, setProtect] = useState(false);
  const [sl, setSl] = useState("");
  const [tgt, setTgt] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { setLimit(""); setStop(""); setErr(null); }, [symbol, type]);
  useEffect(() => {
    if (protect && !sl && !tgt) { setSl((live * 0.95).toFixed(2)); setTgt((live * 1.1).toFixed(2)); }
  }, [protect, live, sl, tgt]);

  const q = Math.max(0, Math.floor(Number(qty) || 0));
  const ref = type === "LIMIT" ? Number(limit) || live : type === "STOP" ? Number(stop) || live : live * (side === "BUY" ? 1 + SLIP : 1 - SLIP);
  const value = q * ref;
  const fees = estFees(value, side === "BUY");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (q <= 0) return setErr("Enter a quantity of at least 1.");
    setBusy(true);
    try {
      const o = await post<Order>("/orders", {
        symbol, side, order_type: type, quantity: q,
        limit_price: type === "LIMIT" ? Number(limit) : null, stop_price: type === "STOP" ? Number(stop) : null,
        stop_loss: side === "BUY" && protect && sl ? Number(sl) : null, target: side === "BUY" && protect && tgt ? Number(tgt) : null,
      });
      toast(o.status === "FILLED" ? `${side === "BUY" ? "Bought" : "Sold"} ${q} ${symbol} at ${money(o.avg_fill_price)}` : `${type.toLowerCase()} order placed for ${q} ${symbol}`,
        "success", o.status === "OPEN" ? "It fills automatically when the price reaches your level." : `Charges ${money(o.fees)}`);
      onPlaced?.(o);
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="ticket-form" aria-label={`Order ticket for ${symbol}`}>
      <div className="seg side" role="group" aria-label="Side" style={{ marginBottom: 14 }}>
        <button type="button" className={side === "BUY" ? "on buy" : ""} onClick={() => setSide("BUY")}>Buy</button>
        <button type="button" className={side === "SELL" ? "on sell" : ""} onClick={() => setSide("SELL")}>Sell</button>
      </div>
      <Field label="Order type">
        <select value={type} onChange={(e) => setType(e.target.value as OrderType)}>
          <option value="MARKET">Market: fill now at the live price</option>
          <option value="LIMIT">Limit: fill at my price or better</option>
          <option value="STOP">Stop: trigger when price crosses a level</option>
        </select>
      </Field>
      <Field label="Quantity" hint={side === "SELL" ? `You hold ${held}` : undefined}>
        <input type="number" inputMode="numeric" min={1} step={1} value={qty} onChange={(e) => setQty(e.target.value)} required />
      </Field>
      {type === "LIMIT" && (
        <Field label="Limit price" hint={`Live ${money(live)}`}>
          <input type="number" step="0.05" min="0.05" value={limit} onChange={(e) => setLimit(e.target.value)} required />
        </Field>
      )}
      {type === "STOP" && (
        <Field label="Trigger price" hint={side === "BUY" ? "Buys when the price rises to this level" : "Sells when the price falls to this level"}>
          <input type="number" step="0.05" min="0.05" value={stop} onChange={(e) => setStop(e.target.value)} required />
        </Field>
      )}
      {side === "BUY" && (
        <>
          <label className="check"><input type="checkbox" checked={protect} onChange={(e) => setProtect(e.target.checked)} /> Add stop-loss and target</label>
          {protect && (
            <div className="grid g2" style={{ gap: 10 }}>
              <Field label="Stop-loss"><input type="number" step="0.05" value={sl} onChange={(e) => setSl(e.target.value)} /></Field>
              <Field label="Target"><input type="number" step="0.05" value={tgt} onChange={(e) => setTgt(e.target.value)} /></Field>
            </div>
          )}
        </>
      )}
      <div className="est">
        <dl className="kv">
          <dt>Approx. value</dt><dd>{money(value)}</dd>
          <dt>Est. charges</dt><dd>{money(fees)}</dd>
          <dt>{side === "BUY" ? "Total cost" : "You receive"}</dt><dd><b>{money(side === "BUY" ? value + fees : value - fees)}</b></dd>
        </dl>
      </div>
      {err && <ErrorBox message={err} />}
      <Button type="submit" variant={side === "BUY" ? "buy" : "sell"} busy={busy} style={{ width: "100%" }}>
        {side === "BUY" ? "Buy" : "Sell"} {q || ""} {symbol}
      </Button>
    </form>
  );
}
