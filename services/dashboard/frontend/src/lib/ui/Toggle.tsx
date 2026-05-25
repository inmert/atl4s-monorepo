// iOS-style switch. Controlled — pass `checked` and `onChange`. Native
// keyboard handling (Space / Enter to flip) comes for free via <button>.

import type { ButtonHTMLAttributes } from 'react';

export interface ToggleProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'onChange' | 'type' | 'children'> {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** Accessible name. Renders as a tooltip + aria-label when no surrounding label is present. */
  label?: string;
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
  className = '',
  ...rest
}: ToggleProps) {
  const classes = ['toggle', checked ? 'on' : '', className].filter(Boolean).join(' ');
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      title={label}
      className={classes}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      {...rest}
    >
      <span className="toggle-knob" />
    </button>
  );
}
