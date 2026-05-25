// Shared UI primitives. Keep small — pages compose these instead of redefining
// chrome. Anything that grows page-specific stays in the page file.

import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
}) {
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

export function Card({
  title,
  right,
  children,
  className = '',
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  if (!title) {
    return <div className={`card ${className}`}>{children}</div>;
  }
  return (
    <div className={`card flush ${className}`}>
      <div className="card-header">
        <h2>{title}</h2>
        {right}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}

export function StatTile({
  label,
  value,
  tone,
}: {
  label: ReactNode;
  value: ReactNode;
  tone?: 'ok' | 'warn' | 'err';
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ''}`}>{value}</div>
    </div>
  );
}

export function Badge({
  tone,
  children,
}: {
  tone?: 'ok' | 'warn' | 'err' | 'accent';
  children: ReactNode;
}) {
  return <span className={`badge${tone ? ` ${tone}` : ''}`}>{children}</span>;
}

export function StatusDot({ tone }: { tone?: 'ok' | 'warn' | 'err' }) {
  return <span className={`dot${tone ? ` ${tone}` : ''}`} />;
}

export function EmptyState({
  icon: Icon,
  title,
  children,
}: {
  icon?: LucideIcon;
  title: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {Icon && <Icon className="empty-icon" />}
      <div className="empty-title">{title}</div>
      {children && <div>{children}</div>}
    </div>
  );
}

export function Subnav({
  items,
  active,
  onSelect,
}: {
  items: { id: string; label: string }[];
  active: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="subnav">
      {items.map((it) => (
        <a
          key={it.id}
          href="#"
          className={it.id === active ? 'active' : ''}
          onClick={(e) => {
            e.preventDefault();
            onSelect(it.id);
          }}
        >
          {it.label}
        </a>
      ))}
    </div>
  );
}
