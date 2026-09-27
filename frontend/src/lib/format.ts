const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2, minimumFractionDigits: 2 });
const inr0 = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export const money = (v: number | null | undefined, whole = false) =>
  v == null || Number.isNaN(v) ? "—" : (whole ? inr0 : inr).format(v);
export const signedMoney = (v: number | null | undefined) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${inr.format(Math.abs(v))}`;
export const pct = (v: number | null | undefined, digits = 2) =>
  v == null || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(digits)}%`;
/** fraction (0.034) -> "3.40%" */
export const frac = (v: number | null | undefined, digits = 2, signed = false) =>
  v == null || Number.isNaN(v) ? "—" : signed ? pct(v * 100, digits) : `${v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(digits)}%`;
export const n = (v: number | null | undefined, digits = 2) =>
  v == null || Number.isNaN(v) ? "—" : num.format(Number(v.toFixed(digits)));
export const score = (v: number | null | undefined) =>
  v == null || Number.isNaN(v) ? "—" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)}`;
export const tone = (v: number | null | undefined) => (v == null || v === 0 ? "" : v > 0 ? "gain" : "loss");

export function when(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
export const dateShort = (iso: string) =>
  new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "2-digit" });
export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

export const regimeLabel: Record<string, string> = {
  TRENDING: "Trending", SIDEWAYS: "Sideways", HIGH_VOLATILITY: "High volatility", WARMUP: "Warming up",
};
export const componentLabel: Record<string, string> = {
  trend: "Trend", momentum: "Momentum", reversion: "Reversion", volume: "Volume",
  rsi: "RSI", mean_reversion: "Mean reversion", volatility: "Volatility",
};
