// Square button containing a single icon, no text. Common in modal close
// affordances and inline row actions where space is tight.

import type { ButtonHTMLAttributes } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { ButtonVariant, ButtonSize } from './Button';

export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'children' | 'type'> {
  icon: LucideIcon;
  /** Accessible name — required for screen readers since there's no text. */
  label: string;
  variant?: ButtonVariant;
  size?: ButtonSize;
  type?: 'button' | 'submit' | 'reset';
}

export function IconButton({
  icon: Icon,
  label,
  variant = 'ghost',
  size = 'md',
  className = '',
  type = 'button',
  ...rest
}: IconButtonProps) {
  const iconSize = size === 'sm' ? 12 : 14;
  const classes = [
    'icon-only',
    variant !== 'primary' ? variant : '',
    size === 'sm' ? 'size-sm' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button type={type} className={classes} title={label} aria-label={label} {...rest}>
      <Icon size={iconSize} />
    </button>
  );
}
