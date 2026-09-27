import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Backtest } from "../api/types";
import { EquityChart } from "../components/charts";
import { Badge, ErrorBox, Loading, Panel, Stat, Tabs } from "../components/ui";
import { dateShort, frac, money, n, signedMoney, tone } from "../lib/format";
import { useApi } from "../lib/useApi";

const REASON: Record<string, string> = { STOP: "Stop-loss", STOP_GAP: "Stop (gap)", TARGET: "Target", TARGET_GAP: "Target (gap)", SIGNAL: "Signal exit", END: "End of test" };

export default function BacktestDetail() {
  const { id } = useParams();
  const { data: b, error, loading, reload } = useApi<Backtest>(`/backtests/${id}`);
  const [tab, setTab] = useState<"trades" | "wf" | "rb">("trades");
  if (loading) return <Loading />;
  if (error || !b) return <ErrorBox message={error ?? ""} onRetry={reload} />;
  if (b.status === "FAILED") return <ErrorBox message={`Backtest failed: ${b.error}`} />;
  const m = b.metrics ?? {};
  const bench = b.benchmark_curve;
  const bhReturn = bench && bench.length > 1 ? bench[bench.length - 1].v / bench[0].v - 1 : null;
  const tabs = [{ value: "trades" as const, label: `Trades (${b.trades?.length ?? 0})` },
    ...(b.walk_forward ? [{ value: "wf" as const, label: "Walk-forward" }] : []),
    ...(b.robustness ? [{ value: "rb" as const, label: "Robustness" }] : [])];

  return (
    <>
      <div className="page-head">
        <div><h1>Backtest #{b.id}: {b.symbol}</h1>
          <p>Algorithm v{b.algorithm_version}{Object.keys(b.params).length ? ` with ${Object.entries(b.params).map(([k, v]) => `${k} ${v}`).join(", ")}` : " with default parameters"}. {b.bars} bars, {b.start && dateShort(b.start)} to {b.end && dateShort(b.end)}.</p></div>
        <Link className="btn" to={`/strategy?symbol=${b.symbol}`}>Tune in strategy lab</Link>
      </div>
      <div className="notice">Past results don't predict future returns. Synthetic history has no real edge, so treat these numbers as a check that the pipeline works, not as proof of profit.</div>
      <div className="stats" style={{ marginBottom: 18 }}>
        <Stat label="Total return" value={<span className={tone(m.total_return)}>{frac(m.total_return, 2, true)}</span>} sub={bhReturn != null ? `Buy & hold ${frac(bhReturn, 2, true)}` : undefined} />
        <Stat label="Max drawdown" value={frac(m.max_drawdown)} />
        <Stat label="Sharpe" value={n(m.sharpe)} sub={`CAGR ${frac(m.cagr, 1, true)}`} />
        <Stat label="Win rate" value={frac(m.win_rate, 0)} sub={`Profit factor ${n(m.profit_factor)}`} />
        <Stat label="Trades" value={m.trade_count ?? 0} sub={`Avg ${signedMoney(m.avg_trade)}`} />
        <Stat label="Costs" value={money((m.fees_paid ?? 0) + (m.slippage_cost ?? 0), true)} sub={`${frac(m.cost_drag_pct_of_start)} of capital`} />
      </div>
      <Panel title="Equity: strategy vs buy & hold" className="stack">
        {b.equity_curve && <EquityChart data={b.equity_curve} benchmark={bench} height={300} />}
        <p className="small muted">Solid line is the strategy, dashed is buying {b.symbol} at the start and holding.</p>
      </Panel>
      <div style={{ height: 18 }} />
      <Panel>
        <Tabs value={tab} onChange={setTab} options={tabs} />
        {tab === "trades" && (!b.trades?.length ? <p className="muted">The algorithm didn't find any entry that passed all its rules in this period.</p> : (
          <div className="table-wrap"><table>
            <thead><tr><th>Entry</th><th>Exit</th><th className="num">Qty</th><th className="num">Entry price</th><th className="num">Exit price</th><th>Reason</th><th>Regime</th><th className="num">P&L</th></tr></thead>
            <tbody>{b.trades.map((t, i) => (
              <tr key={i}><td className="small">{dateShort(t.entry_time)}</td><td className="small">{t.exit_time ? dateShort(t.exit_time) : "Open"}</td>
                <td className="num">{t.qty}</td><td className="num">{money(t.entry_price)}</td><td className="num">{money(t.exit_price)}</td>
                <td className="small">{REASON[t.exit_reason] ?? t.exit_reason}</td><td><Badge value={t.regime} /></td>
                <td className={`num ${tone(t.pnl)}`}>{signedMoney(t.pnl)}</td></tr>
            ))}</tbody>
          </table></div>
        ))}
        {tab === "wf" && b.walk_forward && (
          <>
            <p className="small muted">Each row picks the best parameters on a training window, then trades the next unseen window with them. Consistent test results matter more than any single number.</p>
            <div className="table-wrap"><table>
              <thead><tr><th>Test window</th><th className="num">Chosen entry</th><th className="num">Chosen stop (×ATR)</th><th className="num">Test return</th><th className="num">Test trades</th><th className="num">Test max DD</th></tr></thead>
              <tbody>{b.walk_forward.map((r, i) => (
                <tr key={i}><td className="small">{dateShort(String(r.test_start))} to {dateShort(String(r.test_end))}</td>
                  <td className="num">{n(r.chosen_entry_score as number)}</td><td className="num">{n(r.chosen_atr_stop_mult as number)}</td>
                  <td className={`num ${tone(r.test_total_return as number)}`}>{frac(r.test_total_return as number, 2, true)}</td>
                  <td className="num">{r.test_trade_count ?? 0}</td><td className="num">{frac(r.test_max_drawdown as number)}</td></tr>
              ))}</tbody>
            </table></div>
          </>
        )}
        {tab === "rb" && b.robustness && (
          <>
            <p className="small muted">Each parameter is nudged by −20% to +20%. Big jumps between neighbouring rows mean the result depends on a lucky setting.</p>
            <div className="table-wrap"><table>
              <thead><tr><th>Parameter</th><th className="num">Multiplier</th><th className="num">Value</th><th className="num">Return</th><th className="num">Sharpe</th><th className="num">Trades</th></tr></thead>
              <tbody>{b.robustness.map((r, i) => (
                <tr key={i}><td>{String(r.param)}</td><td className="num">×{n(r.multiplier as number)}</td><td className="num">{n(r.value as number, 3)}</td>
                  <td className={`num ${tone(r.total_return as number)}`}>{frac(r.total_return as number, 2, true)}</td><td className="num">{n(r.sharpe as number)}</td><td className="num">{r.trade_count ?? 0}</td></tr>
              ))}</tbody>
            </table></div>
          </>
        )}
      </Panel>
    </>
  );
}
