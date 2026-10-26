import { useCallback } from "react";
import { api } from "./api";
import { Controls } from "./components/Controls";
import { MethodDrawer } from "./components/MethodDrawer";
import { ukFull } from "./lib/format";
import { useFetch } from "./lib/useFetch";
import { useUrlState, type View } from "./lib/urlState";
import { ReplayView } from "./views/Replay";
import { ScorecardView } from "./views/Scorecard";
import { TimingView } from "./views/Timing";

const VIEWS: { id: View; label: string }[] = [
  { id: "replay", label: "Decision replay" },
  { id: "scorecard", label: "January scorecard" },
  { id: "timing", label: "Timing" },
];

const FALLBACK_PRESETS = [
  { id: "epex60", label: "EPEX 60-min day-ahead auction", gate: "09:20", default: true },
  { id: "n2ex", label: "N2EX day-ahead auction", gate: "09:50", default: false },
  { id: "epex30", label: "EPEX 30-min day-ahead auction", gate: "15:30", default: false },
];

export default function App() {
  const [state, update] = useUrlState();
  const meta = useFetch("meta", api.meta);
  const presets = meta.data?.gate_presets ?? FALLBACK_PRESETS;
  const closeMethod = useCallback(() => update({ method: false }), [update]);

  return (
    <main className="shell">
      <header className="masthead">
        <div className="brand">
          <h1>Day-Ahead Wind Desk</h1>
          <p>GB wind forecast as seen at gate closure, scored against actual output · decisions made in January 2026</p>
        </div>
        <nav className="nav" aria-label="Views">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              type="button"
              aria-current={state.view === v.id ? "page" : undefined}
              onClick={() => update({ view: v.id })}
            >
              {v.label}
            </button>
          ))}
          <button type="button" className="ghost" onClick={() => update({ method: !state.method })}>
            Method &amp; data
          </button>
        </nav>
      </header>

      <Controls state={state} update={update} presets={presets} showDate={state.view === "replay"} />

      {state.view === "replay" && <ReplayView state={state} update={update} />}
      {state.view === "scorecard" && <ScorecardView state={state} update={update} />}
      {state.view === "timing" && <TimingView state={state} />}

      {meta.error && <div className="error">API unreachable: {meta.error}</div>}

      <MethodDrawer
        open={state.method}
        onClose={closeMethod}
        meta={meta.data}
        gate={state.gate}
        align={state.align}
        setAlign={(align) => update({ align })}
      />

      <footer className="foot">
        <span>
          Data: Elexon BMRS WINDFOR (forecast) and FUELHH WIND (actual), snapshot fetched{" "}
          {meta.data ? `${ukFull(meta.data.snapshot.fetched_at_utc)} UK` : "…"}.
        </span>
        <span>All times UK (Europe/London).</span>
        {state.align === "point" && <span>Alignment: first half-hour (point).</span>}
        <a href="/api/docs">API docs</a>
      </footer>
    </main>
  );
}
