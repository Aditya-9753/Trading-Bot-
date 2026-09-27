import { useState } from "react";
import { patch, post } from "../api/client";
import type { AdminStats, AdminUser, AuditEntry, Bot, Instrument } from "../api/types";
import { Badge, Button, Confirm, ErrorBox, Field, Loading, Modal, Panel, Stat, Tabs } from "../components/ui";
import { dateTime, money, when } from "../lib/format";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { useApi } from "../lib/useApi";

// ── Role badge helper ──────────────────────────────────────────────────────────
function RolePill({ role }: { role: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    SUPER_ADMIN: { label: "⭐ Super Admin", cls: "role-pill super" },
    ADMIN: { label: "🛡 Admin", cls: "role-pill admin" },
    USER: { label: "User", cls: "role-pill user" },
  };
  const { label, cls } = map[role] ?? { label: role, cls: "role-pill user" };
  return <span className={cls}>{label}</span>;
}

// ── Top-up Modal ───────────────────────────────────────────────────────────────
function TopupModal({ target, onClose, onDone }: { target: AdminUser | null; onClose(): void; onDone(): void }) {
  const toast = useToast();
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!target) return null;

  async function submit() {
    const n = Number(amount);
    if (!n || n === 0) return setErr("Enter a valid amount (use negative to deduct).");
    setErr(null); setBusy(true);
    try {
      const r = await post<{ new_cash: number }>(`/admin/users/${target!.id}/topup`, {
        amount: n,
        note,
      });
      toast(`Cash ${n > 0 ? "added to" : "deducted from"} ${target!.email}`, "success",
        `New balance: ${money(r.new_cash)}`);
      setAmount(""); setNote("");
      onDone();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title={`Cash Top-up — ${target.email}`} open={!!target} onClose={onClose}>
      <div style={{
        background: "var(--surface-2, rgba(255,215,0,0.04))",
        border: "1px solid var(--admin-gold, rgba(245,158,11,0.2))",
        borderRadius: 10, padding: "12px 16px", marginBottom: 16,
      }}>
        <p className="small muted" style={{ margin: 0 }}>
          This is a <b>practice account</b>. Adjusting cash here affects only virtual money.
          Current equity: <b style={{ color: "var(--text)" }}>{money(target.equity ?? 0)}</b>
        </p>
      </div>
      <Field label="Amount (₹)" hint="Positive to add, negative to deduct">
        <input type="number" step="1000" placeholder="e.g. 50000 or -10000"
          value={amount} onChange={(e) => { setAmount(e.target.value); setErr(null); }} />
      </Field>
      <Field label="Admin note (shown to user)">
        <input type="text" maxLength={200} placeholder="Reason for adjustment..."
          value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      {err && <div className="errorbox" role="alert"><span>{err}</span></div>}
      <div className="row-end" style={{ gap: 10 }}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" busy={busy} onClick={submit}
          style={{ background: "linear-gradient(135deg, #f59e0b, #d97706)" }}>
          Apply Cash Change
        </Button>
      </div>
    </Modal>
  );
}

// ── Broadcast Modal ────────────────────────────────────────────────────────────
function BroadcastModal({ open, onClose }: { open: boolean; onClose(): void }) {
  const toast = useToast();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<"INFO" | "WARN" | "ERROR">("INFO");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function send() {
    if (!title.trim()) return setErr("Title is required.");
    setErr(null); setBusy(true);
    try {
      const r = await post<{ recipients: number }>("/admin/broadcast", { title, body, kind });
      toast(`Broadcast sent to ${r.recipients} users`, "success");
      setTitle(""); setBody(""); onClose();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <Modal title="📢 Platform Broadcast" open={open} onClose={onClose}>
      <p className="muted small" style={{ marginBottom: 16 }}>
        Send a notification to <b>all active users</b> instantly. Use for maintenance notices, updates, or announcements.
      </p>
      <Field label="Kind">
        <select value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
          <option value="INFO">ℹ️ Info — general announcement</option>
          <option value="WARN">⚠️ Warning — important notice</option>
          <option value="ERROR">🚨 Critical — urgent alert</option>
        </select>
      </Field>
      <Field label="Title (shown as notification headline)">
        <input type="text" maxLength={160} placeholder="e.g. Scheduled maintenance at 2 AM..."
          value={title} onChange={(e) => { setTitle(e.target.value); setErr(null); }} />
      </Field>
      <Field label="Body (optional detail)">
        <textarea maxLength={500} rows={3} placeholder="Additional details..."
          value={body} onChange={(e) => setBody(e.target.value)}
          style={{ resize: "vertical", fontFamily: "inherit" }} />
      </Field>
      {err && <div className="errorbox" role="alert"><span>{err}</span></div>}
      <div className="row-end" style={{ gap: 10 }}>
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="primary" busy={busy} onClick={send}
          style={{ background: kind === "ERROR" ? undefined : kind === "WARN" ? "linear-gradient(135deg,#f59e0b,#d97706)" : undefined }}>
          Send to All Users
        </Button>
      </div>
    </Modal>
  );
}

// ── Main Admin Page ────────────────────────────────────────────────────────────
export default function Admin() {
  const { user } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState<"users" | "bots" | "instruments" | "audit">("users");
  const stats = useApi<AdminStats>("/admin/stats");
  const [q, setQ] = useState("");
  const users = useApi<AdminUser[]>(tab === "users" ? `/admin/users?q=${encodeURIComponent(q)}` : null);
  const bots = useApi<Bot[]>(tab === "bots" ? "/admin/bots" : null);
  const instruments = useApi<Instrument[]>(tab === "instruments" ? "/admin/instruments" : null);
  const audit = useApi<AuditEntry[]>(tab === "audit" ? "/admin/audit?limit=300" : null);
  const [kill, setKill] = useState<null | boolean>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [topup, setTopup] = useState<AdminUser | null>(null);
  const [showBroadcast, setShowBroadcast] = useState(false);
  const superAdmin = user?.role === "SUPER_ADMIN";

  async function updateUser(u: AdminUser, body: Partial<AdminUser>) {
    try { await patch(`/admin/users/${u.id}`, body); toast("User updated", "success"); await users.reload(); await stats.reload(); }
    catch (e) { toast("Couldn't update user", "error", (e as Error).message); }
  }

  async function toggleInstrument(symbol: string) {
    try {
      await post(`/admin/instruments/${symbol}/toggle`, {});
      toast(`${symbol} toggled`, "success");
      await instruments.reload();
    } catch (e) { toast("Failed", "error", (e as Error).message); }
  }

  async function setKillSwitch(active: boolean) {
    setBusy(true);
    try {
      const r = await post<{ bots_stopped: number; orders_cancelled: number }>("/admin/kill-switch", { active, reason });
      toast(active ? "Trading paused platform-wide" : "Trading resumed", "success",
        active ? `${r.bots_stopped} bots stopped, ${r.orders_cancelled} orders cancelled` : undefined);
      setKill(null); setReason(""); await stats.reload();
    } catch (e) { toast("Kill switch failed", "error", (e as Error).message); } finally { setBusy(false); }
  }

  if (stats.loading) return <Loading />;
  if (stats.error || !stats.data) return <ErrorBox message={stats.error ?? ""} onRetry={stats.reload} />;
  const s = stats.data;

  return (
    <>
      {/* ── Page header with admin badge ───────────────────── */}
      <div className="page-head">
        <div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="admin-crown-icon" aria-hidden>👑</span>
            Admin Control Centre
          </h1>
          <p>Platform health, user management, instruments and broadcast tools.</p>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <Button variant="ghost" onClick={() => setShowBroadcast(true)}
            style={{ borderColor: "var(--admin-gold, #f59e0b)", color: "var(--admin-gold, #f59e0b)" }}>
            📢 Broadcast
          </Button>
          {superAdmin && (
            s.kill_switch.active
              ? <Button variant="primary" onClick={() => setKill(false)}>▶ Resume Trading</Button>
              : <Button variant="danger" onClick={() => setKill(true)}>⏸ Pause All Trading</Button>
          )}
        </div>
      </div>

      {/* ── Kill switch banner ────────────────────────────── */}
      {s.kill_switch.active && (
        <div style={{
          background: "rgba(239,68,68,0.12)", border: "1px solid rgba(239,68,68,0.4)",
          borderRadius: 10, padding: "12px 18px", marginBottom: 18,
          display: "flex", alignItems: "center", gap: 12,
        }}>
          <span style={{ fontSize: "1.3rem" }}>🚨</span>
          <div>
            <b className="loss">Trading is PAUSED platform-wide.</b>
            {s.kill_switch.reason && <span className="muted"> Reason: {s.kill_switch.reason}.</span>}
            <span className="muted small"> Set by {s.kill_switch.by} {when(s.kill_switch.at)}.</span>
          </div>
        </div>
      )}

      {/* ── Stats row ─────────────────────────────────────── */}
      <div className="stats" style={{ marginBottom: 18 }}>
        <Stat label="Total Users" value={s.users} sub={<><b className="gain">{s.active_users}</b> active</>} />
        <Stat label="Bots Running" value={s.bots_running}
          sub={s.bots_error ? <span className="loss">{s.bots_error} in error</span> : "None in error"} />
        <Stat label="Orders Today" value={s.orders_today} sub={`${s.trades_today} fills`} />
        <Stat label="Open Orders" value={s.open_orders} sub={`${s.instruments} instruments`} />
      </div>

      {/* ── Kill switch control (super admin only) ─────────── */}
      {!s.kill_switch.active && superAdmin && (
        <Panel title="⚠️ Kill Switch">
          <p className="muted small">Pause stops every running bot, cancels every open order, and blocks new buys for all users. Sells stay allowed.</p>
          <div className="row" style={{ alignItems: "flex-end", gap: 12 }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <Field label="Reason (shown to users)">
                <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} placeholder="e.g. Scheduled maintenance" />
              </Field>
            </div>
          </div>
        </Panel>
      )}
      {!superAdmin && (
        <Panel>
          <p className="small muted">⚡ The kill switch is available only to Super Admins. Contact your Super Admin to pause/resume trading.</p>
        </Panel>
      )}

      <div style={{ height: 18 }} />

      {/* ── Main tab panel ────────────────────────────────── */}
      <Panel>
        <Tabs value={tab} onChange={setTab} options={[
          { value: "users", label: `👥 Users (${s.users})` },
          { value: "bots", label: `🤖 Bots (${s.bots_running} running)` },
          { value: "instruments", label: `📈 Instruments (${s.instruments})` },
          { value: "audit", label: "📋 Audit Log" },
        ]} />

        {/* ── Users tab ──────────────────────────────────── */}
        {tab === "users" && (<>
          <input className="search" placeholder="Search by email or name" value={q}
            onChange={(e) => setQ(e.target.value)} style={{ marginBottom: 12 }} aria-label="Search users" />
          {users.loading ? <Loading /> : <div className="table-wrap"><table>
            <thead><tr>
              <th>User</th><th>Role</th><th className="num">Equity</th>
              <th className="num">Bots</th><th>Last login</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>{users.data?.map((u) => (
              <tr key={u.id} style={{ background: u.role !== "USER" ? "rgba(245,158,11,0.04)" : undefined }}>
                <td>
                  <b>{u.email}</b>
                  <span className="sub">{u.full_name}</span>
                </td>
                <td>
                  {superAdmin && u.id !== user?.id ? (
                    <select value={u.role}
                      onChange={(e) => void updateUser(u, { role: e.target.value as AdminUser["role"] })}
                      style={{ width: "auto" }} aria-label={`Role for ${u.email}`}>
                      <option value="USER">User</option>
                      <option value="ADMIN">Admin</option>
                      <option value="SUPER_ADMIN">Super-admin</option>
                    </select>
                  ) : <RolePill role={u.role} />}
                </td>
                <td className="num">{money(u.equity, true)}</td>
                <td className="num">{u.bots}</td>
                <td className="small muted">{when(u.last_login_at)}</td>
                <td>{u.is_active ? <Badge value="RUNNING" title="Active" /> : <Badge value="STOPPED" title="Disabled" />}</td>
                <td className="num">
                  <div className="row" style={{ gap: 6, justifyContent: "flex-end", flexWrap: "nowrap" }}>
                    {/* Cash top-up — admin power */}
                    <button
                      title="Adjust cash balance"
                      onClick={() => setTopup(u)}
                      style={{
                        padding: "4px 10px", borderRadius: 6, border: "1px solid var(--admin-gold, #f59e0b)",
                        background: "rgba(245,158,11,0.08)", color: "var(--admin-gold, #f59e0b)",
                        cursor: "pointer", fontSize: "0.78rem", fontWeight: 600,
                      }}>
                      ₹ Top-up
                    </button>
                    {u.id !== user?.id && (
                      <Button variant="ghost" onClick={() => void updateUser(u, { is_active: !u.is_active })}>
                        {u.is_active ? "Disable" : "Enable"}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}</tbody>
          </table></div>}
        </>)}

        {/* ── Bots tab ───────────────────────────────────── */}
        {tab === "bots" && (bots.loading ? <Loading /> : <div className="table-wrap"><table>
          <thead><tr><th>Bot</th><th>Owner</th><th>Status</th><th className="num">Position</th><th>Last run</th></tr></thead>
          <tbody>{bots.data?.map((b) => (
            <tr key={b.id}>
              <td><b>{b.name}</b><span className="sub">{b.symbol}</span></td>
              <td className="small">{b.owner}</td>
              <td><Badge value={b.status} title={b.error_message ?? undefined} /></td>
              <td className="num">{b.position_qty || "Flat"}</td>
              <td className="small muted">{when(b.last_evaluated_at)}</td>
            </tr>
          ))}</tbody>
        </table></div>)}

        {/* ── Instruments tab ────────────────────────────── */}
        {tab === "instruments" && (<>
          <p className="muted small" style={{ marginBottom: 12 }}>
            Toggle instruments to enable or disable them for trading across all users.
            Disabled instruments cannot receive new buy orders.
          </p>
          {instruments.loading ? <Loading /> : <div className="table-wrap"><table>
            <thead><tr><th>Symbol</th><th>Name</th><th>Sector</th><th className="num">Last price</th><th>Status</th><th /></tr></thead>
            <tbody>{instruments.data?.map((i) => (
              <tr key={i.symbol}>
                <td><code style={{ fontWeight: 700 }}>{i.symbol}</code></td>
                <td className="small">{i.name}</td>
                <td className="small muted">{i.sector}</td>
                <td className="num">{money(i.last_price)}</td>
                <td>{i.is_active ? <Badge value="RUNNING" title="Tradable" /> : <Badge value="STOPPED" title="Disabled" />}</td>
                <td className="num">
                  <Button variant="ghost" onClick={() => void toggleInstrument(i.symbol)}>
                    {i.is_active ? "Disable" : "Enable"}
                  </Button>
                </td>
              </tr>
            ))}</tbody>
          </table></div>}
        </>)}

        {/* ── Audit log tab ──────────────────────────────── */}
        {tab === "audit" && (audit.loading ? <Loading /> : <div className="table-wrap"><table>
          <thead><tr><th>Time</th><th>Who</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
          <tbody>{audit.data?.map((a) => (
            <tr key={a.id}>
              <td className="small">{dateTime(a.created_at)}</td>
              <td className="small">{a.user ?? "system"}</td>
              <td><code style={{
                background: a.action.startsWith("admin.") ? "rgba(245,158,11,0.12)" : undefined,
                color: a.action.startsWith("admin.") ? "var(--admin-gold,#f59e0b)" : undefined,
                padding: "2px 6px", borderRadius: 4, fontSize: "0.78rem",
              }}>{a.action}</code></td>
              <td className="small">{a.target}</td>
              <td className="small muted" style={{ maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis" }}>
                {a.detail ? JSON.stringify(a.detail) : ""}
              </td>
            </tr>
          ))}</tbody>
        </table></div>)}
      </Panel>

      {/* ── Modals ─────────────────────────────────────────── */}
      <TopupModal target={topup} onClose={() => setTopup(null)} onDone={() => { setTopup(null); void users.reload(); }} />
      <BroadcastModal open={showBroadcast} onClose={() => setShowBroadcast(false)} />
      <Confirm open={kill !== null} danger={!!kill} busy={busy}
        title={kill ? "Pause all trading?" : "Resume trading?"}
        confirmLabel={kill ? "Pause all trading" : "Resume trading"}
        body={kill
          ? <p>Every running bot stops and every open order is cancelled for all users. This is logged.</p>
          : <p>Users can buy again and start their bots. Stopped bots stay stopped until their owners restart them.</p>}
        onClose={() => setKill(null)} onConfirm={() => void setKillSwitch(!!kill)} />
    </>
  );
}
