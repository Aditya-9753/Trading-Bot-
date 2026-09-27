import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { del, patch, post } from "../api/client";
import type { Backtest, Bot, BotLog, StrategyMeta } from "../api/types";
import { Contributions } from "../components/charts";
import SignalGauge from "../components/SignalGauge";
import { Badge, Button, Confirm, ErrorBox, Field, Loading, Modal, Panel, Stat } from "../components/ui";
import { dateTime, frac, money, n, regimeLabel, signedMoney, tone, when } from "../lib/format";
import { useLiveRefresh } from "../lib/live";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";
import { ParamEditor } from "./StrategyLab";

export default function BotDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const bot = useApi<Bot>(`/bots/${id}`);
  const [level, setLevel] = useState("");
  const logs = useApi<BotLog[]>(`/bots/${id}/logs?limit=200${level ? `&level=${level}` : ""}`);
  useLiveRefresh(["bot", "order"], () => { void bot.reload(); void logs.reload(); }, 1000);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<"kill" | "stop" | "delete" | null>(null);
  const [editing, setEditing] = useState(false);

  async function action(name: string, body?: unknown) {
    setBusy(name); setConfirm(null);
    try {
      if (name === "backtest") {
        const r = await post<{ bot: Bot; backtest: Backtest }>(`/bots/${id}/backtest`, body ?? { walk_forward: true });
        bot.setData(r.bot);
        toast("Backtest finished", "success", `Return ${frac(r.backtest.metrics?.total_return, 2, true)} over ${r.backtest.metrics?.trade_count ?? 0} trades`);
      } else if (name === "delete") {
        await del(`/bots/${id}`); nav("/bots"); return;
      } else {
        bot.setData(await post<Bot>(`/bots/${id}/${name}`));
        toast({ start: "Bot started", pause: "Bot paused", resume: "Bot resumed", stop: "Bot stopped", kill: "Bot stopped and position closed" }[name] ?? "Done", "success");
      }
      void logs.reload();
    } catch (e) { toast("That didn't work", "error", (e as Error).message); } finally { setBusy(null); }
  }

  if (bot.loading) return <Loading />;
  if (bot.error || !bot.data) return <ErrorBox message={bot.error ?? ""} onRetry={bot.reload} />;
  const b = bot.data;
  const d = b.last_decision;
  const entry = b.params.entry_score ?? 0.55, exit = b.params.long_exit ?? -0.25;
  const canStart = ["BACKTESTED", "STOPPED", "ERROR"].includes(b.status) && b.backtest_current;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{b.name}</h1>
          <p><Link to={`/markets/${b.symbol}`}>{b.symbol}</Link>, algorithm v{b.algorithm_version}, capital {money(b.capital_allocation, true)}. <Badge value={b.status} /></p>
        </div>
        <div className="row">
          {(b.status === "DRAFT" || !b.backtest_current || b.status === "BACKTESTED" || b.status === "STOPPED" || b.status === "ERROR") &&
            <Button busy={busy === "backtest"} onClick={() => void action("backtest")}>{b.backtest_current ? "Backtest again" : "Run backtest"}</Button>}
          {canStart && <Button variant="primary" busy={busy === "start"} onClick={() => void action("start")}>Start bot</Button>}
          {b.status === "RUNNING" && <Button busy={busy === "pause"} onClick={() => void action("pause")}>Pause</Button>}
          {b.status === "PAUSED" && <Button variant="primary" busy={busy === "resume"} onClick={() => void action("resume")}>Resume</Button>}
          {["RUNNING", "PAUSED", "ERROR"].includes(b.status) && <Button busy={busy === "stop"} onClick={() => setConfirm("stop")}>Stop</Button>}
          {(["RUNNING", "PAUSED"].includes(b.status) || b.position_qty > 0) && <Button variant="danger" busy={busy === "kill"} onClick={() => setConfirm("kill")}>Stop and sell now</Button>}
        </div>
      </div>
      {b.status === "ERROR" && <ErrorBox message={`This bot stopped with an error: ${b.error_message}. Fix the cause, then start it again.`} />}
      {b.status === "DRAFT" && <div className="notice">Run a backtest with the current settings before this bot can start.</div>}
      <div className="stats" style={{ marginBottom: 18 }}>
        <Stat label="Position" value={b.position_qty ? `${b.position_qty} shares` : "Flat"} sub={b.position_qty ? `Entry ${money(b.entry_price)}` : "Waiting for a signal"} />
        <Stat label="Stop / target" value={b.position_qty ? money(b.stop_price) : "—"} sub={b.position_qty ? `Target ${money(b.target_price)}` : undefined} />
        <Stat label="Open P&L" value={<span className={tone(b.unrealized_pnl)}>{b.position_qty ? signedMoney(b.unrealized_pnl) : "—"}</span>} />
        <Stat label="Realised P&L" value={<span className={tone(b.realized_pnl)}>{signedMoney(b.realized_pnl)}</span>} sub={`${b.trade_count} closed trade(s)`} />
      </div>
      <div className="grid g-main-side">
        <Panel title="Activity log" action={
          <select value={level} onChange={(e) => setLevel(e.target.value)} style={{ width: "auto" }} aria-label="Filter log">
            <option value="">All events</option><option value="WARN">Warnings</option><option value="ERROR">Errors</option>
          </select>}>
          {logs.loading ? <Loading /> : !logs.data?.length ? <p className="muted">Nothing logged yet.</p> : (
            <div>{logs.data.map((l) => (
              <div key={l.id} className={`logline lv-${l.level}`}>
                <time dateTime={l.ts} title={dateTime(l.ts)}>{when(l.ts)}</time>
                <span className="ev">{l.event.replace(/_/g, " ").toLowerCase()}</span>
                <span>{l.message}</span>
              </div>
            ))}</div>
          )}
        </Panel>
        <div className="stack">
          <Panel title="Latest signal">
            {d ? (
              <>
                <SignalGauge value={d.S} entry={entry} exit={exit} action={d.action} size={280} />
                <p className="small muted" style={{ textAlign: "center" }}>{regimeLabel[d.regime] ?? d.regime}, ATR {n(d.atr)}, evaluated {when(b.last_evaluated_at)}</p>
                <Contributions values={d.contributions} />
              </>
            ) : <p className="muted">The bot scores {b.symbol} every time a practice bar closes. The first reading shows up after it starts.</p>}
          </Panel>
          <Panel title="Settings" action={<Button variant="ghost" disabled={["RUNNING", "PAUSED"].includes(b.status)} onClick={() => setEditing(true)}>Edit</Button>}>
            <dl className="kv">
              {Object.keys(b.params).length === 0 ? <><dt>Parameters</dt><dd>Defaults</dd></> :
                Object.entries(b.params).map(([k, v]) => <FragmentKV key={k} k={k} v={String(v)} />)}
              <dt>Last backtest</dt><dd>{b.last_backtest_id ? <Link to={`/backtests/${b.last_backtest_id}`}>#{b.last_backtest_id}</Link> : "None"}</dd>
              <dt>Created</dt><dd>{when(b.created_at)}</dd>
            </dl>
            {["DRAFT", "BACKTESTED", "STOPPED", "ERROR"].includes(b.status) && b.position_qty === 0 &&
              <Button variant="ghost" onClick={() => setConfirm("delete")} style={{ marginTop: 12 }}>Delete bot</Button>}
          </Panel>
        </div>
      </div>
      <Confirm open={confirm === "kill"} danger title="Stop and sell now?" confirmLabel="Stop and sell"
        body={<p>The bot stops immediately{b.position_qty ? ` and its ${b.position_qty} ${b.symbol} shares are sold at market` : ""}.</p>}
        onClose={() => setConfirm(null)} onConfirm={() => void action("kill")} />
      <Confirm open={confirm === "stop"} title="Stop this bot?" confirmLabel="Stop bot"
        body={<p>The bot stops trading.{b.position_qty ? ` Its ${b.position_qty} shares stay in your portfolio with the bot's last stop-loss (${money(b.stop_price)}) and target.` : ""}</p>}
        onClose={() => setConfirm(null)} onConfirm={() => void action("stop")} />
      <Confirm open={confirm === "delete"} danger title="Delete this bot?" confirmLabel="Delete bot"
        body={<p>Its settings and log are removed. Past orders and trades stay in your history.</p>}
        onClose={() => setConfirm(null)} onConfirm={() => void action("delete")} />
      <EditBot bot={b} open={editing} onClose={() => setEditing(false)} onSaved={(nb) => { bot.setData(nb); setEditing(false); void logs.reload(); }} />
    </>
  );
}

function FragmentKV({ k, v }: { k: string; v: string }) {
  return <><dt>{k.replace(/_/g, " ")}</dt><dd>{v}</dd></>;
}

function EditBot({ bot, open, onClose, onSaved }: { bot: Bot; open: boolean; onClose(): void; onSaved(b: Bot): void }) {
  const meta = useApi<StrategyMeta>(open ? `/strategy/params?version=${bot.algorithm_version}` : null);
  const [name, setName] = useState(bot.name);
  const [capital, setCapital] = useState(String(bot.capital_allocation));
  const [params, setParams] = useState<Record<string, number>>(bot.params);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    setBusy(true); setErr(null);
    try { onSaved(await patch<Bot>(`/bots/${bot.id}`, { name, capital_allocation: Number(capital), params })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  return (
    <Modal title="Edit bot" open={open} onClose={onClose} wide>
      {err && <ErrorBox message={err} />}
      <div className="grid g2" style={{ gap: 14 }}>
        <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Capital (₹)"><input type="number" min={10000} step={10000} value={capital} onChange={(e) => setCapital(e.target.value)} /></Field>
      </div>
      <p className="small muted">Changing parameters sends the bot back to draft; you'll need to backtest it again.</p>
      {meta.data ? <ParamEditor meta={meta.data} values={params} onChange={setParams} /> : <Loading />}
      <div className="row-end"><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" busy={busy} onClick={save}>Save changes</Button></div>
    </Modal>
  );
}
