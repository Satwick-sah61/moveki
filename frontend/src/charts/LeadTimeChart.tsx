import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { LeadTime, LeadBucket } from "../types";
import { mw, signedMw } from "../lib/format";

interface Props {
  lead: LeadTime;
}

type Row = LeadBucket & { x: number; width: number; band: [number, number] | null };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const r = payload?.[0]?.payload;
  if (!active || !r) return null;
  return (
    <div className="chart-tip">
      <b>
        Made {r.bucket}–{r.bucket + r.width} h ahead
      </b>
      <div className="row">
        <span>MAE</span>
        <span>{mw(r.mae_mw)}</span>
      </div>
      <div className="row">
        <span>Bias</span>
        <span>{signedMw(r.bias_mw)}</span>
      </div>
      <div className="row">
        <span>P10 – P90 of error</span>
        <span>
          {signedMw(r.p10_err)} – {signedMw(r.p90_err)}
        </span>
      </div>
      <div className="row">
        <span>n</span>
        <span>{r.n} pairs</span>
      </div>
    </div>
  );
}

export function LeadTimeChart({ lead }: Props) {
  const rows: Row[] = lead.buckets.map((b) => ({
    ...b,
    x: b.bucket + lead.bucket_hours / 2,
    width: lead.bucket_hours,
    band: b.p10_err !== null && b.p90_err !== null ? [b.p10_err, b.p90_err] : null,
  }));
  const [lo, hi] = lead.decision_window_h;
  const extent = rows.flatMap((r) => [r.mae_mw ?? 0, r.bias_mw ?? 0, r.p10_err ?? 0, r.p90_err ?? 0]);
  const top = Math.ceil(Math.max(...extent) / 2000) * 2000;
  const bottom = Math.floor(Math.min(0, ...extent) / 2000) * 2000;
  const ticks = Array.from({ length: (top - bottom) / 2000 + 1 }, (_, i) => bottom + i * 2000);
  const dot = (color: string) => ({ r: 3.5, fill: color, stroke: "var(--surface)", strokeWidth: 2 });
  return (
    <div>
      <div className="legend">
        <span>
          <i style={{ color: "var(--series-1)" }} /> MAE
        </span>
        <span>
          <i style={{ color: "var(--series-2)" }} /> Bias
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--band)" }} /> P10–P90 of the error
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--surface-2)", border: "1px solid var(--grid)" }} /> leads in play at the 09:20 gate
        </span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 69]}
            ticks={[0, 12, 24, 36, 48, 60]}
            tickFormatter={(v: number) => `${v} h`}
            tickLine={false}
          />
          <YAxis
            domain={[bottom, top]}
            ticks={ticks}
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)} GW`}
            width={56}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<Tip />} cursor={{ stroke: "var(--axis)" }} />
          {lo !== null && hi !== null && <ReferenceArea x1={lo} x2={hi} fill="var(--surface-2)" fillOpacity={1} />}
          <Area dataKey="band" type="monotone" fill="var(--band)" stroke="none" isAnimationActive={false} />
          <Line
            dataKey="mae_mw"
            type="monotone"
            stroke="var(--series-1)"
            strokeWidth={2}
            dot={dot("var(--series-1)")}
            isAnimationActive={false}
          />
          <Line
            dataKey="bias_mw"
            type="monotone"
            stroke="var(--series-2)"
            strokeWidth={2}
            dot={dot("var(--series-2)")}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
