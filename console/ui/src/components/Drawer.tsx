import { ReactNode, useEffect } from 'react';
import { X } from 'lucide-react';

// Generic right-hand slide-over with a scrim. Closes on Escape or scrim click.
export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  actions,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="drawer-root" role="dialog" aria-modal="true">
      <div className="drawer-scrim" onClick={onClose} />
      <aside className="drawer">
        <header className="drawer-header">
          <div className="drawer-titles">
            <div className="drawer-title">{title}</div>
            {subtitle && <div className="drawer-subtitle">{subtitle}</div>}
          </div>
          <div className="drawer-header-actions">
            {actions}
            <button className="icon-btn sm" onClick={onClose} aria-label="Close" title="Close">
              <X size={18} />
            </button>
          </div>
        </header>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
