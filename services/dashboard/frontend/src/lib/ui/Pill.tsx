// Compact rounded indicator with an optional dot and an optional icon.
// Use cases: active-task banners, status chips, filter chips. Inline only;
// not for full-width row banners — use a Card or Banner for those.

import type { HTMLAttributes, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export type PillTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'err';

export interface PillProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: PillTone;
  icon?: LucideIcon;
  dot?: boolean;
  children: ReactNode;
}

export function Pill({
  tone = 'neutral',
  icon: Icon,
  dot,
  children,
  className = '',
  ...rest
}: PillProps) {
  const classes = ['pill', tone !== 'neutral' ? tone : '', className]
    .filter(Boolean)
    .join(' ');
  return (
    <span className={classes} {...rest}>
      {dot && <span className="pill-dot" />}
      {Icon && <Icon size={12} className="pill-icon" />}
      <span className="pill-label">{children}</span>
    </span>
  );
}
