import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { post } from "../api/client";
import type { Backtest, Evaluation, Instrument, StrategyMeta, TunableParam } from "../api/types";
import { Contributions, SignalChart } from "../components/charts";
import SignalGauge from "../components/SignalGauge";
import { Button, ErrorBox, Field, Loading, Panel, Stat } from "../components/ui";
import { money, n, regimeLabel, score } from "../lib/format";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

export function ParamEditor({ meta, values, onChange }: { meta: StrategyMeta; values: Record<string, number>; onChange(v: Record<string, number>): void }) {
  const set = (p: TunableParam, raw: string) => {
    const v = p.type === "int" ? Math.round(Number(raw)) : Number(raw);
    const next = { ...values };
    if (Number.isNaN(v) || v === p.default) delete next[p.name]; else next[p.name] = v;
    onChange(next);
  };
  return (
    <div>
      {meta.tunable.map((p) => {
        const v = values[p.name] ?? p.default;
        const step = p.type === "int" ? 1 : p.max - p.min <= 0.1 ? 0.001 : 0.05;
        return (
          <div key={p.name} className={`param-row ${values[p.name] != null ? "changed" : ""}`}>
            <label htmlFor={`p-${p.name}`}>{p.label}</label>
            <input type="number" value={v} step={step} min={p.min} max={p.max} onChange={(e) => set(p, e.target.value)} aria-label={p.label} />
            <input id={`p-${p.name}`} type="range" min={p.min} max={p.max} step={step} value={v} onChange={(e) => set(p, e.target.value)} />
            <span className="help">{p.help}. Default {p.default}, range {p.min} to {p.max}.</span>
          </div>
        );
      })}
    </div>
  );
}

export default function StrategyLab() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const toast = useToast();
  const markets = useApi<Instrument[]>("/markets");
  const [version, setVersion] = useState("1.2");
  const meta = useApi<StrategyMeta>(`/strategy/params?version=${version}`);
  const [symbol, setSymbol] = useState(params.get("symbol") ?? "RELIANCE");
  const [values, setValues] = useState<Record<string, number>>({});
  const [ev, setEv] = useState<Evaluation | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [btBusy, setBtBusy] = useState(false);

  const payload = useMemo(() => ({ symbol, version, params: values, bars: 200 }), [symbol, version, values]);
  useEffect(() => {
    const t = setTimeout(async () => {
      setBusy(true);
      try { setEv(await post<Evaluation>("/strategy/evaluate", payload)); setErr(null); }
      catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
    }, 350);
    return () => clearTimeout(t);
  }, [payload]);

  async function backtest() {
    setBtBusy(true);
    try {
      const b = await post<Backtest>("/backtests", { symbol, version, params: values, walk_forward: true });
      nav(`/backtests/${b.id}`);
    } catch (e) { toast("Backtest failed", "error", (e as Error).message); } finally { setBtBusy(false); }
  }
  function makeBot() {
    const q = new URLSearchParams({ symbol, version, params: JSON.stringify(values) });
    nav(`/bots?new=1&${q.toString()}`);
  }

  return (
    <>
      <div className="page-head">
        <div><h1>Strategy lab</h1><p>See how the Hybrid algorithm scores a stock, and how your parameter changes move the signal.</p></div>
        <div className="row">
          <Button onClick={makeBot}>Create bot with these settings</Button>
          <Button variant="primary" busy={btBusy} onClick={backtest}>Run backtest</Button>
        </div>
      </div>
      <div className="grid g-main-side">
        <div className="stack">
          <Panel>
            {err && <ErrorBox message={err} />}
            {!ev ? <Loading label="Scoring" /> : (
              <div className="grid g2" style={{ alignItems: "center" }}>
                <SignalGauge value={ev.latest.S} entry={ev.thresholds.entry} exit={ev.thresholds.long_exit} action={ev.decision.action} size={320} />
                <div>
                  <div className="stats" style={{ boxShadow: "none", marginBottom: 14 }}>
                    <Stat label="Regime" value={regimeLabel[ev.latest.regime] ?? ev.latest.regime} />
                    <Stat label="Confidence" value={`${n(ev.latest.confidence, 0)}`} sub="0 to 100" />
                  </div>
                  <h3 style={{ marginBottom: 10 }}>What makes up S</h3>
                  <Contributions values={ev.latest.contributions} scores={ev.latest.scores} />
                  <p className="small muted" style={{ marginTop: 10 }}>Each bar is weight × score for the current regime. They add up to S = {score(ev.latest.S)}.
                    {ev.latest.regime === "HIGH_VOLATILITY" && " New entries are blocked while volatility is high."}</p>
                </div>
              </div>
            )}
            {busy && ev && <p className="small muted">Updating…</p>}
          </Panel>
          <Panel title="Signal score over the last 200 bars">
            {ev ? <SignalChart series={ev.series} entry={ev.thresholds.entry} exit={ev.thresholds.long_exit} /> : <Loading />}
            <p className="small muted">Shaded bands are the buy and sell zones; the dashed line is where longs exit. ATR {money(ev?.latest.atr)}, volatility ratio {n(ev?.latest.vol_ratio)}.</p>
          </Panel>
        </div>
        <Panel title="Settings">
          <Field label="Stock">
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {(markets.data ?? [{ symbol } as Instrument]).map((m) => <option key={m.symbol} value={m.symbol}>{m.symbol}</option>)}
            </select>
          </Field>
          <Field label="Algorithm version" hint={version === "1.2" ? "Default. Fixes six issues found in v1.1." : "Original spec, kept for comparison. Uses 6 components."}>
            <select value={version} onChange={(e) => { setVersion(e.target.value); setValues({}); }}>
              {(meta.data?.versions ?? ["1.2", "1.1"]).map((v) => <option key={v} value={v}>v{v}</option>)}
            </select>
          </Field>
          {meta.data ? <ParamEditor meta={meta.data} values={values} onChange={setValues} /> : <Loading />}
          {Object.keys(values).length > 0 && <Button variant="ghost" onClick={() => setValues({})}>Reset to defaults</Button>}
        </Panel>
      </div>
    </>
  );
}
