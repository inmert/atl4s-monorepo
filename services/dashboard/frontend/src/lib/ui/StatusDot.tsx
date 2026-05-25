// Tiny coloured circle. Use beside a label to convey liveness ("Gazebo
// Drone •"). Shares the Tone vocabulary with Badge.

import type { Tone } from './Badge';

export interface StatusDotProps {
  tone?: Tone;
}

export function StatusDot({ tone }: StatusDotProps) {
  return <span className={`dot${tone ? ` ${tone}` : ''}`} />;
}
