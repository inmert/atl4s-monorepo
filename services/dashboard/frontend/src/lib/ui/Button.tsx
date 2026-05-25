// Primary action element. The wrapped <button> inherits the global button
// styling from primitives.css; variants map to existing CSS classes
// (`.ghost`, `.danger`, `.link`). The default is the filled accent style.

import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { Spinner } from './Spinner';

export type ButtonVariant = 'primary' | 'ghost' | 'danger' | 'link';
export type ButtonSize = 'sm' | 'md';

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  iconLeft?: LucideIcon;
  iconRight?: LucideIcon;
  loading?: boolean;
  type?: 'button' | 'submit' | 'reset';
  children?: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  iconLeft: IconLeft,
  iconRight: IconRight,
  loading = false,
  disabled,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const iconSize = size === 'sm' ? 12 : 14;
  const classes = [
    variant !== 'primary' ? variant : '',
    size === 'sm' ? 'size-sm' : '',
    loading ? 'loading' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <Spinner size={iconSize} />
      ) : IconLeft ? (
        <IconLeft size={iconSize} />
      ) : null}
      {children}
      {!loading && IconRight && <IconRight size={iconSize} />}
    </button>
  );
}
