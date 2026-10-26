// View state lives in the URL query (?view=replay&date=2026-01-28&gate=09:20&reveal=1), so
// every screen is a shareable link and the browser's back button works without a router.

import { useCallback, useEffect, useState } from "react";
import type { Alignment } from "../types";

export type View = "replay" | "scorecard" | "timing";

export interface UrlState {
  view: View;
  date: string;
  gate: string;
  reveal: boolean;
  adjusted: boolean;
  align: Alignment;
  method: boolean;
}

export const DEFAULTS: UrlState = {
  view: "replay",
  date: "2026-01-28",
  gate: "09:20",
  reveal: false,
  adjusted: false,
  align: "block",
  method: false,
};

// Delivery days for decisions made in January: 2 January to 1 February 2026.
export const FIRST_DAY = "2026-01-02";
export const LAST_DAY = "2026-02-01";
const DATE_RE = /^2026-(01-(0[2-9]|[12]\d|3[01])|02-01)$/;
const GATE_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

function parse(search: string): UrlState {
  const q = new URLSearchParams(search);
  const view = q.get("view");
  const date = q.get("date");
  const gate = q.get("gate");
  const align = q.get("align");
  return {
    view: view === "scorecard" || view === "timing" ? view : "replay",
    date: date && DATE_RE.test(date) ? date : DEFAULTS.date,
    gate: gate && GATE_RE.test(gate) ? gate : DEFAULTS.gate,
    reveal: q.get("reveal") === "1",
    adjusted: q.get("adjusted") === "1",
    align: align === "point" ? "point" : "block",
    method: q.get("method") === "1",
  };
}

function serialise(s: UrlState): string {
  const q = new URLSearchParams();
  if (s.view !== DEFAULTS.view) q.set("view", s.view);
  if (s.date !== DEFAULTS.date) q.set("date", s.date);
  if (s.gate !== DEFAULTS.gate) q.set("gate", s.gate);
  if (s.reveal) q.set("reveal", "1");
  if (s.adjusted) q.set("adjusted", "1");
  if (s.align !== DEFAULTS.align) q.set("align", s.align);
  if (s.method) q.set("method", "1");
  const str = q.toString();
  return str ? `?${str}` : "";
}

export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const [state, setState] = useState<UrlState>(() => parse(window.location.search));

  useEffect(() => {
    const onPop = () => setState(parse(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const update = useCallback((patch: Partial<UrlState>) => {
    setState((prev) => {
      const next = { ...prev, ...patch };
      const url = `${window.location.pathname}${serialise(next)}`;
      if (url !== `${window.location.pathname}${window.location.search}`) {
        window.history.pushState(null, "", url);
      }
      return next;
    });
  }, []);

  return [state, update];
}
