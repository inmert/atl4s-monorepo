// Right-side sheet that slides in over the page. Closes on backdrop click
// and on Escape. Pass `open` and `onClose`; render children freely inside
// — there's no required body wrapper. Use for config panels, inspectors,
// any contextual edit surface that doesn't justify a full-screen modal.

import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { IconButton } from './IconButton';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  /** Default 420 px. Pass a number (pixels) or any CSS width string. */
  width?: number | string;
  children: ReactNode;
}

export function Drawer({ open, onClose, title, width = 420, children }: DrawerProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  const widthCss = typeof width === 'number' ? `${width}px` : width;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{ width: widthCss }}
      >
        <div className="drawer-header">
          <h2>{title}</h2>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </div>
        <div className="drawer-body">{children}</div>
      </aside>
    </div>
  );
}
