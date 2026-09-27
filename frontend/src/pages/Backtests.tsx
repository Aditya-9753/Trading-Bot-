import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { del, post } from "../api/client";
import type { Backtest, Instrument } from "../api/types";
import { Badge, Button, Empty, ErrorBox, Field, Loading, Panel } from "../components/ui";
import { dateShort, frac, n, when } from "../lib/format";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

export default function Backtests() {
  const list = useApi<Backtest[]>("/backtests");
  const markets = useApi<Instrument[]>("/markets");
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState({ symbol: "RELIANCE", version: "1.2", capital: "1000000", wf: true, rb: false });
  const [busy, setBusy] = useState(false);

  async function run(e: React.FormEvent) {
    e.preventDefault(); setBusy(true);
    try {
      const b = await post<Backtest>("/backtests", { symbol: f.symbol, version: f.version, initial_capital: Number(f.capital), walk_forward: f.wf, robustness: f.rb });
      nav(`/backtests/${b.id}`);
    } catch (e2) { toast("Backtest failed", "error", (e2 as Error).message); } finally { setBusy(false); }
  }
  async function remove(id: number) {
    try { await del(`/backtests/${id}`); await list.reload(); } catch (e) { toast("Couldn't delete", "error", (e as Error).message); }
  }

  return (
    <>
      <div className="page-head"><div><h1>Backtests</h1><p>Replay the algorithm on past bars, with realistic Indian delivery charges and slippage.</p></div></div>
      <div className="grid g-main-side">
        <Panel title="Your backtests">
          {list.loading ? <Loading /> : list.error ? <ErrorBox message={list.error} onRetry={list.reload} /> :
            !list.data?.length ? <Empty title="No backtests yet">Run one with the form, or tune parameters first in the strategy lab.</Empty> : (
              <div className="table-wrap"><table>
                <thead><tr><th>#</th><th>Stock</th><th>Version</th><th>Period</th><th className="num">Return</th><th className="num">Max DD</th><th className="num">Sharpe</th><th className="num">Trades</th><th /></tr></thead>
                <tbody>{list.data.map((b) => {
                  const m = b.metrics ?? {};
                  return (
                    <tr key={b.id}>
                      <td><Link to={`/backtests/${b.id}`}>#{b.id}</Link><span className="sub">{when(b.created_at)}</span></td>
                      <td><b>{b.symbol}</b>{b.bot_id && <span className="sub">Bot #{b.bot_id}</span>}</td>
                      <td>v{b.algorithm_version}{Object.keys(b.params).length > 0 && <span className="sub">custom</span>}</td>
                      <td className="small">{b.start ? `${dateShort(b.start)} to ${dateShort(b.end!)}` : "—"}</td>
                      {b.status === "FAILED" ? <td colSpan={4}><Badge value="FAILED" title={b.error ?? ""} /></td> : <>
                        <td className={`num ${(m.total_return ?? 0) >= 0 ? "gain" : "loss"}`}>{frac(m.total_return, 2, true)}</td>
                        <td className="num">{frac(m.max_drawdown)}</td><td className="num">{n(m.sharpe)}</td><td className="num">{m.trade_count ?? 0}</td></>}
                      <td className="num"><button className="icon-btn" aria-label={`Delete backtest ${b.id}`} onClick={() => void remove(b.id)}>×</button></td>
                    </tr>
                  );
                })}</tbody>
              </table></div>
            )}
        </Panel>
        <Panel title="New backtest">
          <form onSubmit={run}>
            <Field label="Stock">
              <select value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value })}>
                {(markets.data ?? []).map((m) => <option key={m.symbol}>{m.symbol}</option>)}
              </select>
            </Field>
            <Field label="Algorithm version"><select value={f.version} onChange={(e) => setF({ ...f, version: e.target.value })}><option value="1.2">v1.2 (default)</option><option value="1.1">v1.1 (original)</option></select></Field>
            <Field label="Starting capital (₹)"><input type="number" min={10000} step={10000} value={f.capital} onChange={(e) => setF({ ...f, capital: e.target.value })} /></Field>
            <label className="check"><input type="checkbox" checked={f.wf} onChange={(e) => setF({ ...f, wf: e.target.checked })} /> Walk-forward test</label>
            <label className="check"><input type="checkbox" checked={f.rb} onChange={(e) => setF({ ...f, rb: e.target.checked })} /> Robustness test (slower)</label>
            <p className="small muted">Uses default parameters. To change them, use the strategy lab.</p>
            <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Run backtest</Button>
          </form>
        </Panel>
      </div>
    </>
  );
}
