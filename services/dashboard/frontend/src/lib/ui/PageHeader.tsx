// Title + optional subtitle + right-side actions. Every top-level page
// starts with one of these so spacing and the bottom rule stay consistent.

import type { ReactNode } from 'react';

export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
}

export function PageHeader({ title, subtitle, right }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <div className="subtitle">{subtitle}</div>}
      </div>
      {right && <div className="page-header-right">{right}</div>}
    </div>
  );
}
