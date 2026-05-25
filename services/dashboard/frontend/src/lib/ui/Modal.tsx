// Centred dialog over a dimmed backdrop. Closes on backdrop click and on
// Escape. For contextual side panels (e.g. config drawers) prefer Drawer.

import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { IconButton } from './IconButton';

export interface ModalProps {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  /** Defaults to the CSS default (about 520 px). Pass a number (pixels) or any CSS width string. */
  width?: number | string;
}

export function Modal({ title, onClose, children, width }: ModalProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={width ? { maxWidth: width } : undefined}
      >
        <div className="modal-header">
          <h2>{title}</h2>
          <IconButton icon={X} label="Close" onClick={onClose} />
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
