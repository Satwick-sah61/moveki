import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Replay, ReplayHour } from "../types";
import { mw, signedMw, ukDayTime } from "../lib/format";

interface Props {
  replay: Replay;
  reveal: boolean;
  adjusted: boolean;
  showLater: boolean;
}

interface Row {
  x: number; // hour of the delivery day, 0..24 (24 closes the last step)
  forecast: number | null;
  band: [number, number] | null;
  actual: number | null;
  adjusted: number | null;
  hour?: ReplayHour;
  [run: string]: unknown;
}

const RUN_PREFIX = "run_";

function buildRows(replay: Replay, reveal: boolean, adjusted: boolean, showLater: boolean): Row[] {
  const byStart = new Map<string, Record<string, number | null>>();
  if (showLater) {
    replay.later_runs.forEach((run, i) => {
      run.values.forEach((v) => {
        const rec = byStart.get(v.start_time) ?? {};
        rec[`${RUN_PREFIX}${i}`] = v.forecast_mw;
        byStart.set(v.start_time, rec);
      });
    });
  }
  const rows: Row[] = replay.hours.map((h, i) => ({
    x: i,
    forecast: h.forecast_mw,
    band: h.band_lo_mw !== null && h.band_hi_mw !== null ? [h.band_lo_mw, h.band_hi_mw] : null,
    actual: reveal ? h.actual_mw : null,
    adjusted: adjusted ? h.adjusted_mw : null,
    hour: h,
    ...(byStart.get(h.start_time) ?? {}),
  }));
  // Close the final step so the last hour is drawn as a full block.
  const last = rows[rows.length - 1];
  if (last) rows.push({ ...last, x: rows.length, actual: null, hour: undefined });
  return rows;
}

function TipContent({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row?.hour) return null;
  const h = row.hour;
  return (
    <div className="chart-tip">
      <b>{ukDayTime(h.start_time)} UK</b>
      <div className="row">
        <span>Forecast at gate</span>
        <span>{mw(h.forecast_mw)}</span>
      </div>
      {h.band_lo_mw !== null && (
        <div className="row">
          <span>80% band</span>
          <span>
            {mw(h.band_lo_mw)} – {mw(h.band_hi_mw)}
          </span>
        </div>
      )}
      {row.adjusted !== null && (
        <div className="row">
          <span>Bias-adjusted</span>
          <span>{mw(h.adjusted_mw)}</span>
        </div>
      )}
      {row.actual !== null && (
        <>
          <div className="row">
            <span>Actual</span>
            <span>{mw(h.actual_mw)}</span>
          </div>
          <div className="row">
            <span>Error (forecast − actual)</span>
            <span>{signedMw(h.error_mw)}</span>
          </div>
        </>
      )}
      {h.publish_time && (
        <div className="row">
          <span>Run used</span>
          <span>
            {ukDayTime(h.publish_time)}, lead {h.lead_h?.toFixed(1)} h
          </span>
        </div>
      )}
    </div>
  );
}

export function ReplayChart({ replay, reveal, adjusted, showLater }: Props) {
  const rows = buildRows(replay, reveal, adjusted, showLater);
  const laterCount = showLater ? replay.later_runs.length : 0;
  // Clean ticks every 4 GW up to the highest value on the chart.
  const peak = Math.max(
    0,
    ...rows.flatMap((r) => [r.forecast ?? 0, r.actual ?? 0, r.adjusted ?? 0, r.band?.[1] ?? 0]),
    ...(showLater ? replay.later_runs.flatMap((run) => run.values.map((v) => v.forecast_mw ?? 0)) : []),
  );
  const top = Math.max(4000, Math.ceil(peak / 4000) * 4000);
  const ticks = Array.from({ length: top / 4000 + 1 }, (_, i) => i * 4000);
  return (
    <div>
      <div className="legend" aria-label="Legend">
        <span>
          <i style={{ color: "var(--series-1)" }} /> Forecast at the gate
        </span>
        <span>
          <i className="swatch" style={{ background: "var(--band)" }} /> 80% band (other days' errors at this lead)
        </span>
        {laterCount > 0 && (
          <span>
            <i style={{ color: "var(--series-later)" }} /> Later runs ({laterCount}, darker = newer)
          </span>
        )}
        {adjusted && (
          <span>
            <i className="dashed" style={{ color: "var(--series-3)" }} /> Bias-adjusted (last week's miss removed)
          </span>
        )}
        {reveal && (
          <span>
            <i style={{ color: "var(--series-2)" }} /> Actual (hourly average)
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={rows} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, 24]}
            ticks={[0, 3, 6, 9, 12, 15, 18, 21, 24]}
            tickFormatter={(v: number) => `${String(v % 24).padStart(2, "0")}:00`}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(v: number) => `${(v / 1000).toFixed(0)} GW`}
            width={56}
            tickLine={false}
            axisLine={false}
            domain={[0, top]}
            ticks={ticks}
          />
          <Tooltip content={<TipContent />} cursor={{ stroke: "var(--axis)" }} />
          <Area
            dataKey="band"
            type="stepAfter"
            fill="var(--band)"
            stroke="none"
            isAnimationActive={false}
            connectNulls={false}
          />
          {Array.from({ length: laterCount }, (_, i) => (
            <Line
              key={i}
              dataKey={`${RUN_PREFIX}${i}`}
              type="stepAfter"
              stroke="var(--series-later)"
              strokeOpacity={0.25 + (0.6 * (i + 1)) / laterCount}
              strokeWidth={1}
              dot={false}
              isAnimationActive={false}
              connectNulls={false}
            />
          ))}
          <Line
            dataKey="forecast"
            type="stepAfter"
            stroke="var(--series-1)"
            strokeWidth={2.5}
            dot={false}
            isAnimationActive={false}
          />
          {adjusted && (
            <Line
              dataKey="adjusted"
              type="stepAfter"
              stroke="var(--series-3)"
              strokeWidth={2}
              strokeDasharray="6 4"
              dot={false}
              isAnimationActive={false}
            />
          )}
          {reveal && (
            <Line
              dataKey="actual"
              type="monotone"
              stroke="var(--series-2)"
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 2, stroke: "var(--surface)", fill: "var(--series-2)" }}
              isAnimationActive={false}
              connectNulls={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
