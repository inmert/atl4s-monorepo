// "Nothing here yet" placeholder. Pass a lucide icon and a short title;
// children render as supporting text beneath.

import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: ReactNode;
  children?: ReactNode;
}

export function EmptyState({ icon: Icon, title, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {Icon && <Icon className="empty-icon" />}
      <div className="empty-title">{title}</div>
      {children && <div>{children}</div>}
    </div>
  );
}
