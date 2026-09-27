import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { post } from "../api/client";
import { Button, ErrorBox, Field } from "../components/ui";
import { useAuth } from "../lib/auth";

function Card({ title, lede, children }: { title: string; lede: string; children: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <span className="ribbon" style={{ display: "inline-block", marginBottom: 16 }}>Practice money, simulated prices</span>
        <h1>{title}</h1>
        <p className="lede">{lede}</p>
        {children}
      </div>
    </div>
  );
}

function pwProblems(pw: string) {
  const p: string[] = [];
  if (pw.length < 8) p.push("8+ characters");
  if (!/[A-Z]/.test(pw)) p.push("an uppercase letter");
  if (!/[a-z]/.test(pw)) p.push("a lowercase letter");
  if (!/\d/.test(pw)) p.push("a digit");
  return p;
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await login(email, pw); nav(from, { replace: true }); }
    catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <Card title="Log in to TradeBot" lede="Practise trading NSE stocks and run rule-based bots with ₹10 lakh of virtual money.">
      <form onSubmit={submit}>
        {err && <ErrorBox message={err} />}
        <Field label="Email"><input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
        <Field label="Password"><input type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} required /></Field>
        <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Log in</Button>
      </form>
      <div className="auth-foot"><Link to="/register">Create an account</Link><Link to="/forgot-password">Forgot password?</Link></div>
    </Card>
  );
}

export function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", pw: "", pw2: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const problems = f.pw ? pwProblems(f.pw) : [];
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null);
    if (problems.length) return setErr(`Password needs ${problems.join(", ")}.`);
    if (f.pw !== f.pw2) return setErr("The two passwords don't match.");
    setBusy(true);
    try { await register(f.email, f.pw, f.name); nav("/", { replace: true }); }
    catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <Card title="Create your practice account" lede="You start with ₹10,00,000 of virtual cash. Nothing here uses real money.">
      <form onSubmit={submit}>
        {err && <ErrorBox message={err} />}
        <Field label="Your name"><input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} autoComplete="name" /></Field>
        <Field label="Email"><input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required autoComplete="email" /></Field>
        <Field label="Password" hint={problems.length ? `Needs ${problems.join(", ")}` : f.pw ? "Looks good" : "At least 8 characters with upper, lower case and a digit"}>
          <input type="password" value={f.pw} onChange={(e) => setF({ ...f, pw: e.target.value })} required autoComplete="new-password" />
        </Field>
        <Field label="Confirm password"><input type="password" value={f.pw2} onChange={(e) => setF({ ...f, pw2: e.target.value })} required autoComplete="new-password" /></Field>
        <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Create account</Button>
      </form>
      <div className="auth-foot"><span>Already registered? <Link to="/login">Log in</Link></span></div>
    </Card>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await post("/auth/forgot-password", { email }); setDone(true); }
    catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <Card title="Reset your password" lede="Enter your account email and we'll send a reset link that works for 30 minutes.">
      {done ? (
        <div className="notice info">If that email is registered, a reset link is on its way. In this self-hosted setup the link is written to the server log.</div>
      ) : (
        <form onSubmit={submit}>
          {err && <ErrorBox message={err} />}
          <Field label="Email"><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus /></Field>
          <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Send reset link</Button>
        </form>
      )}
      <div className="auth-foot"><Link to="/login">Back to log in</Link></div>
    </Card>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const problems = pw ? pwProblems(pw) : [];
  async function submit(e: FormEvent) {
    e.preventDefault(); setErr(null);
    if (problems.length) return setErr(`Password needs ${problems.join(", ")}.`);
    setBusy(true);
    try { await post("/auth/reset-password", { token, new_password: pw }); nav("/login", { replace: true }); }
    catch (e2) { setErr((e2 as Error).message); } finally { setBusy(false); }
  }
  return (
    <Card title="Choose a new password" lede="After this you'll be logged out on every device.">
      {!token ? <ErrorBox message="This link is missing its token. Request a new reset link." /> : (
        <form onSubmit={submit}>
          {err && <ErrorBox message={err} />}
          <Field label="New password" hint={problems.length ? `Needs ${problems.join(", ")}` : undefined}>
            <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required autoComplete="new-password" autoFocus />
          </Field>
          <Button type="submit" variant="primary" busy={busy} style={{ width: "100%" }}>Save new password</Button>
        </form>
      )}
      <div className="auth-foot"><Link to="/forgot-password">Request a new link</Link></div>
    </Card>
  );
}
