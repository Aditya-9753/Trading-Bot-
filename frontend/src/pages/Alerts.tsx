import { useState } from "react";
import { del, post } from "../api/client";
import type { Alert, Instrument, Notification, Paged } from "../api/types";
import { Badge, Button, Empty, ErrorBox, Field, Loading, Panel, SymbolLink, Tabs } from "../components/ui";
import { money, when } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

export default function Alerts() {
  const [tab, setTab] = useState<"notifications" | "alerts">("notifications");
  const notes = useApi<{ unread: number } & Paged<Notification>>("/notifications?limit=100");
  const alerts = useApi<Alert[]>("/alerts");
  const markets = useApi<Instrument[]>("/markets");
  useLiveRefresh(["notification"], () => { void notes.reload(); void alerts.reload(); }, 500);
  const toast = useToast();
  const [f, setF] = useState({ symbol: "RELIANCE", condition: "ABOVE", price: "", note: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const last = markets.data?.find((m) => m.symbol === f.symbol)?.last_price;

  async function create(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      await post("/alerts", { ...f, price: Number(f.price) });
      toast("Alert set", "success"); setF({ ...f, price: "", note: "" }); await alerts.reload();
    } catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  async function readAll() { await post("/notifications/read-all"); await notes.reload(); }
  async function read(id: number) { await post(`/notifications/${id}/read`); await notes.reload(); }

  return (
    <>
      <div className="page-head"><div><h1>Alerts and notifications</h1><p>Fills, bot events, price alerts and platform messages.</p></div></div>
      <Tabs value={tab} onChange={setTab} options={[
        { value: "notifications", label: `Notifications${notes.data?.unread ? ` (${notes.data.unread} new)` : ""}` },
        { value: "alerts", label: "Price alerts" }]} />
      {tab === "notifications" ? (
        <Panel action={notes.data?.unread ? <Button variant="ghost" onClick={() => void readAll()}>Mark all as read</Button> : undefined} title="Latest">
          {notes.loading ? <Loading /> : notes.error ? <ErrorBox message={notes.error} onRetry={notes.reload} /> :
            !notes.data?.items.length ? <Empty title="Nothing here yet">Order fills, bot errors and triggered alerts will show up here.</Empty> :
              notes.data.items.map((x) => (
                <div key={x.id} className={`notif ${x.is_read ? "" : "unread"}`}>
                  <div style={{ flex: 1 }}>
                    <div className="t">{x.title}</div>
                    {x.body && <div className="small muted">{x.body}</div>}
                  </div>
                  <div className="small muted" style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {when(x.created_at)}
                    {!x.is_read && <div><button className="btn btn-ghost" onClick={() => void read(x.id)}>Mark read</button></div>}
                  </div>
                </div>
              ))}
        </Panel>
      ) : (
        <div className="grid g-main-side">
          <Panel title="Your alerts">
            {alerts.loading ? <Loading /> : !alerts.data?.length ? <Empty title="No price alerts">Set one with the form and we'll notify you when the price gets there.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>Stock</th><th>When price</th><th className="num">Level</th><th className="num">Now</th><th>Status</th><th /></tr></thead>
                <tbody>{alerts.data.map((a) => (
                  <tr key={a.id}>
                    <td><SymbolLink symbol={a.symbol} />{a.note && <span className="sub">{a.note}</span>}</td>
                    <td>{a.condition === "ABOVE" ? "rises to" : "falls to"}</td>
                    <td className="num">{money(a.price)}</td><td className="num">{money(a.last_price)}</td>
                    <td>{a.is_active ? <Badge value="OPEN" /> : <span className="small muted">Triggered {when(a.triggered_at)}</span>}</td>
                    <td className="num"><button className="icon-btn" aria-label="Delete alert" onClick={() => void del(`/alerts/${a.id}`).then(() => alerts.reload())}>×</button></td>
                  </tr>
                ))}</tbody>
              </table></div>
            )}
          </Panel>
          <Panel title="New price alert">
            <form onSubmit={create}>
              {err && <ErrorBox message={err} />}
              <Field label="Stock"><select value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })}>{(markets.data ?? []).map((m) => <option key={m.symbol}>{m.symbol}</option>)}</select></Field>
              <Field label="Notify me when the price">
                <select value={f.condition} onChange={(e) => setF({ ...f, condition: e.target.value })}><option value="ABOVE">rises to or above</option><option value="BELOW">falls to or below</option></select>
              </Field>
              <Field label="Price (₹)" hint={last ? `Now ${money(last)}` : undefined}><input type="number" step="0.05" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} required /></Field>
              <Field label="Note (optional)"><input value={f.note} maxLength={200} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
              <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Set alert</Button>
            </form>
          </Panel>
        </div>
      )}
    </>
  );
}
