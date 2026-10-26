import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HistogramBin } from "../types";
import { mw } from "../lib/format";

interface Props {
  bins: HistogramBin[];
  p90: number | null;
  bias: number | null;
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: HistogramBin }[] }) {
  const b = payload?.[0]?.payload;
  if (!active || !b) return null;
  return (
    <div className="chart-tip">
      <b>
        {mw(b.lo)} to {mw(b.hi)}
      </b>
      <div className="row">
        <span>Hours</span>
        <span>{b.n}</span>
      </div>
    </div>
  );
}

export function HistogramChart({ bins, p90, bias }: Props) {
  const data = bins.map((b) => ({ ...b, mid: (b.lo + b.hi) / 2 }));
  const lo = Math.floor((bins[0]?.lo ?? 0) / 2000) * 2000;
  const hi = Math.ceil((bins[bins.length - 1]?.hi ?? 0) / 2000) * 2000;
  const ticks = Array.from({ length: (hi - lo) / 2000 + 1 }, (_, i) => lo + i * 2000);
  return (
    <div>
      <div className="legend">
        <span>
          <i style={{ color: "var(--ink-2)" }} /> mean (bias)
        </span>
        <span>
          <i style={{ color: "var(--series-2)" }} /> P90 of |error|
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 18, left: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="mid"
            type="number"
            domain={[lo, hi]}
            ticks={ticks}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}`}
            tickLine={false}
            label={{ value: "forecast − actual, GW", position: "bottom", offset: 2, fill: "var(--muted)", fontSize: 11 }}
          />
          <YAxis width={36} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: "var(--surface-2)" }} />
          <ReferenceLine x={0} stroke="var(--axis)" />
          {bias !== null && <ReferenceLine x={bias} stroke="var(--ink-2)" strokeWidth={2} />}
          {p90 !== null && <ReferenceLine x={p90} stroke="var(--series-2)" strokeWidth={2} />}
          <Bar dataKey="n" fill="var(--series-1)" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
