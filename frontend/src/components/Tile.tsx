import type { ReactNode } from "react";

interface Props {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  revealed?: boolean;
}

// Stat tile: label, value, optional note (e.g. the n or a range). The number is the chart.
export function Tile({ label, value, note, revealed }: Props) {
  return (
    <div className={`tile${revealed ? " revealed" : ""}`}>
      <div className="label">{label}</div>
      <p className="value">{value}</p>
      {note && <div className="note">{note}</div>}
    </div>
  );
}
