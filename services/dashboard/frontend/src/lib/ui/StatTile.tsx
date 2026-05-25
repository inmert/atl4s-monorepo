// Block-level label/value pair for stat strips at the top of a page.
// Prefer KeyValue for inline lists; StatTile is for the prominent
// "battery 100%" / "mode STABILIZE" boxes.

import type { ReactNode } from 'react';

export type StatTone = 'ok' | 'warn' | 'err';

export interface StatTileProps {
  label: ReactNode;
  value: ReactNode;
  tone?: StatTone;
}

export function StatTile({ label, value, tone }: StatTileProps) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ''}`}>{value}</div>
    </div>
  );
}
