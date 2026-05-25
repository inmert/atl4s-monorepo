// Small indeterminate spinner. Uses pure CSS rotation; no JS animation
// loop. Default size matches a 14 px icon so it composes inside a Button.

export interface SpinnerProps {
  size?: number;
  /** Defaults to `currentColor` so it inherits from the parent (e.g. a Button). */
  color?: string;
  className?: string;
}

export function Spinner({ size = 14, color = 'currentColor', className = '' }: SpinnerProps) {
  const classes = ['spinner', className].filter(Boolean).join(' ');
  return (
    <span
      className={classes}
      role="status"
      aria-label="Loading"
      style={{
        width: size,
        height: size,
        borderColor: `${color} transparent transparent transparent`,
      }}
    />
  );
}
