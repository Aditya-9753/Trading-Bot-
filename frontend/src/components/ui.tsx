import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useLive } from "../lib/live";
import { money, pct, tone } from "../lib/format";

export function Button({ variant = "default", busy, children, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "danger" | "ghost" | "buy" | "sell"; busy?: boolean }) {
  return (
    <button {...rest} className={`btn btn-${variant} ${rest.className ?? ""}`} disabled={rest.disabled || busy} aria-busy={busy}>
      {busy ? <span className="spinner" aria-hidden /> : null}
      {children}
    </button>
  );
}

export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string | null; children: ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && <span className="field-error">{error}</span>}
    </label>
  );
}

export function Panel({ title, action, children, className = "" }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <header className="panel-head">
          {title && <h2>{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, valueClass = "" }: { label: string; value: ReactNode; sub?: ReactNode; valueClass?: string }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <span className={`stat-value ${valueClass}`}>{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

const STATUS_TONE: Record<string, string> = {
  FILLED: "ok", RUNNING: "ok", DONE: "ok", OPEN: "info", BACKTESTED: "info", PAUSED: "warn", DRAFT: "muted",
  STOPPED: "muted", CANCELLED: "muted", REJECTED: "bad", ERROR: "bad", FAILED: "bad", WARN: "warn", INFO: "muted",
  BUY: "buy", SELL: "sell", TRENDING: "info", SIDEWAYS: "muted", HIGH_VOLATILITY: "warn", WARMUP: "muted",
};
const STATUS_TEXT: Record<string, string> = {
  FILLED: "Filled", RUNNING: "Running", DONE: "Done", OPEN: "Open", BACKTESTED: "Backtested", PAUSED: "Paused",
  DRAFT: "Draft", STOPPED: "Stopped", CANCELLED: "Cancelled", REJECTED: "Rejected", ERROR: "Error", FAILED: "Failed",
  BUY: "Buy", SELL: "Sell", TRENDING: "Trending", SIDEWAYS: "Sideways", HIGH_VOLATILITY: "High volatility",
  WARMUP: "Warming up", MANUAL: "Manual", BOT: "Bot", SYSTEM: "Stop/target", INFO: "Info", WARN: "Warning",
  HOLD: "Hold", EXIT: "Exit",
};
export function Badge({ value, title }: { value: string; title?: string }) {
  return <span className={`badge badge-${STATUS_TONE[value] ?? "muted"}`} title={title}>{STATUS_TEXT[value] ?? value}</span>;
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty-title">{title}</p>
      {children && <p className="empty-body">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="errorbox" role="alert">
      <span>{message}</span>
      {onRetry && <Button variant="ghost" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return <div className="loading"><span className="spinner" aria-hidden /> {label}…</div>;
}

export function Tabs<T extends string>({ value, onChange, options }: { value: T; onChange(v: NoInfer<T>): void; options: readonly { value: NoInfer<T>; label: ReactNode }[] }) {
  return (
    <div className="tabs" role="tablist">
      {options.map((o) => (
        <button key={o.value} role="tab" aria-selected={o.value === value} className={o.value === value ? "on" : ""} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({ title, open, onClose, children, wide }: { title: string; open: boolean; onClose(): void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal?.();
    if (!open && d.open) d.close?.();
  }, [open]);
  if (!open) return null;
  return (
    <dialog ref={ref} className={`modal ${wide ? "modal-wide" : ""}`} onClose={onClose} onCancel={onClose} open={open}>
      <header className="modal-head">
        <h2>{title}</h2>
        <button className="icon-btn" aria-label="Close" onClick={onClose}>×</button>
      </header>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}

/** Price that follows the live feed, with a brief flash when it moves. */
export function LivePrice({ symbol, fallback, showChange = true }: { symbol: string; fallback: number; showChange?: boolean }) {
  const t = useLive().prices[symbol];
  const price = t?.price ?? fallback;
  const prev = useRef(price);
  const dir = price > prev.current ? "up" : price < prev.current ? "down" : "";
  useEffect(() => { prev.current = price; }, [price]);
  return (
    <span className="liveprice">
      <span key={price} className={`num flash-${dir}`}>{money(price)}</span>
      {showChange && t && <span className={`chg ${tone(t.change)}`}>{pct(t.change_pct)}</span>}
    </span>
  );
}

export function SymbolLink({ symbol }: { symbol: string }) {
  return <Link className="sym" to={`/markets/${symbol}`}>{symbol}</Link>;
}

export function Confirm({ open, title, body, confirmLabel, danger, onConfirm, onClose, busy }: {
  open: boolean; title: string; body: ReactNode; confirmLabel: string; danger?: boolean; busy?: boolean;
  onConfirm(): void; onClose(): void;
}) {
  return (
    <Modal title={title} open={open} onClose={onClose}>
      <div className="confirm-body">{body}</div>
      <div className="row-end">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} busy={busy} onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}
