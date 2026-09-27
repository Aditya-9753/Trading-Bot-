/** The signal gauge: S from −1 (strong sell) to +1 (strong buy) on a half dial,
 *  with the exit zone, neutral band and the ±entry threshold marked. */
import { score } from "../lib/format";

interface Props {
  value: number | null; entry: number; exit: number; size?: number; label?: string; action?: string; compact?: boolean;
}
const R = 100;
const pt = (s: number, r: number) => {
  const a = Math.PI * (1 - (s + 1) / 2); // s=-1 -> 180°, s=+1 -> 0°
  return [120 + r * Math.cos(a), 118 - r * Math.sin(a)];
};
function arc(from: number, to: number, r: number) {
  const [x1, y1] = pt(from, r);
  const [x2, y2] = pt(to, r);
  return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
}

export default function SignalGauge({ value, entry, exit, size = 260, label = "Signal score S", action, compact }: Props) {
  const v = value == null || Number.isNaN(value) ? null : Math.max(-1, Math.min(1, value));
  const [nx, ny] = pt(v ?? 0, R - 18);
  const ticks = [-1, -0.5, 0, 0.5, 1];
  const zone = v == null ? "Not enough data" : v >= entry ? "Buy zone" : v <= -entry ? "Sell zone" : v <= exit ? "Exit zone for longs" : "Neutral";
  return (
    <figure className={`gauge ${compact ? "gauge-compact" : ""}`} style={{ width: size }}>
      <svg viewBox="0 0 240 158" role="img" aria-label={`${label}: ${v == null ? "no value" : score(v)}, ${zone}`}>
        <path d={arc(-1, 1, R)} className="g-track" />
        <path d={arc(-1, exit, R)} className="g-exit" />
        <path d={arc(-1, -entry, R)} className="g-sell" />
        <path d={arc(entry, 1, R)} className="g-buy" />
        {ticks.map((t) => {
          const [x1, y1] = pt(t, R + 9);
          const [x2, y2] = pt(t, R + 15);
          const [lx, ly] = pt(t, R + 25);
          return (
            <g key={t}>
              <line x1={x1} y1={y1} x2={x2} y2={y2} className="g-tick" />
              {!compact && <text x={lx} y={ly + 3} className="g-ticklabel">{t > 0 ? `+${t}` : t}</text>}
            </g>
          );
        })}
        {[entry, -entry].map((t) => {
          const [x1, y1] = pt(t, R - 11);
          const [x2, y2] = pt(t, R + 11);
          return <line key={t} x1={x1} y1={y1} x2={x2} y2={y2} className="g-threshold" />;
        })}
        {v != null && (
          <g className="g-needle" style={{ transformOrigin: "120px 118px" }}>
            <line x1={120} y1={118} x2={nx} y2={ny} />
            <circle cx={120} cy={118} r={7} />
          </g>
        )}
        <text x={120} y={154} className="g-value">{v == null ? "—" : score(v)}</text>
      </svg>
      <figcaption>
        <span className="g-zone">{zone}</span>
        {action && <span className={`g-action g-action-${action.toLowerCase()}`}>Engine says: {action === "HOLD" ? "hold" : action.toLowerCase()}</span>}
        {!compact && <span className="g-legend">Entry at ±{entry.toFixed(2)}, confirmed over 2 bars. Longs exit below {score(exit)}.</span>}
      </figcaption>
    </figure>
  );
}
