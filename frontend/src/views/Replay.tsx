import { useState } from "react";
import { api } from "../api";
import { ReplayChart } from "../charts/ReplayChart";
import { Switch } from "../components/Switch";
import { Tile } from "../components/Tile";
import { gw, gwh, hours, leadRange, mw, pct, signedMw, ukDayTime, ukLongDay, ukShortDate, ukTime } from "../lib/format";
import { useFetch } from "../lib/useFetch";
import type { UrlState } from "../lib/urlState";

interface Props {
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
}

export function ReplayView({ state, update }: Props) {
  const { date, gate, align, reveal, adjusted } = state;
  const [showLater, setShowLater] = useState(true);
  const { data, error, loading } = useFetch(`${date}|${gate}|${align}`, () => api.decision(date, gate, align));

  if (error && !data) return <div className="error">Could not load the replay: {error}</div>;
  if (!data) return <p className="hint">Loading the replay…</p>;

  const r = data;
  const run = r.runs_used[0];
  const b = r.before_reveal;
  const a = r.after_reveal;
  const gaps = r.hours_total - r.hours_with_forecast;

  return (
    <div className={loading || error ? "stale" : undefined}>
      {error && (
        <div className="error" style={{ marginBottom: 12 }}>
          Could not load this selection: {error}. Showing the previous one.
        </div>
      )}
      <div className="card-head">
        <div>
          <h2 style={{ margin: 0 }}>{ukLongDay(r.day)}</h2>
          <p className="hint" style={{ margin: "2px 0 10px" }}>
            Decision at {r.gate} UK on {ukShortDate(r.cutoff_utc)}. The chart shows only what the desk could see then
            {reveal ? ", plus what actually happened" : ""}.
          </p>
        </div>
        <div className="control-row" style={{ gap: 18 }}>
          <Switch checked={adjusted} onChange={(v) => update({ adjusted: v })} label="Bias-adjusted line" />
          <Switch checked={showLater} onChange={setShowLater} label="Later runs" />
          <Switch checked={reveal} onChange={(v) => update({ reveal: v })} label="Reveal actual" />
        </div>
      </div>

      {run ? (
        <div className="badge">
          Using the run published <b>{ukDayTime(run.publish_time)} UK</b>, {hours(run.age_h)} before the gate · lead{" "}
          {leadRange(run.lead_min, run.lead_max)}
          {r.runs_used.length > 1 && ` · ${r.runs_used.length} runs used`}
          {gaps > 0 && ` · ${gaps} hour${gaps > 1 ? "s" : ""} with no eligible forecast`}
        </div>
      ) : (
        <div className="badge">No forecast run had been published by this gate.</div>
      )}

      <div className="tiles">
        <Tile
          label="Forecast wind energy for the day"
          value={gwh(b.forecast_energy_gwh)}
          note={`80% band ${gwh(b.band_energy_lo_gwh)} – ${gwh(b.band_energy_hi_gwh)}`}
        />
        <Tile label="Forecast peak / trough" value={`${gw(b.forecast_peak_mw, 1)} / ${gw(b.forecast_trough_mw, 1)}`} />
        <Tile
          label="Median miss at this gate (all 31 days)"
          value={gw(b.month_p50_abs_mw, 1)}
          note={`half of the hours miss by less; average ${gw(b.month_mae_mw, 1)}; 9 in 10 under ${gw(b.month_p90_abs_mw, 1)}`}
        />
        <Tile
          label="Bias at this gate (all 31 days)"
          value={signedMw(b.month_bias_mw)}
          note={b.month_bias_mw === null ? undefined : b.month_bias_mw > 0 ? "forecast reads high" : "forecast reads low"}
        />
        {adjusted && (
          <Tile
            label="Bias-adjusted energy"
            value={gwh(b.adjusted_energy_gwh)}
            note={`last week's average miss ${signedMw(b.trailing_bias_mw)} removed`}
          />
        )}
      </div>

      {reveal && (
        <div className="tiles">
          <Tile revealed label="Actual wind energy" value={gwh(a.actual_energy_gwh)} />
          <Tile
            revealed
            label="Net error for the day"
            value={gwh(a.net_gwh, 1, true)}
            note={a.net_gwh === null ? undefined : a.net_gwh > 0 ? "planned wind that never arrived" : "more wind than planned"}
          />
          <Tile revealed label="Day MAE / bias" value={`${mw(a.mae_mw)} / ${signedMw(a.bias_mw)}`} />
          <Tile
            revealed
            label="Hours inside the 80% band"
            value={`${a.band_hits} of ${r.hours_scored}`}
            note={`persistence would have missed by ${mw(a.persistence_mae_mw)}`}
          />
          {adjusted && (
            <Tile revealed label="MAE with bias adjustment" value={mw(a.adjusted_mae_mw)} note={`vs ${mw(a.mae_mw)} raw`} />
          )}
          {a.unusual_day && (
            <div className="tile revealed">
              <div className="label">Flag</div>
              <p className="value" style={{ fontSize: "1.05rem" }}>
                <span className="flag unusual">
                  <span className="dot" /> Unusual day
                </span>
              </p>
              <div className="note">net error more than 2σ from the month's mean</div>
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2>Hourly forecast the desk had{reveal ? " vs what happened" : ""}</h2>
        <p className="sub">
          UK time. The band is built from the other 30 days' errors at the same lead time, leaving this day out.
        </p>
        <ReplayChart replay={r} reveal={reveal} adjusted={adjusted} showLater={showLater} />
        <details className="table-view">
          <summary>Table view ({r.hours.length} hours)</summary>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Hour (UK)</th>
                  <th>Forecast</th>
                  <th>Band low</th>
                  <th>Band high</th>
                  {adjusted && <th>Adjusted</th>}
                  {reveal && <th>Actual</th>}
                  {reveal && <th>Error</th>}
                  <th>Run used (UK)</th>
                  <th>Lead</th>
                </tr>
              </thead>
              <tbody>
                {r.hours.map((h) => (
                  <tr key={h.start_time} className={reveal && h.unusual_hour ? "unusual" : undefined}>
                    <td>{ukTime(h.start_time)}</td>
                    <td>{mw(h.forecast_mw)}</td>
                    <td>{mw(h.band_lo_mw)}</td>
                    <td>{mw(h.band_hi_mw)}</td>
                    {adjusted && <td>{mw(h.adjusted_mw)}</td>}
                    {reveal && <td>{mw(h.actual_mw)}</td>}
                    {reveal && <td>{signedMw(h.error_mw)}</td>}
                    <td>{h.publish_time ? ukDayTime(h.publish_time) : "–"}</td>
                    <td>{h.lead_h === null ? "–" : `${h.lead_h.toFixed(1)} h`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {reveal && (
            <p className="hint">
              Highlighted rows are unusual hours: a miss in the top {pct(0.05)} across all 31 days.
            </p>
          )}
        </details>
      </div>
    </div>
  );
}
