// Thin typed client for the FastAPI backend. Every call is a relative /api path so the
// same code works in dev (Vite proxy), in Docker and on Vercel without any config.

import type { Alignment, Health, LeadTime, Meta, Replay, Scorecard, Timing, Waiting } from "./types";

const TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
  }
}

async function getJson<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = params ? `${path}?${new URLSearchParams(params)}` : path;
  // A timeout so the page says "unreachable" instead of spinning forever if the server hangs.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(url, { headers: { Accept: "application/json" }, signal: controller.signal });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") detail = body.detail;
        else if (Array.isArray(body.detail)) detail = JSON.stringify(body.detail);
      } catch {
        // keep statusText
      }
      throw new ApiError(`${url}: ${res.status} ${detail}`, res.status);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    const reason = err instanceof Error && err.name === "AbortError" ? "timed out" : String(err);
    throw new ApiError(`${url}: ${reason}`);
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => getJson<Health>("/api/health"),
  meta: () => getJson<Meta>("/api/meta"),
  decision: (date: string, gate: string, align: Alignment) =>
    getJson<Replay>("/api/decision", { date, gate, align }),
  scorecard: (gate: string, align: Alignment) => getJson<Scorecard>("/api/scorecard", { gate, align }),
  timing: (align: Alignment) => getJson<Timing>("/api/timing", { align }),
  leadtime: (align: Alignment) => getJson<LeadTime>("/api/leadtime", { align }),
  waiting: (align: Alignment) => getJson<Waiting>("/api/waiting", { align }),
};
