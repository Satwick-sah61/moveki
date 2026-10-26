// Every time shown to a user is UK local time, whatever the viewer's own time zone.
const LONDON = "Europe/London";

const timeFmt = new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, hour: "2-digit", minute: "2-digit", hour12: false });
const dayTimeFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: LONDON,
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const dayFmt = new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, weekday: "short", day: "numeric", month: "short" });
const longDayFmt = new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, weekday: "long", day: "numeric", month: "long", year: "numeric" });

const shortDateFmt = new Intl.DateTimeFormat("en-GB", { timeZone: LONDON, weekday: "short", day: "numeric", month: "short" });

const fullFmt = new Intl.DateTimeFormat("en-GB", {
  timeZone: LONDON,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

export const ukTime = (iso: string) => timeFmt.format(new Date(iso));
export const ukFull = (iso: string) => fullFmt.format(new Date(iso));
export const ukShortDate = (iso: string) => shortDateFmt.format(new Date(iso));
export const ukDayTime = (iso: string) => dayTimeFmt.format(new Date(iso));
export const ukDay = (isoDate: string) => dayFmt.format(new Date(`${isoDate}T12:00:00Z`));
export const ukLongDay = (isoDate: string) => longDayFmt.format(new Date(`${isoDate}T12:00:00Z`));

export function mw(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits })} MW`;
}

export function gw(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v / 1000).toFixed(digits)} GW`;
}

export function gwh(v: number | null | undefined, digits = 1, signed = false): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const s = v.toFixed(digits);
  return `${signed && v > 0 ? "+" : ""}${s} GWh`;
}

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signedMw(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${v > 0 ? "+" : ""}${Math.round(v).toLocaleString("en-GB")} MW`;
}

export function hours(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  const h = Math.floor(v);
  const m = Math.round((v - h) * 60);
  return m ? `${h} h ${m} min` : `${h} h`;
}

export function leadRange(lo: number, hi: number): string {
  return `${lo.toFixed(1)}–${hi.toFixed(1)} h`;
}
