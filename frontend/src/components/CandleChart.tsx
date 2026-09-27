/** Dependency-free SVG candlestick chart with EMA overlays, volume, crosshair and optional price lines. */
import { useEffect, useMemo, useRef, useState } from "react";
import type { ChartData } from "../api/types";
import { dateShort, money, n } from "../lib/format";

interface Line { price: number; label: string; kind: "stop" | "target" | "entry" | "alert" }
interface Props { data: ChartData; height?: number; lines?: Line[]; showEma?: boolean }

const PAD = { l: 8, r: 84, t: 12, b: 22 };

/** Width of a container, kept up to date, so the SVG is drawn 1:1 and text never shrinks. */
function useWidth(ref: React.RefObject<HTMLDivElement>, fallback = 900) {
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

export default function CandleChart({ data, height = 380, lines = [], showEma = true }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<number | null>(null);
  const W = useWidth(wrap);
  const H = height;
  const volH = 56;
  const c = data.candles;

  const geo = useMemo(() => {
    const vals = c.flatMap((k) => [k.h, k.l]).concat(showEma ? [...data.ema20, ...data.ema50].filter((x): x is number => x != null) : [])
      .concat(lines.map((l) => l.price));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const padv = (hi - lo) * 0.06 || 1;
    lo -= padv; hi += padv;
    const plotW = W - PAD.l - PAD.r;
    const step = plotW / Math.max(c.length, 1);
    const y = (p: number) => PAD.t + (1 - (p - lo) / (hi - lo)) * (H - PAD.t - PAD.b - volH);
    const maxV = Math.max(...c.map((k) => k.v), 1);
    const vy = (v: number) => H - PAD.b - (v / maxV) * (volH - 8);
    const x = (i: number) => PAD.l + step * i + step / 2;
    const ticks = Array.from({ length: 5 }, (_, i) => lo + ((hi - lo) * (i + 0.5)) / 5);
    return { y, vy, x, step, ticks };
  }, [c, data.ema20, data.ema50, lines, showEma, H, W]);

  if (!c.length) return <div className="chart-empty">No price history yet.</div>;
  const path = (arr: (number | null)[]) =>
    arr.map((v, i) => (v == null ? "" : `${arr[i - 1] == null ? "M" : "L"}${geo.x(i).toFixed(1)},${geo.y(v).toFixed(1)}`)).join(" ");
  const bw = Math.max(1, Math.min(10, geo.step * 0.62));
  const h = hover != null ? c[hover] : c[c.length - 1];
  const hi = hover ?? c.length - 1;

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round((px - PAD.l - geo.step / 2) / geo.step);
    setHover(i >= 0 && i < c.length ? i : null);
  };
  const labelEvery = Math.ceil(c.length / Math.max(3, Math.floor(W / 130)));

  return (
    <div className="candle-wrap" ref={wrap}>
      <div className="ohlc" aria-live="off">
        <span>{dateShort(h.t)}</span>
        <span>O <b className="num">{n(h.o)}</b></span><span>H <b className="num">{n(h.h)}</b></span>
        <span>L <b className="num">{n(h.l)}</b></span><span>C <b className="num">{n(h.c)}</b></span>
        {showEma && <><span className="k-ema20">EMA 20 <b className="num">{n(data.ema20[hi])}</b></span>
          <span className="k-ema50">EMA 50 <b className="num">{n(data.ema50[hi])}</b></span></>}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="candles" onPointerMove={onMove} onPointerLeave={() => setHover(null)}
        role="img" aria-label={`${data.symbol} price chart, last close ${money(c[c.length - 1].c)}`}>
        {geo.ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.l} x2={W - PAD.r} y1={geo.y(t)} y2={geo.y(t)} className="grid" />
            <text x={W - PAD.r + 6} y={geo.y(t) + 4} className="axis">{n(t, 0)}</text>
          </g>
        ))}
        {c.map((k, i) => i % labelEvery === 0 && (
          <text key={k.t} x={geo.x(i)} y={H - 6} className="axis" textAnchor="middle">{dateShort(k.t)}</text>
        ))}
        {c.map((k, i) => (
          <rect key={`v${i}`} x={geo.x(i) - bw / 2} width={bw} y={geo.vy(k.v)} height={H - PAD.b - geo.vy(k.v)}
            className={k.c >= k.o ? "vol-up" : "vol-down"} />
        ))}
        {c.map((k, i) => {
          const up = k.c >= k.o;
          const top = geo.y(Math.max(k.o, k.c));
          const bh = Math.max(1, Math.abs(geo.y(k.o) - geo.y(k.c)));
          return (
            <g key={i} className={up ? "cd-up" : "cd-down"}>
              <line x1={geo.x(i)} x2={geo.x(i)} y1={geo.y(k.h)} y2={geo.y(k.l)} />
              <rect x={geo.x(i) - bw / 2} y={top} width={bw} height={bh} />
            </g>
          );
        })}
        {showEma && <path d={path(data.ema20)} className="ema20" />}
        {showEma && <path d={path(data.ema50)} className="ema50" />}
        {lines.map((l) => (
          <g key={`${l.kind}${l.price}`} className={`pline pline-${l.kind}`}>
            <line x1={PAD.l} x2={W - PAD.r} y1={geo.y(l.price)} y2={geo.y(l.price)} />
            <text x={W - PAD.r + 6} y={geo.y(l.price) - 4}>{l.label}</text>
          </g>
        ))}
        {hover != null && <line x1={geo.x(hover)} x2={geo.x(hover)} y1={PAD.t} y2={H - PAD.b} className="crosshair" />}
      </svg>
    </div>
  );
}

/** Small oscillator strip (RSI or MACD histogram). */
export function Oscillator({ values, kind, height = 90 }: { values: (number | null)[]; kind: "rsi" | "macd"; height?: number }) {
  const box = useRef<HTMLDivElement>(null);
  const W = useWidth(box), H = height;
  const xs = values.map((_, i) => PAD.l + ((W - PAD.l - PAD.r) * (i + 0.5)) / values.length);
  const nums = values.filter((v): v is number => v != null);
  if (!nums.length) return <div ref={box} />;
  const lo = kind === "rsi" ? 0 : Math.min(...nums, 0), hi = kind === "rsi" ? 100 : Math.max(...nums, 0);
  const y = (v: number) => 6 + (1 - (v - lo) / (hi - lo || 1)) * (H - 12);
  const last = nums[nums.length - 1];
  return (
    <div ref={box}><svg viewBox={`0 0 ${W} ${H}`} className="osc" role="img" aria-label={`${kind.toUpperCase()} ${n(last)}`}>
      {kind === "rsi" ? (
        <>
          <rect x={PAD.l} width={W - PAD.l - PAD.r} y={y(70)} height={y(30) - y(70)} className="rsi-band" />
          {[30, 70].map((v) => <line key={v} x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="grid" />)}
          <path className="rsi-line" d={values.map((v, i) => (v == null ? "" : `${values[i - 1] == null ? "M" : "L"}${xs[i]},${y(v)}`)).join(" ")} />
          <text x={W - PAD.r + 6} y={y(last) + 4} className="axis">RSI {n(last, 0)}</text>
        </>
      ) : (
        <>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(0)} y2={y(0)} className="grid" />
          {values.map((v, i) => v != null && (
            <rect key={i} x={xs[i] - 1.5} width={3} y={Math.min(y(0), y(v))} height={Math.abs(y(v) - y(0))} className={v >= 0 ? "vol-up" : "vol-down"} />
          ))}
          <text x={W - PAD.r + 6} y={y(last) + 4} className="axis">MACD {n(last)}</text>
        </>
      )}
    </svg></div>
  );
}
