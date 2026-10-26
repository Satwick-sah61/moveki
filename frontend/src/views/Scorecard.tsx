import { api } from "../api";
import { CalendarHeatmap } from "../charts/CalendarHeatmap";
import { HistogramChart } from "../charts/HistogramChart";
import { HourOfDayChart } from "../charts/HourOfDayChart";
import { Tile } from "../components/Tile";
import { gw, gwh, mw, pct, signedMw, ukDay, ukDayTime } from "../lib/format";
import { useFetch } from "../lib/useFetch";
import type { UrlState } from "../lib/urlState";

interface Props {
  state: UrlState;
  update: (patch: Partial<UrlState>) => void;
}

export function ScorecardView({ state, update }: Props) {
  const { gate, align } = state;
  const { data, error, loading } = useFetch(`${gate}|${align}`, () => api.scorecard(gate, align));
  if (error && !data) return <div className="error">Could not load the scorecard: {error}</div>;
  if (!data) return <p className="hint">Loading the scorecard…</p>;

  const k = data.kpis;
  const n = `n = ${k.n} hours`;
  const openDay = (day: string) => update({ view: "replay", date: day, reveal: true });

  return (
    <div className={loading || error ? "stale" : undefined}>
      {error && (
        <div className="error" style={{ marginBottom: 12 }}>
          Could not load this selection: {error}. Showing the previous one.
        </div>
      )}
      <h2 style={{ margin: "0 0 2px" }}>Decisions made in January 2026, at the {data.gate} gate</h2>
      <p className="hint" style={{ margin: "0 0 12px" }}>
        The same rule applied to all {data.days} decision days (delivery 2 Jan – 1 Feb): for every hour, the newest forecast
        published by {data.gate} UK the day before. Error = forecast − actual; positive means the forecast read high and the
        buyer was short.
      </p>

      <div className="tiles">
        <Tile label="Typical miss (MAE)" value={mw(k.mae)} note={n} />
        <Tile label="Bias (forecast − actual)" value={signedMw(k.bias)} note={`high in ${pct(k.share_over)} of hours`} />
        <Tile label="9 hours in 10 the miss was under" value={gw(k.p90_abs, 1)} note={`P90 of |error|; max ${gw(k.max_abs, 1)}`} />
        <Tile label="Shortfall cover (P90)" value={gw(k.p90_shortfall, 1)} note="plan this much less wind to be covered 9 in 10" />
        <Tile label="WAPE" value={pct(k.wape, 1)} note="sum |error| / sum actual" />
        <Tile label="Skill vs persistence" value={pct(k.skill_vs_persistence)} note={`persistence MAE ${mw(k.persistence_mae)}`} />
        <Tile
          label="MAE with last week's bias removed"
          value={mw(k.adjusted_mae)}
          note={`${pct(k.adjusted_improvement)} better, bias ${signedMw(k.adjusted_bias)}`}
        />
        <Tile label="80% band hit rate (out of sample)" value={pct(k.band_coverage_oos)} note="calibrated 2–16 Jan, tested 17 Jan – 1 Feb" />
        <Tile label="Net energy error per day" value={gwh(k.mean_daily_net_gwh, 0, true)} note="planned wind that never arrived" />
        <Tile label="Coverage" value={pct(k.coverage)} note={`${k.n} of ${k.hours_expected} hours scored`} />
        <Tile label="Unusual hours / days" value={`${k.unusual_hours} / ${k.unusual_days}`} note={`|error| ≥ ${gw(k.unusual_hour_threshold_mw, 1)}; day > 2σ`} />
        <Tile label="RMSE" value={mw(k.rmse)} note={`RMSE/MAE ${k.rmse && k.mae ? (k.rmse / k.mae).toFixed(2) : "–"} (tail weight)`} />
      </div>

      <div className="card">
        <h2>What this means for buying</h2>
        <p className="sub">Sentences generated from the numbers above, so they cannot say more than the data does.</p>
        <ul className="sentences">
          {data.sentences.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h2>Day by day</h2>
        <p className="sub">Daily MAE, darker = worse. Errors cluster by day, so the day is the unit that matters for a desk.</p>
        <CalendarHeatmap daily={data.daily} onPick={openDay} />
        <details className="table-view">
          <summary>Table view ({data.daily.length} days)</summary>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Hours</th>
                  <th>MAE</th>
                  <th>Bias</th>
                  <th>Net energy</th>
                  <th>Flag</th>
                </tr>
              </thead>
              <tbody>
                {data.daily.map((d) => (
                  <tr key={d.day} className={`clickable${d.unusual ? " unusual" : ""}`} onClick={() => openDay(d.day)}>
                    <td>{ukDay(d.day)}</td>
                    <td>{d.hours}</td>
                    <td>{mw(d.mae_mw)}</td>
                    <td>{signedMw(d.bias_mw)}</td>
                    <td>{gwh(d.net_gwh, 1, true)}</td>
                    <td>{d.unusual ? "unusual" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <div className="two-col">
        <div className="card">
          <h2>Bias by hour of day</h2>
          <p className="sub">Mean of forecast − actual for each UK hour (n = 31 days each, a small sample).</p>
          <HourOfDayChart rows={data.by_hour} measure="bias_mw" />
        </div>
        <div className="card">
          <h2>Typical miss by hour of day</h2>
          <p className="sub">MAE for each UK hour, GW (n = 31 days each).</p>
          <HourOfDayChart rows={data.by_hour} measure="mae_mw" />
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h2>How the errors are spread</h2>
          <p className="sub">Hours per 500 MW bin of forecast − actual. Most of the mass sits right of zero.</p>
          <HistogramChart bins={data.histogram} p90={k.p90_abs} bias={k.bias} />
        </div>
        <div className="card">
          <h2>Worst days and hours</h2>
          <p className="sub">By net energy error (days) and by absolute miss (hours). Click a day to replay it.</p>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Day</th>
                  <th>Net energy</th>
                  <th>MAE</th>
                </tr>
              </thead>
              <tbody>
                {data.worst_days.map((d) => (
                  <tr key={d.day} className={`clickable${d.unusual ? " unusual" : ""}`} onClick={() => openDay(d.day)}>
                    <td>{ukDay(d.day)}</td>
                    <td>{gwh(d.net_gwh, 1, true)}</td>
                    <td>{mw(d.mae_mw)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <table className="data" style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Hour (UK)</th>
                  <th>Forecast</th>
                  <th>Actual</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {data.worst_hours.slice(0, 5).map((h) => (
                  <tr key={h.start_time}>
                    <td>{ukDayTime(h.start_time)}</td>
                    <td>{mw(h.forecast_mw)}</td>
                    <td>{mw(h.actual_mw)}</td>
                    <td>{signedMw(h.error_mw)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <p className="hint">
        Alignment sensitivity: with point-matched actuals instead of the hourly block mean the MAE is {mw(k.alignment_other_mae)}, so
        the conclusions do not depend on that choice.
      </p>
    </div>
  );
}
