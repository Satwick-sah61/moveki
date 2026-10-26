import { api } from "../api";
import { LeadTimeChart } from "../charts/LeadTimeChart";
import { RunBarChart } from "../charts/RunBarChart";
import { TimingChart } from "../charts/TimingChart";
import { Tile } from "../components/Tile";
import { mw, pct, signedMw, ukDay } from "../lib/format";
import { useFetch } from "../lib/useFetch";
import type { UrlState } from "../lib/urlState";
import type { Waiting } from "../types";

interface Props {
  state: UrlState;
}

export function TimingView({ state }: Props) {
  const { align, gate } = state;
  const timing = useFetch(`timing|${align}`, () => api.timing(align));
  const lead = useFetch(`lead|${align}`, () => api.leadtime(align));
  const wait = useFetch(`wait|${align}`, () => api.waiting(align));

  if (timing.error && !timing.data) return <div className="error">Could not load the timing curve: {timing.error}</div>;
  if (!timing.data) return <p className="hint">Computing the timing curve (50 gates)…</p>;
  const t = timing.data;
  const current = t.gates.find((g) => g.gate === gate);

  return (
    <div className={timing.loading || timing.error ? "stale" : undefined}>
      {timing.error && (
        <div className="error" style={{ marginBottom: 12 }}>
          Could not load this selection: {timing.error}. Showing the previous one.
        </div>
      )}
      <h2 style={{ margin: "0 0 2px" }}>Is it worth deciding later?</h2>
      <p className="hint" style={{ margin: "0 0 12px" }}>
        The same 31 decision days scored for every possible decision time on the day before. {t.headline}
      </p>

      <div className="card">
        <h2>Typical miss by decision time</h2>
        <p className="sub">
          Each point: decide at that UK time on D-1, use the newest run published by then, score every decision day. Vertical lines
          mark the auction gates{current ? `; your current gate ${gate} scores MAE ${mw(current.mae_mw)}` : ""}.
        </p>
        <TimingChart timing={t} currentGate={gate} />
        <details className="table-view">
          <summary>Table view ({t.gates.length} gates)</summary>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Gate (UK)</th>
                  <th>MAE</th>
                  <th>P90 |error|</th>
                  <th>Bias</th>
                  <th>Coverage</th>
                </tr>
              </thead>
              <tbody>
                {t.gates.map((g) => (
                  <tr key={g.gate}>
                    <td>{g.gate}</td>
                    <td>{mw(g.mae_mw)}</td>
                    <td>{mw(g.p90_abs_mw)}</td>
                    <td>{signedMw(g.bias_mw)}</td>
                    <td>{pct(g.coverage)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </div>

      <WaitingBlock wait={wait.data} error={wait.error} />

      <div className="card">
        <h2>Error against lead time</h2>
        <p className="sub">
          Every (run, hour) pair for the 31 delivery days, grouped by how far ahead the forecast was made (
          {lead.data?.bucket_hours ?? 3}-hour buckets). The miss grows with lead; the bias barely moves.
        </p>
        {lead.data ? <LeadTimeChart lead={lead.data} /> : <p className="hint">{lead.error ?? "Loading…"}</p>}
        {lead.data && <p className="hint">{lead.data.note}</p>}
        {lead.data && (
          <p className="hint">
            About {pct(lead.data.past_hours.share_of_rows, 1)} of the rows in the forecast file describe hours that were
            already over when the run was published ({lead.data.past_hours.hours_per_run_min} to{" "}
            {lead.data.past_hours.hours_per_run_max} hours per run, because every run starts at 21:00 UTC the evening before).
            They are never selected and never scored as forecasts. Measured against the meter they still read{" "}
            {signedMw(lead.data.past_hours.bias_mw)} high (MAE {mw(lead.data.past_hours.mae_mw)}, n ={" "}
            {lead.data.past_hours.scored_n.toLocaleString("en-GB")}), the same size as forecasts made 0–6 hours ahead. That
            points to a difference in what the two datasets count rather than to weather uncertainty (a hypothesis).
          </p>
        )}
        {lead.data && (
          <details className="table-view">
            <summary>Table view ({lead.data.buckets.length} buckets)</summary>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Lead (h)</th>
                    <th>n</th>
                    <th>MAE</th>
                    <th>Bias</th>
                    <th>P10 error</th>
                    <th>P90 error</th>
                  </tr>
                </thead>
                <tbody>
                  {lead.data.buckets.map((b) => (
                    <tr key={b.bucket}>
                      <td>
                        {b.bucket}–{b.bucket + lead.data!.bucket_hours}
                      </td>
                      <td>{b.n}</td>
                      <td>{mw(b.mae_mw)}</td>
                      <td>{signedMw(b.bias_mw)}</td>
                      <td>{signedMw(b.p10_err)}</td>
                      <td>{signedMw(b.p90_err)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function WaitingBlock({ wait, error }: { wait?: Waiting; error?: string }) {
  if (!wait) {
    return (
      <div className="card">
        <h2>How often does waiting pay?</h2>
        <p className="hint">{error ? `Could not load this block: ${error}` : "Computing day-by-day results…"}</p>
      </div>
    );
  }
  const later = wait.comparisons[wait.comparisons.length - 1];
  return (
    <div className="card">
      <h2>How often does waiting pay?</h2>
      <p className="sub">
        Day by day, using the actuals. This is hindsight: it shows whether waiting tends to pay, but no desk can know in advance
        which run will turn out closest.
      </p>

      {later && (
        <div className="tiles">
          <Tile
            label={`Deciding at ${later.gate} instead of ${later.baseline_gate}`}
            value={`closer on ${later.days_better} of ${later.days} days`}
            note={`further on ${later.days_worse}${later.days_same ? `, identical on ${later.days_same}` : ""}`}
          />
          <Tile label="Average gain" value={mw(later.mean_gain_mw)} note={`${pct(later.mean_gain_pct, 1)} lower miss`} />
          <Tile label="Median day" value={mw(later.median_gain_mw)} note="half of the days gained less" />
          <Tile
            label="Best / worst day"
            value={`${signedMw(later.best_gain_mw)} / ${signedMw(later.worst_gain_mw)}`}
            note={`${ukDay(later.best_gain_day)} / ${ukDay(later.worst_gain_day)}`}
          />
          <Tile
            label="Perfect hindsight (not achievable)"
            value={`−${pct(wait.oracle_improvement)}`}
            note={`best run every day: ${mw(wait.oracle_mae_mw)} vs ${mw(wait.baseline_mae_mw)}`}
          />
        </div>
      )}

      <ul className="sentences">
        {wait.sentences.map((s) => (
          <li key={s}>{s}</li>
        ))}
      </ul>

      <div className="two-col" style={{ marginTop: 12 }}>
        <div>
          <h3 style={{ fontSize: "0.95rem", margin: "0 0 2px" }}>Average miss when each run is used</h3>
          <p className="sub">Decide the minute the run is published, score all 31 days.</p>
          <RunBarChart runs={wait.runs} measure="mean_mae_mw" />
        </div>
        <div>
          <h3 style={{ fontSize: "0.95rem", margin: "0 0 2px" }}>Days each run was the closest (hindsight)</h3>
          <p className="sub">Spread across all eight runs: no single time is reliably best.</p>
          <RunBarChart runs={wait.runs} measure="best_days" />
        </div>
      </div>

      <div className="table-wrap" style={{ marginTop: 8 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Decision time</th>
              <th>Closer on</th>
              <th>Further on</th>
              <th>Same</th>
              <th>Average gain</th>
              <th>Median day</th>
              <th>Best day</th>
              <th>Worst day</th>
            </tr>
          </thead>
          <tbody>
            {wait.comparisons.map((c) => (
              <tr key={c.gate}>
                <td>
                  {c.gate} vs {c.baseline_gate}
                </td>
                <td>{c.days_better}</td>
                <td>{c.days_worse}</td>
                <td>{c.days_same}</td>
                <td>
                  {signedMw(c.mean_gain_mw)} ({pct(c.mean_gain_pct, 1)})
                </td>
                <td>{signedMw(c.median_gain_mw)}</td>
                <td>
                  {signedMw(c.best_gain_mw)} · {ukDay(c.best_gain_day)}
                </td>
                <td>
                  {signedMw(c.worst_gain_mw)} · {ukDay(c.worst_gain_day)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="table-view">
        <summary>Table view: every day ({wait.daily.length})</summary>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Delivery day</th>
                <th>Miss at {wait.baseline_gate}</th>
                <th>Miss at {later?.gate}</th>
                <th>Gain from waiting</th>
                <th>Closest run (hindsight)</th>
                <th>Its miss</th>
              </tr>
            </thead>
            <tbody>
              {wait.daily.map((d) => (
                <tr key={d.day}>
                  <td>{ukDay(d.day)}</td>
                  <td>{mw(d.mae_baseline_mw)}</td>
                  <td>{mw(d.mae_waited_mw)}</td>
                  <td>{signedMw(d.gain_mw)}</td>
                  <td>{d.best_run}</td>
                  <td>{mw(d.best_mae_mw)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint">{wait.note}</p>
      </details>
    </div>
  );
}
