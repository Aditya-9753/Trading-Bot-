import { useState } from "react";
import { del, patch, post } from "../api/client";
import type { Instrument, Watchlist } from "../api/types";
import { Button, Confirm, Empty, ErrorBox, LivePrice, Loading, Panel, SymbolLink } from "../components/ui";
import { pct, tone } from "../lib/format";
import { useLive } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

export default function Watchlists() {
  const { data, error, loading, reload } = useApi<Watchlist[]>("/watchlists");
  const markets = useApi<Instrument[]>("/markets");
  const { prices } = useLive();
  const toast = useToast();
  const [name, setName] = useState("");
  const [adding, setAdding] = useState<Record<number, string>>({});
  const [toDelete, setToDelete] = useState<Watchlist | null>(null);

  const act = async (fn: () => Promise<unknown>, ok?: string) => {
    try { await fn(); if (ok) toast(ok, "success"); await reload(); } catch (e) { toast("That didn't work", "error", (e as Error).message); }
  };

  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <>
      <div className="page-head"><div><h1>Watchlists</h1><p>Group the stocks you want to keep an eye on.</p></div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); if (name.trim()) void act(() => post("/watchlists", { name }), "Watchlist created").then(() => setName("")); }}>
          <input placeholder="New watchlist name" value={name} onChange={(e) => setName(e.target.value)} style={{ width: 220 }} aria-label="New watchlist name" />
          <Button type="submit" variant="primary" disabled={!name.trim()}>Create watchlist</Button>
        </form>
      </div>
      {data?.length === 0 && <Panel><Empty title="No watchlists yet">Create one above, then add stocks to it.</Empty></Panel>}
      <div className="grid g2">
        {data?.map((w) => {
          const available = (markets.data ?? []).filter((m) => !w.items.some((x) => x.symbol === m.symbol));
          return (
            <Panel key={w.id} title={w.name} action={
              <div className="row">
                <Button variant="ghost" onClick={() => { const nn = prompt("Rename watchlist", w.name); if (nn?.trim()) void act(() => patch(`/watchlists/${w.id}`, { name: nn })); }}>Rename</Button>
                <Button variant="ghost" onClick={() => setToDelete(w)}>Delete</Button>
              </div>}>
              {w.items.length === 0 ? <p className="muted">Empty. Add a stock below.</p> : (
                <table><tbody>{w.items.map((i) => (
                  <tr key={i.symbol}>
                    <td><SymbolLink symbol={i.symbol} /><span className="sub">{i.name}</span></td>
                    <td className="num"><LivePrice symbol={i.symbol} fallback={i.last_price} showChange={false} /></td>
                    <td className={`num ${tone(prices[i.symbol]?.change ?? i.change)}`}>{pct(prices[i.symbol]?.change_pct ?? i.change_pct)}</td>
                    <td className="num"><button className="icon-btn" aria-label={`Remove ${i.symbol}`} onClick={() => void act(() => del(`/watchlists/${w.id}/items/${i.symbol}`))}>×</button></td>
                  </tr>
                ))}</tbody></table>
              )}
              <div className="row" style={{ marginTop: 12 }}>
                <select value={adding[w.id] ?? ""} onChange={(e) => setAdding({ ...adding, [w.id]: e.target.value })} style={{ flex: 1 }} aria-label="Stock to add">
                  <option value="">Choose a stock</option>{available.map((m) => <option key={m.symbol} value={m.symbol}>{m.symbol}, {m.name}</option>)}
                </select>
                <Button disabled={!adding[w.id]} onClick={() => void act(() => post(`/watchlists/${w.id}/items`, { symbol: adding[w.id] })).then(() => setAdding({ ...adding, [w.id]: "" }))}>Add</Button>
              </div>
            </Panel>
          );
        })}
      </div>
      <Confirm open={!!toDelete} title="Delete watchlist?" confirmLabel="Delete watchlist" danger onClose={() => setToDelete(null)}
        body={<p>“{toDelete?.name}” will be removed. Your holdings are not affected.</p>}
        onConfirm={() => { const w = toDelete!; setToDelete(null); void act(() => del(`/watchlists/${w.id}`), "Watchlist deleted"); }} />
    </>
  );
}
