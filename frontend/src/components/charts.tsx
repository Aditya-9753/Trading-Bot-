import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dateShort, money, score } from "../lib/format";

const INK = "#38BDF8", MUTED = "#64748B", GRID = "rgba(255, 255, 255, 0.07)", GAIN = "#10B981", LOSS = "#F43F5E", MARIGOLD = "#F59E0B";
const tick = { fill: MUTED, fontSize: 11, fontFamily: "var(--mono)" };
const compact = (v: number) => (Math.abs(v) >= 1e7 ? `${(v / 1e7).toFixed(1)}Cr` : Math.abs(v) >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : `${Math.round(v / 1e3)}k`);

const tooltipStyle = {
  backgroundColor: "rgba(17, 24, 39, 0.95)",
  backdropFilter: "blur(12px)",
  borderColor: "rgba(255, 255, 255, 0.12)",
  borderRadius: "8px",
  color: "#F8FAFC",
  boxShadow: "0 12px 30px rgba(0, 0, 0, 0.6)",
  fontSize: "12px",
  padding: "8px 12px",
};

export function EquityChart({ data, benchmark, height = 260 }: {
  data: { t: string; v: number }[]; benchmark?: { t: string; v: number }[] | null; height?: number;
}) {
  const bm = new Map((benchmark ?? []).map((p) => [p.t, p.v]));
  const rows = data.map((p) => ({ t: p.t, v: p.v, b: bm.get(p.t) }));
  const start = data[0]?.v ?? 0;
  const up = (data[data.length - 1]?.v ?? 0) >= start;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="eqfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={up ? GAIN : LOSS} stopOpacity={0.22} />
            <stop offset="100%" stopColor={up ? GAIN : LOSS} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="t" tickFormatter={dateShort} tick={tick} minTickGap={48} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={compact} tick={tick} width={48} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number, k) => [money(v), k === "v" ? "Strategy" : "Buy & hold"]} labelFormatter={(l) => dateShort(String(l))} />
        <ReferenceLine y={start} stroke={MUTED} strokeDasharray="3 3" />
        {benchmark && <Area type="monotone" dataKey="b" stroke={MUTED} strokeDasharray="4 3" fill="none" dot={false} isAnimationActive={false} />}
        <Area type="monotone" dataKey="v" stroke={up ? GAIN : LOSS} strokeWidth={2} fill="url(#eqfill)" dot={false} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SignalChart({ series, entry, exit, height = 220 }: {
  series: { t: string; S: number | null }[]; entry: number; exit: number; height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="2 4" />
        <ReferenceArea y1={entry} y2={1} fill={MARIGOLD} fillOpacity={0.16} />
        <ReferenceArea y1={-1} y2={-entry} fill={LOSS} fillOpacity={0.12} />
        <ReferenceLine y={0} stroke={MUTED} />
        <ReferenceLine y={exit} stroke={LOSS} strokeDasharray="3 3" />
        <XAxis dataKey="t" tickFormatter={dateShort} tick={tick} minTickGap={48} axisLine={false} tickLine={false} />
        <YAxis domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} tick={tick} width={36} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [score(v), "S"]} labelFormatter={(l) => dateShort(String(l))} />
        <Line type="monotone" dataKey="S" stroke={INK} strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function PnlBars({ data, height = 220 }: { data: { label: string; value: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} strokeDasharray="2 4" />
        <XAxis dataKey="label" tick={tick} axisLine={false} tickLine={false} />
        <YAxis tickFormatter={compact} tick={tick} width={48} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [money(v), "P&L"]} />
        <ReferenceLine y={0} stroke={MUTED} />
        <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
          {data.map((d) => <Cell key={d.label} fill={d.value >= 0 ? GAIN : LOSS} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Horizontal contribution bars: w_i × score_i for each component; they sum to S. */
export function Contributions({ values, scores }: { values: Record<string, number | null>; scores?: Record<string, number | null> }) {
  const entries = Object.entries(values);
  const max = Math.max(0.25, ...entries.map(([, v]) => Math.abs(v ?? 0)));
  const labels: Record<string, string> = { trend: "Trend", momentum: "Momentum", reversion: "Reversion", volume: "Volume",
    rsi: "RSI", mean_reversion: "Mean reversion", volatility: "Volatility" };
  return (
    <ul className="contrib">
      {entries.map(([k, v]) => {
        const w = (Math.abs(v ?? 0) / max) * 50;
        return (
          <li key={k}>
            <span className="contrib-name">{labels[k] ?? k}</span>
            <span className="contrib-bar" aria-hidden>
              <span className={`contrib-fill ${(v ?? 0) >= 0 ? "pos" : "neg"}`}
                style={(v ?? 0) >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} />
            </span>
            <span className="num contrib-val">{score(v)}</span>
            {scores && <span className="contrib-raw">score {score(scores[k])}</span>}
          </li>
        );
      })}
    </ul>
  );
}
