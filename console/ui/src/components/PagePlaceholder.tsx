import { ReactNode } from 'react';
import { LucideIcon } from 'lucide-react';

// Shared scaffold for the not-yet-wired pages: a page header (icon + title +
// description) over an empty-state card. Each feature replaces the children as
// its logic lands; until then the card states the page is a placeholder.
export function PagePlaceholder({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page">
      <header className="page-header">
        <span className="page-header-icon">
          <Icon size={22} strokeWidth={2} />
        </span>
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-desc">{description}</p>
        </div>
      </header>

      <div className="page-body">
        {children ?? (
          <div className="empty-card">
            <span className="empty-badge">Placeholder</span>
            <p>
              This page is a placeholder. Its data and logic will be wired up next, through the same
              logic/design split the rest of the console uses.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
