import { useEffect } from "react";
import { api } from "../api";
import { REPO_URL } from "../config";
import { gw, mw, pct, ukFull } from "../lib/format";
import { useFetch } from "../lib/useFetch";
import type { Alignment, Meta } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  meta?: Meta;
  gate: string;
  align: Alignment;
  setAlign: (a: Alignment) => void;
}

export function MethodDrawer({ open, onClose, meta, gate, align, setAlign }: Props) {
  // The numbers quoted below come from the live scorecard for the current gate, never from text.
  const sc = useFetch(open ? `${gate}|${align}` : "closed", () =>
    open ? api.scorecard(gate, align) : Promise.reject(new Error("closed")),
  );
  const k = sc.data?.kpis;
  const lead = useFetch(open ? `lead|${align}` : "closed-lead", () =>
    open ? api.leadtime(align) : Promise.reject(new Error("closed")),
  );
  const nearest = lead.data?.buckets[0];
  const past = lead.data?.past_hours;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  const snap = meta?.snapshot;
  const win = meta?.scored_window;
  const runTimes = snap ? Object.entries(snap.publish_clock_times_utc).filter(([, n]) => n > 5).map(([t]) => t) : [];
  const alignDiff = k && k.mae !== null && k.alignment_other_mae !== null ? Math.abs(k.mae - k.alignment_other_mae) : null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-label="Method and data" onClick={(e) => e.stopPropagation()}>
        <div className="card-head">
          <h2 style={{ margin: 0 }}>Method &amp; data</h2>
          <button type="button" className="ghost" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        <h3>Scope</h3>
        <p>
          The brief limits the data to purchase decisions made in January 2026. A day-ahead decision made on day D-1 buys
          power for day D, so the app scores delivery days {win?.from ?? "2026-01-02"} to {win?.to ?? "2026-02-01"} (
          {win?.days ?? 31} days), using only forecasts that had been published by the gate on the day before. Earlier
          December days are loaded only as warm-up for the persistence baseline and the bias adjustment.
        </p>

        <h3>The rule</h3>
        <p>
          For each hour of delivery day D, use the forecast row with the <b>newest publish time at or before the gate</b>{" "}
          (default 09:20 UK on D-1, the EPEX 60-minute day-ahead auction). A run published exactly at the gate counts.
          Nothing published later is ever used; an hour with no eligible forecast stays empty and is counted as a gap. In
          code this is one <code>pandas.merge_asof</code> call, tested with golden days and a no-look-ahead check over every
          day in the window.
        </p>

        <h3>Lining up the two datasets</h3>
        <p>
          Actuals (FUELHH) are half-hourly averages; forecasts (WINDFOR) are hourly. The actual for forecast hour t is the
          mean of the two half-hours in [t, t+1h), matching the hourly blocks traded in the auctions. Hours with a missing
          half-hour are dropped, never guessed. Matching the first half-hour instead changes the MAE by{" "}
          {alignDiff === null ? "a few tens of MW" : `about ${mw(alignDiff)}`}, so the conclusions do not depend on it.
        </p>
        <div className="control">
          <span>Alignment (advanced)</span>
          <div className="segmented" role="group" aria-label="Alignment">
            <button type="button" aria-pressed={align === "block"} onClick={() => setAlign("block")}>
              Hourly block mean
            </button>
            <button type="button" aria-pressed={align === "point"} onClick={() => setAlign("point")}>
              First half-hour (point)
            </button>
          </div>
        </div>

        <h3>Sign convention</h3>
        <p>
          Error = forecast − actual. Positive means the forecast read high: less wind arrived than planned, so a buyer who
          trusted it was short and had to buy more at short notice.
        </p>

        <h3>The band</h3>
        <p>
          The 80% band around a forecast is empirical: the 10th and 90th percentiles of the error of every (run, hour) pair
          in the window made at the same lead time (3-hour buckets), leaving the day being shown out. Because the forecast
          runs high, the band sits mostly below the line. Checked out of sample: calibrated on days before{" "}
          {win?.oos_split ?? "2026-01-17"} and tested on the rest, the band contained the actual in{" "}
          {k ? pct(k.band_coverage_oos) : "about 88%"} of hours.
        </p>

        <h3>The finding</h3>
        <p>
          At the {gate} gate the forecast read about {k ? gw(k.bias) : "1.7 GW"} high in {k ? pct(k.share_over) : "85%"} of
          hours, and it still reads {nearest ? gw(nearest.bias_mw) : "about 1.4 GW"} high when made only 0–3 hours ahead.
          Even the forecast rows that describe hours already over ({past ? pct(past.share_of_rows) : "about 20%"} of the
          file, never used as forecasts) read {past ? gw(past.bias_mw) : "about 1.7 GW"} above the meter (Timing view). A gap
          that does not close as the weather becomes known points to the two datasets counting different things: WINDFOR is a forecast of
          what the wind fleet could produce, FUELHH is metered output after balancing actions such as curtailment. This is a
          hypothesis; proving it needs curtailment volumes, which is listed as pilot work. For the desk it is actionable now:
          the bias-adjusted line subtracts the previous week's average miss (days D-8 to D-2, all settled by the gate) and
          cuts the typical miss by {k ? pct(k.adjusted_improvement) : "about 20%"} with no look-ahead.
        </p>

        <h3>Unusual hours and days</h3>
        <p>
          Flags, not a model: an hour is unusual when its absolute error is in the top 5% for the window; a day when its
          net energy error is more than two standard deviations from the mean. Both can be checked by hand.
        </p>

        <h3>Data</h3>
        {snap ? (
          <ul className="meta-list">
            <li>
              Source: Elexon BMRS <code>WINDFOR</code> (forecast) and <code>FUELHH</code>, fuelType WIND (actual). Public, no
              key.
            </li>
            <li>Snapshot fetched {ukFull(snap.fetched_at_utc)} UK; the app never calls Elexon while serving.</li>
            <li>
              Forecast runs: {snap.runs} (
              {Object.entries(snap.runs_per_utc_day)
                .map(([k2, v]) => `${k2}/day × ${v} days`)
                .join(", ")}
              ), published around {runTimes.join(", ")} UTC; each covers a fixed 21:00-to-21:00 window of 73 hours.
            </li>
            <li>
              Scored actuals: {snap.scored_half_hours} half-hours ({win?.days ?? 31} × 48). Warm-up from {meta?.warmup_from}{" "}
              feeds only the persistence baseline and the bias adjustment.
            </li>
            {Object.entries(snap.files).map(([name, f]) => (
              <li key={name}>
                <code>{name}</code>: {f.rows.toLocaleString("en-GB")} rows, sha256 <code>{f.sha256.slice(0, 12)}…</code>
              </li>
            ))}
            {snap.warnings.length > 0 && <li>Warnings: {snap.warnings.join("; ")}</li>}
          </ul>
        ) : (
          <p className="hint">Loading snapshot details…</p>
        )}
        <p>
          <a href="/api/docs">API documentation</a>
          {REPO_URL && (
            <>
              {" · "}
              <a href={REPO_URL}>Source repository</a>
            </>
          )}
        </p>
      </aside>
    </div>
  );
}
