import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { post } from "../api/client";
import type { Bot, Instrument, StrategyMeta } from "../api/types";
import { Badge, Button, Empty, ErrorBox, Field, Loading, Modal, Panel } from "../components/ui";
import { money, score, signedMoney, tone, when } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useApi } from "../lib/useApi";
import { ParamEditor } from "./StrategyLab";

export default function Bots() {
  const [sp, setSp] = useSearchParams();
  const { data, error, loading, reload } = useApi<Bot[]>("/bots");
  useLiveRefresh(["bot", "order"], reload, 1500);
  const [open, setOpen] = useState(sp.get("new") === "1");

  return (
    <>
      <div className="page-head">
        <div><h1>Bots</h1><p>A bot runs the Hybrid algorithm on one stock and trades your practice account on every closed bar.</p></div>
        <Button variant="primary" onClick={() => setOpen(true)}>Create bot</Button>
      </div>
      <div className="notice info">Every bot must pass a backtest with its current settings before it can start. Changing settings sends it back to draft.</div>
      <Panel>
        {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : !data?.length ? (
          <Empty title="No bots yet" action={<Button variant="primary" onClick={() => setOpen(true)}>Create your first bot</Button>}>
            Pick a stock and a capital amount. You can backtest and start it from the next screen.
          </Empty>
        ) : (
          <div className="table-wrap"><table>
            <thead><tr><th>Bot</th><th>Status</th><th className="num">Capital</th><th className="num">Position</th><th className="num">Last S</th><th className="num">Realised</th><th className="num">Open P&L</th><th>Last run</th></tr></thead>
            <tbody>{data.map((b) => (
              <tr key={b.id}>
                <td><Link className="sym" to={`/bots/${b.id}`}>{b.name}</Link><span className="sub">{b.symbol}, v{b.algorithm_version}</span></td>
                <td><Badge value={b.status} title={b.error_message ?? undefined} /></td>
                <td className="num">{money(b.capital_allocation, true)}</td>
                <td className="num">{b.position_qty ? `${b.position_qty} @ ${money(b.entry_price)}` : <span className="muted">Flat</span>}</td>
                <td className="num">{score(b.last_decision?.S)}</td>
                <td className={`num ${tone(b.realized_pnl)}`}>{signedMoney(b.realized_pnl)}</td>
                <td className={`num ${tone(b.unrealized_pnl)}`}>{b.position_qty ? signedMoney(b.unrealized_pnl) : "—"}</td>
                <td className="small muted">{when(b.last_evaluated_at)}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Panel>
      <CreateBot open={open} onClose={() => { setOpen(false); if (sp.get("new")) setSp({}); }} preset={sp} />
    </>
  );
}

function CreateBot({ open, onClose, preset }: { open: boolean; onClose(): void; preset: URLSearchParams }) {
  const nav = useNavigate();
  const markets = useApi<Instrument[]>(open ? "/markets" : null);
  const [version, setVersion] = useState(preset.get("version") ?? "1.2");
  const meta = useApi<StrategyMeta>(open ? `/strategy/params?version=${version}` : null);
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState(preset.get("symbol") ?? "RELIANCE");
  const [capital, setCapital] = useState("200000");
  const [params, setParams] = useState<Record<string, number>>(() => { try { return JSON.parse(preset.get("params") ?? "{}"); } catch { return {}; } });
  const [custom, setCustom] = useState(Object.keys(params).length > 0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (!name) setName(`${symbol} trend bot`); }, [symbol]); // eslint-disable-line

  async function create(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const b = await post<Bot>("/bots", { name, symbol, version, params: custom ? params : {}, capital_allocation: Number(capital) });
      nav(`/bots/${b.id}`);
    } catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Create bot" open={open} onClose={onClose} wide>
      <form onSubmit={create}>
        {err && <ErrorBox message={err} />}
        <div className="grid g2" style={{ gap: 14 }}>
          <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} /></Field>
          <Field label="Stock">
            <select value={symbol} onChange={(e) => { setSymbol(e.target.value); setName(`${e.target.value} trend bot`); }}>
              {(markets.data ?? [{ symbol } as Instrument]).map((m) => <option key={m.symbol}>{m.symbol}</option>)}
            </select>
          </Field>
          <Field label="Capital for this bot (₹)" hint="Position size is 1% risk of this amount per trade, scaled by conviction and risk.">
            <input type="number" min={10000} step={10000} value={capital} onChange={(e) => setCapital(e.target.value)} required />
          </Field>
          <Field label="Algorithm version">
            <select value={version} onChange={(e) => { setVersion(e.target.value); setParams({}); }}><option value="1.2">v1.2 (default)</option><option value="1.1">v1.1 (original)</option></select>
          </Field>
        </div>
        <label className="check"><input type="checkbox" checked={custom} onChange={(e) => setCustom(e.target.checked)} /> Customise parameters</label>
        {custom && meta.data && <ParamEditor meta={meta.data} values={params} onChange={setParams} />}
        <div className="row-end"><Button variant="ghost" type="button" onClick={onClose}>Cancel</Button><Button variant="primary" type="submit" busy={busy}>Create bot</Button></div>
      </form>
    </Modal>
  );
}
