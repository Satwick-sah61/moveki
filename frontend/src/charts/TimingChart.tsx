import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Timing, TimingGate } from "../types";
import { mw, pct } from "../lib/format";

interface Props {
  timing: Timing;
  currentGate: string;
}

const toMin = (hhmm: string) => {
  const [h, m] = hhmm.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
};
const fmtMin = (v: number) => `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}`;

type Row = TimingGate & { x: number };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="chart-tip">
      <b>Decide at {r.gate} UK, day before</b>
      <div className="row">
        <span>MAE</span>
        <span>{mw(r.mae_mw)}</span>
      </div>
      <div className="row">
        <span>P90 |error|</span>
        <span>{mw(r.p90_abs_mw)}</span>
      </div>
      <div className="row">
        <span>Bias</span>
        <span>{mw(r.bias_mw)}</span>
      </div>
      <div className="row">
        <span>Coverage</span>
        <span>
          {pct(r.coverage)} ({r.hours_scored} h)
        </span>
      </div>
    </div>
  );
}

export function TimingChart({ timing, currentGate }: Props) {
  const rows: Row[] = timing.gates.map((g) => ({ ...g, x: toMin(g.gate) }));
  const earliest = toMin(timing.earliest_full_gate);
  const peak = Math.max(...rows.map((r) => r.p90_abs_mw ?? 0));
  const top = Math.ceil(peak / 1000) * 1000;
  const ticks = Array.from({ length: top / 1000 + 1 }, (_, i) => i * 1000);
  // Preset labels sit 30 minutes apart, so stagger them vertically instead of letting them collide.
  const presetLabel = (text: string, row: number) => (props: { viewBox?: { x?: number; y?: number } }) => (
    <text
      x={(props.viewBox?.x ?? 0) + 3}
      y={(props.viewBox?.y ?? 0) - 4 + row * 12}
      fill="var(--ink-2)"
      fontSize={11}
      textAnchor="start"
    >
      {text}
    </text>
  );
  return (
    <div>
      <div className="legend">
        <span>
          <i style={{ color: "var(--series-1)" }} /> MAE
        </span>
        <span>
          <i style={{ color: "var(--series-2)" }} /> P90 of |error|
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--surface-2)", border: "1px solid var(--grid)" }} /> gates before{" "}
          {timing.earliest_full_gate}: 22/24 hours covered
        </span>
        <span>
          <i style={{ color: "var(--muted)" }} /> forecast run published
        </span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={rows} margin={{ top: 20, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 1440]}
            ticks={[0, 180, 360, 540, 720, 900, 1080, 1260, 1440]}
            tickFormatter={fmtMin}
            tickLine={false}
          />
          <YAxis
            domain={[0, top]}
            ticks={ticks}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)} GW`}
            width={56}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<Tip />} cursor={{ stroke: "var(--axis)" }} />
          <ReferenceArea x1={0} x2={earliest} fill="var(--surface-2)" fillOpacity={1} />
          {timing.run_publish_times_utc.map((t) => (
            <ReferenceLine key={t} x={toMin(t)} stroke="var(--grid)" />
          ))}
          {timing.presets.map((p, i) => (
            <ReferenceLine
              key={p.id}
              x={toMin(p.gate)}
              stroke={p.gate === currentGate ? "var(--ink)" : "var(--axis)"}
              label={presetLabel(p.gate, i % 2)}
            />
          ))}
          <Line dataKey="p90_abs_mw" type="stepAfter" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line dataKey="mae_mw" type="stepAfter" stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
