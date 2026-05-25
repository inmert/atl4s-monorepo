// Inline label/value pair. Compact alternative to StatTile when you want
// a dense list (metadata panels, row inspectors). Pass `mono` for values
// you want in the monospace face (topic names, IDs, hex).

import type { ReactNode } from 'react';

export interface KeyValueProps {
  label: ReactNode;
  value: ReactNode;
  mono?: boolean;
  className?: string;
}

export function KeyValue({ label, value, mono = false, className = '' }: KeyValueProps) {
  const classes = ['kv', className].filter(Boolean).join(' ');
  return (
    <div className={classes}>
      <span className="kv-label">{label}</span>
      <span className={`kv-value${mono ? ' mono' : ''}`}>{value}</span>
    </div>
  );
}
