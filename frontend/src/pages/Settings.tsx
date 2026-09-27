import { useEffect, useState } from "react";
import { patch, post, put } from "../api/client";
import type { RiskLimits, User } from "../api/types";
import { Button, Confirm, ErrorBox, Field, Loading, Panel } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

export default function Settings() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.full_name ?? "");
  const [pw, setPw] = useState({ cur: "", next: "" });
  const [pwErr, setPwErr] = useState<string | null>(null);
  const limits = useApi<RiskLimits>("/portfolio/risk-limits");
  const [lim, setLim] = useState<RiskLimits | null>(null);
  const [limErr, setLimErr] = useState<string | null>(null);
  const [reset, setReset] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  useEffect(() => { if (limits.data) setLim(limits.data); }, [limits.data]);

  async function run(key: string, fn: () => Promise<void>) { setBusy(key); try { await fn(); } finally { setBusy(null); } }

  return (
    <>
      <div className="page-head"><div><h1>Settings</h1><p>{user?.email}</p></div></div>
      <div className="grid g2">
        <Panel title="Profile">
          <Field label="Name"><input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} /></Field>
          <Button busy={busy === "name"} onClick={() => void run("name", async () => {
            try { setUser(await patch<User>("/auth/me", { full_name: name })); toast("Name saved", "success"); } catch (e) { toast("Couldn't save", "error", (e as Error).message); }
          })}>Save name</Button>
        </Panel>
        <Panel title="Password">
          {pwErr && <ErrorBox message={pwErr} />}
          <Field label="Current password"><input type="password" value={pw.cur} onChange={(e) => setPw({ ...pw, cur: e.target.value })} autoComplete="current-password" /></Field>
          <Field label="New password" hint="8+ characters with upper and lower case and a digit"><input type="password" value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} autoComplete="new-password" /></Field>
          <Button busy={busy === "pw"} disabled={!pw.cur || !pw.next} onClick={() => void run("pw", async () => {
            setPwErr(null);
            try { await post("/auth/change-password", { current_password: pw.cur, new_password: pw.next }); setPw({ cur: "", next: "" }); toast("Password changed", "success"); }
            catch (e) { setPwErr((e as Error).message); }
          })}>Change password</Button>
        </Panel>
        <Panel title="Risk limits">
          <p className="small muted">Checked before every new buy, including bot buys. Sells and stop-losses are never blocked.</p>
          {!lim ? <Loading /> : (
            <>
              {limErr && <ErrorBox message={limErr} />}
              <div className="grid g2" style={{ gap: 12 }}>
                <Field label="Daily loss limit (%)" hint="Blocks new buys for the day"><input type="number" step="0.5" min={0.5} max={20} value={+(lim.daily_loss_limit_pct * 100).toFixed(2)} onChange={(e) => setLim({ ...lim, daily_loss_limit_pct: Number(e.target.value) / 100 })} /></Field>
                <Field label="Max size per stock (%)" hint="Of total equity"><input type="number" step="1" min={1} max={100} value={+(lim.max_position_pct * 100).toFixed(2)} onChange={(e) => setLim({ ...lim, max_position_pct: Number(e.target.value) / 100 })} /></Field>
                <Field label="Max open positions"><input type="number" min={1} max={100} value={lim.max_open_positions} onChange={(e) => setLim({ ...lim, max_open_positions: Number(e.target.value) })} /></Field>
                <Field label="Max trades per day"><input type="number" min={1} max={1000} value={lim.max_daily_trades} onChange={(e) => setLim({ ...lim, max_daily_trades: Number(e.target.value) })} /></Field>
              </div>
              <p className="small muted">Short selling is off: the cash segment doesn't allow holding shorts overnight.</p>
              <Button variant="primary" busy={busy === "lim"} onClick={() => void run("lim", async () => {
                setLimErr(null);
                try { setLim(await put<RiskLimits>("/portfolio/risk-limits", lim)); toast("Risk limits saved", "success"); } catch (e) { setLimErr((e as Error).message); }
              })}>Save risk limits</Button>
            </>
          )}
        </Panel>
        <Panel title="Start over">
          <p>Reset your practice account to ₹10,00,000 cash. Holdings are removed, open orders cancelled and bots stopped. Your order history, backtests and bot settings are kept.</p>
          <Button variant="danger" onClick={() => setReset(true)}>Reset practice account</Button>
        </Panel>
      </div>
      <Confirm open={reset} danger title="Reset your practice account?" confirmLabel="Reset account" busy={busy === "reset"}
        body={<p>This can't be undone. All holdings disappear and cash goes back to ₹10,00,000.</p>}
        onClose={() => setReset(false)} onConfirm={() => void run("reset", async () => {
          try { await post("/portfolio/reset", { confirm: true }); toast("Practice account reset", "success"); setReset(false); } catch (e) { toast("Reset failed", "error", (e as Error).message); }
        })} />
    </>
  );
}
