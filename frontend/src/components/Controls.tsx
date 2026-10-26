import type { GatePreset } from "../types";
import { FIRST_DAY as FIRST, LAST_DAY as LAST, type UrlState } from "../lib/urlState";
import { ukDay } from "../lib/format";

interface Props {
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
  presets: GatePreset[];
  showDate: boolean;
}

function shiftDay(iso: string, delta: number): string {
  const d = new Date(`${iso}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + delta);
  return d.toISOString().slice(0, 10);
}

// One filter row above everything it scopes: delivery day and gate (decision time).
export function Controls({ state, update, presets, showDate }: Props) {
  const isPreset = presets.some((p) => p.gate === state.gate);
  return (
    <div className="controls">
      {showDate && (
        <label className="control">
          <span>Delivery day (UK)</span>
          <div className="control-row">
            <button
              type="button"
              className="icon-btn"
              aria-label="Previous day"
              disabled={state.date <= FIRST}
              onClick={() => update({ date: shiftDay(state.date, -1) })}
            >
              ‹
            </button>
            <input
              className="input"
              type="date"
              min={FIRST}
              max={LAST}
              value={state.date}
              onChange={(e) => {
                const v = e.target.value;
                if (v >= FIRST && v <= LAST) update({ date: v });
              }}
            />
            <button
              type="button"
              className="icon-btn"
              aria-label="Next day"
              disabled={state.date >= LAST}
              onClick={() => update({ date: shiftDay(state.date, 1) })}
            >
              ›
            </button>
            <span className="hint">{ukDay(state.date)}</span>
          </div>
        </label>
      )}
      <div className="control">
        <span>Decision time, day before (UK)</span>
        <div className="control-row">
          <div className="segmented" role="group" aria-label="Gate presets">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                aria-pressed={state.gate === p.gate}
                title={p.label}
                onClick={() => update({ gate: p.gate })}
              >
                {p.label.split(" ")[0]} {p.gate}
              </button>
            ))}
          </div>
          <input
            className="input"
            type="time"
            step={1800}
            value={state.gate}
            aria-label="Custom gate time"
            onChange={(e) => {
              if (/^\d{2}:\d{2}$/.test(e.target.value)) update({ gate: e.target.value });
            }}
          />
          {!isPreset && <span className="hint">custom</span>}
        </div>
      </div>
    </div>
  );
}
