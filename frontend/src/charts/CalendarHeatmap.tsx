import type { DailyRow } from "../types";
import { gwh, mw } from "../lib/format";

interface Props {
  daily: DailyRow[];
  onPick: (day: string) => void;
}

// Sequential blue ramp (one hue, light -> dark) for daily MAE: magnitude, not identity.
const STEPS = ["var(--seq-100)", "var(--seq-250)", "var(--seq-400)", "var(--seq-550)", "var(--seq-700)"];
const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function stepFor(value: number, lo: number, hi: number): number {
  if (hi <= lo) return 0;
  return Math.min(STEPS.length - 1, Math.floor(((value - lo) / (hi - lo)) * STEPS.length));
}

export function CalendarHeatmap({ daily, onPick }: Props) {
  const values = daily.map((d) => d.mae_mw ?? 0);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const first = daily[0];
  if (!first) return null;
  // Monday-first offset of the first day (1 Jan 2026 is a Thursday).
  const offset = (new Date(`${first.day}T12:00:00Z`).getUTCDay() + 6) % 7;

  return (
    <div>
      <div className="cal-grid" role="grid" aria-label="Daily MAE calendar">
        {WEEKDAYS.map((w) => (
          <div key={w} className="cal-head">
            {w}
          </div>
        ))}
        {Array.from({ length: offset }, (_, i) => (
          <div key={`pad${i}`} />
        ))}
        {daily.map((d) => {
          const step = stepFor(d.mae_mw ?? 0, lo, hi);
          const dark = step >= 3;
          return (
            <button
              key={d.day}
              type="button"
              className={`cal-cell${d.unusual ? " unusual" : ""}`}
              style={{ background: STEPS[step], color: dark ? "#fff" : "var(--ink)" }}
              title={`${d.day}: MAE ${mw(d.mae_mw)}, net ${gwh(d.net_gwh, 1, true)}${d.unusual ? " (unusual day)" : ""}`}
              onClick={() => onPick(d.day)}
            >
              <span className="cal-day">{Number(d.day.slice(-2))}</span>
              <span className="cal-val">{((d.mae_mw ?? 0) / 1000).toFixed(1)}</span>
              {d.unusual && <span className="cal-flag" aria-label="unusual day" />}
            </button>
          );
        })}
      </div>
      <div className="legend" style={{ marginTop: 8 }}>
        <span>Daily MAE, GW:</span>
        {STEPS.map((s, i) => (
          <span key={s}>
            <i className="swatch" style={{ background: s }} />
            {(lo + ((hi - lo) * i) / STEPS.length) / 1000 > 0
              ? `${((lo + ((hi - lo) * i) / STEPS.length) / 1000).toFixed(1)}+`
              : "low"}
          </span>
        ))}
        <span className="flag unusual">
          <span className="dot" /> unusual day
        </span>
        <span className="hint">click a day to replay it</span>
      </div>
    </div>
  );
}
