import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HourOfDayRow } from "../types";
import { signedMw, mw } from "../lib/format";

interface Props {
  rows: HourOfDayRow[];
  measure: "bias_mw" | "mae_mw";
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: HourOfDayRow }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="chart-tip">
      <b>{String(r.hour).padStart(2, "0")}:00 UK</b>
      <div className="row">
        <span>Bias</span>
        <span>{signedMw(r.bias_mw)}</span>
      </div>
      <div className="row">
        <span>MAE</span>
        <span>{mw(r.mae_mw)}</span>
      </div>
      <div className="row">
        <span>n</span>
        <span>{r.n} days</span>
      </div>
    </div>
  );
}

// Bias has polarity (over / under-forecast) so it takes the diverging pair; MAE is a
// magnitude and takes slot 1.
export function HourOfDayChart({ rows, measure }: Props) {
  // Clean ticks every 500 MW, covering negative bias if it occurs.
  const values = rows.map((r) => r[measure] ?? 0);
  const top = Math.max(500, Math.ceil(Math.max(...values) / 500) * 500);
  const bottom = Math.min(0, Math.floor(Math.min(...values) / 500) * 500);
  const ticks = Array.from({ length: (top - bottom) / 500 + 1 }, (_, i) => bottom + i * 500);
  return (
    <div>
      {measure === "bias_mw" && (
        <div className="legend">
          <span>
            <i className="swatch" style={{ background: "var(--diverge-pos)" }} /> forecast high (short)
          </span>
          <span>
            <i className="swatch" style={{ background: "var(--diverge-neg)" }} /> forecast low
          </span>
        </div>
      )}
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="hour" tickFormatter={(h: number) => String(h).padStart(2, "0")} tickLine={false} interval={2} />
          <YAxis
            domain={[bottom, top]}
            ticks={ticks}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(1)} GW`}
            width={56}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<Tip />} cursor={{ fill: "var(--surface-2)" }} />
          <ReferenceLine y={0} stroke="var(--axis)" />
          <Bar dataKey={measure} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {rows.map((r) => (
              <Cell
                key={r.hour}
                fill={measure === "mae_mw" ? "var(--series-1)" : (r.bias_mw ?? 0) >= 0 ? "var(--diverge-pos)" : "var(--diverge-neg)"}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
