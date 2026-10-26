import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RunScore } from "../types";
import { mw } from "../lib/format";

interface Props {
  runs: RunScore[];
  measure: "mean_mae_mw" | "best_days";
}

function Tip({ active, payload }: { active?: boolean; payload?: { payload: RunScore }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="chart-tip">
      <b>Run published {r.run} UK</b>
      <div className="row">
        <span>Average miss when used</span>
        <span>{mw(r.mean_mae_mw)}</span>
      </div>
      <div className="row">
        <span>Closest of the 8 runs</span>
        <span>{r.best_days} days</span>
      </div>
      <div className="row">
        <span>Furthest of the 8 runs</span>
        <span>{r.worst_days} days</span>
      </div>
    </div>
  );
}

// One series per chart (no second axis): either how big the miss was when each run was used,
// or on how many days each run happened to be the closest one.
export function RunBarChart({ runs, measure }: Props) {
  const values = runs.map((r) => r[measure] ?? 0);
  const isMw = measure === "mean_mae_mw";
  const step = isMw ? 500 : 2;
  const top = Math.max(step, Math.ceil(Math.max(...values) / step) * step);
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step);
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={runs} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap={6}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="run" tickLine={false} />
        <YAxis
          domain={[0, top]}
          ticks={ticks}
          tickFormatter={(v: number) => (isMw ? `${(v / 1000).toFixed(1)} GW` : String(v))}
          width={isMw ? 56 : 32}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<Tip />} cursor={{ fill: "var(--surface-2)" }} />
        <Bar dataKey={measure} fill="var(--series-1)" maxBarSize={28} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );
}
