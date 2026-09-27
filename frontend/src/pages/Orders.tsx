import { useState } from "react";
import { post } from "../api/client";
import type { Fill, Order, Paged } from "../api/types";
import { Badge, Button, Empty, ErrorBox, Loading, Panel, SymbolLink, Tabs } from "../components/ui";
import { dateTime, money, signedMoney, tone } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

type Tab = "open" | "all" | "trades";

export default function Orders() {
  const [tab, setTab] = useState<Tab>("open");
  const [source, setSource] = useState("");
  const toast = useToast();
  const path = tab === "trades" ? null : `/orders?limit=200${tab === "open" ? "&status=OPEN" : ""}${source ? `&source=${source}` : ""}`;
  const orders = useApi<Paged<Order>>(path);
  const trades = useApi<Paged<Fill>>(tab === "trades" ? "/trades?limit=300" : null);
  useLiveRefresh(["order"], () => { void orders.reload(); void trades.reload(); }, 800);
  const [cancelling, setCancelling] = useState<number | null>(null);

  async function cancel(id: number) {
    setCancelling(id);
    try { await post(`/orders/${id}/cancel`); toast("Order cancelled", "success"); await orders.reload(); }
    catch (e) { toast("Couldn't cancel", "error", (e as Error).message); } finally { setCancelling(null); }
  }

  return (
    <>
      <div className="page-head"><div><h1>Orders</h1><p>Everything you, your bots and your stop-losses have sent to the practice broker.</p></div></div>
      <Panel>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <Tabs value={tab} onChange={setTab} options={[{ value: "open", label: "Open" }, { value: "all", label: "All orders" }, { value: "trades", label: "Fills" }]} />
          {tab !== "trades" && (
            <select value={source} onChange={(e) => setSource(e.target.value)} style={{ width: "auto" }} aria-label="Placed by">
              <option value="">Placed by anyone</option><option value="MANUAL">Placed by you</option><option value="BOT">Placed by bots</option><option value="SYSTEM">Stop-loss / target</option>
            </select>
          )}
        </div>
        {tab === "trades" ? (
          trades.loading ? <Loading /> : trades.error ? <ErrorBox message={trades.error} onRetry={trades.reload} /> :
          !trades.data?.items.length ? <Empty title="No fills yet">Filled orders show up here with their charges and realised P&L.</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Time</th><th>Side</th><th>Stock</th><th className="num">Qty</th><th className="num">Price</th><th className="num">Charges</th><th className="num">Realised P&L</th></tr></thead>
              <tbody>{trades.data.items.map((t) => (
                <tr key={t.id}><td className="small">{dateTime(t.created_at)}</td><td><Badge value={t.side} /></td><td><SymbolLink symbol={t.symbol} />{t.bot_id && <span className="sub">Bot #{t.bot_id}</span>}</td>
                  <td className="num">{t.quantity}</td><td className="num">{money(t.price)}</td><td className="num">{money(t.fees)}</td>
                  <td className={`num ${tone(t.realized_pnl)}`}>{t.side === "SELL" ? signedMoney(t.realized_pnl) : "—"}</td></tr>
              ))}</tbody>
            </table></div>
          )
        ) : orders.loading ? <Loading /> : orders.error ? <ErrorBox message={orders.error} onRetry={orders.reload} /> :
          !orders.data?.items.length ? <Empty title={tab === "open" ? "No open orders" : "No orders yet"}>{tab === "open" ? "Limit and stop orders wait here until the price reaches your level." : "Place an order from any stock page."}</Empty> : (
            <div className="table-wrap"><table>
              <thead><tr><th>Time</th><th>Side</th><th>Stock</th><th>Type</th><th className="num">Qty</th><th className="num">Price</th><th>Status</th><th>By</th><th /></tr></thead>
              <tbody>{orders.data.items.map((o) => (
                <tr key={o.id}>
                  <td className="small">{dateTime(o.created_at)}</td><td><Badge value={o.side} /></td><td><SymbolLink symbol={o.symbol} /></td>
                  <td className="small">{o.order_type === "MARKET" ? "Market" : o.order_type === "LIMIT" ? `Limit ${money(o.limit_price)}` : `Stop ${money(o.stop_price)}`}</td>
                  <td className="num">{o.quantity}</td><td className="num">{money(o.avg_fill_price)}</td>
                  <td><Badge value={o.status} />{o.reject_reason && <span className="sub" style={{ maxWidth: 260 }}>{o.reject_reason}</span>}</td>
                  <td><Badge value={o.source} /></td>
                  <td className="num">{o.status === "OPEN" && <Button variant="ghost" busy={cancelling === o.id} onClick={() => void cancel(o.id)}>Cancel</Button>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
      </Panel>
    </>
  );
}
