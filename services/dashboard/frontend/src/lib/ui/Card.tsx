// Surface container. Two modes: `title` set → flush variant with a header
// strip; `title` omitted → padded blank surface. Stack Cards in any layout
// helper (.grid, .stack, .row) for consistent spacing.

import type { ReactNode } from 'react';

export interface CardProps {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ title, right, children, className = '' }: CardProps) {
  if (!title) {
    return <div className={`card ${className}`.trim()}>{children}</div>;
  }
  return (
    <div className={`card flush ${className}`.trim()}>
      <div className="card-header">
        <h2>{title}</h2>
        {right}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}
