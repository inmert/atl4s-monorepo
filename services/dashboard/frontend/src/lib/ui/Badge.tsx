// Static text label with a semantic colour. Use for status (Running,
// Idle, Failed), categories (perception, fusion), or topic types. Not
// interactive — use a Pill or a Button if the chip should respond to
// click.

import type { ReactNode } from 'react';

export type Tone = 'ok' | 'idle' | 'warn' | 'err' | 'accent';

export interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
}

export function Badge({ tone, children }: BadgeProps) {
  return <span className={`badge${tone ? ` ${tone}` : ''}`}>{children}</span>;
}
