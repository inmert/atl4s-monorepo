import { Level } from '../lib/api';

const LABEL: Record<Level, string> = { ok: 'OK', warn: 'Warning', err: 'Error', idle: 'Idle' };

export function StatusDot({ level }: { level: Level }) {
  return <span className={`status-dot level-${level}`} aria-hidden />;
}

// Compact state badge: a dot + the container's state/health text.
export function StatusBadge({ level, text }: { level: Level; text: string }) {
  return (
    <span className={`badge level-${level}`} title={LABEL[level]}>
      <span className="status-dot" />
      {text}
    </span>
  );
}
