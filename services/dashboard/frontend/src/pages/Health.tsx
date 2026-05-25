// Health page — two sections backed by /api/health (single fetch shared
// via lib/health.tsx). Containers come from the host Docker daemon over
// the bind-mounted /var/run/docker.sock. Topic liveness is computed
// from the dashboard's own topic-bridge timestamps, replacing the old
// services/healthcheck stand-alone container.

import { Activity, Box, RefreshCw, Share2 } from 'lucide-react';
import { useHealth } from '../lib/health';
import type { ContainerInfo, HealthLevel, TopicHealth } from '../lib/api';
import { Badge, Card, EmptyState, PageHeader, StatusDot } from '../lib/components';

const LEVEL_LABEL: Record<HealthLevel, string> = {
  ok: 'OK',
  idle: 'IDLE',
  warn: 'WARN',
  err: 'ERROR',
};

function fmtUptime(sec: number | null): string {
  if (sec == null || Number.isNaN(sec) || sec < 0) return '—';
  if (sec < 60) return `${sec.toFixed(0)}s`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`;
  if (sec < 86400) return `${(sec / 3600).toFixed(1)}h`;
  return `${(sec / 86400).toFixed(1)}d`;
}

function fmtAge(sec: number | null): string {
  if (sec == null || Number.isNaN(sec)) return '—';
  if (sec < 1) return `${(sec * 1000).toFixed(0)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

export function Health() {
  const { snap, error, refresh } = useHealth();

  return (
    <section>
      <PageHeader
        title="Health"
        subtitle={
          snap
            ? `${snap.summary.ok} OK · ${snap.summary.warn} warn · ${snap.summary.err} error`
            : 'Loading…'
        }
        right={
          <>
            {snap && (
              <Badge tone={snap.level}>
                <StatusDot tone={snap.level} />
                {LEVEL_LABEL[snap.level]}
              </Badge>
            )}
            <button className="ghost" onClick={refresh} title="Refresh">
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      {error && <p className="error">{error}</p>}

      {!snap ? (
        <p className="placeholder">Loading…</p>
      ) : (
        <div className="grid grid-2" style={{ alignItems: 'start' }}>
          <Card
            title={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Box size={14} /> Containers
              </span>
            }
            right={
              <span className="dim" style={{ fontSize: 12 }}>
                {snap.containers.length} tracked
              </span>
            }
            className="flush"
          >
            {!snap.docker_available ? (
              <div className="card-body">
                <EmptyState icon={Box} title="Docker socket unavailable">
                  Mount <code>/var/run/docker.sock</code> into the dashboard container
                  to enable per-container health.
                </EmptyState>
              </div>
            ) : snap.containers.length === 0 ? (
              <div className="card-body">
                <p className="placeholder">
                  No containers matching <code>atl4s-</code> prefix.
                </p>
              </div>
            ) : (
              <ContainerTable containers={snap.containers} />
            )}
          </Card>

          <Card
            title={
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Share2 size={14} /> Topic liveness
              </span>
            }
            right={
              <span className="dim" style={{ fontSize: 12 }}>
                {snap.topics.length} tracked
              </span>
            }
            className="flush"
          >
            {snap.topics.length === 0 ? (
              <div className="card-body">
                <EmptyState icon={Activity} title="No topics tracked">
                  Add telemetry topics to any robot in{' '}
                  <code>services/dashboard/config/robots.yaml</code>.
                </EmptyState>
              </div>
            ) : (
              <TopicTable topics={snap.topics} />
            )}
          </Card>
        </div>
      )}
    </section>
  );
}

function ContainerTable({ containers }: { containers: ContainerInfo[] }) {
  return (
    <table className="bags">
      <thead>
        <tr>
          <th>Name</th>
          <th>State</th>
          <th>Uptime</th>
          <th>Restarts</th>
          <th>Level</th>
        </tr>
      </thead>
      <tbody>
        {containers.map((c) => (
          <tr key={c.name}>
            <td className="mono">{c.name}</td>
            <td>
              {c.state}
              {c.health ? <span className="dim"> · {c.health}</span> : null}
            </td>
            <td className="dim">{fmtUptime(c.uptime_sec)}</td>
            <td className={c.restart_count > 0 ? 'dim' : 'dim'}>
              {c.restart_count}
            </td>
            <td>
              <Badge tone={c.level}>{LEVEL_LABEL[c.level]}</Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function TopicTable({ topics }: { topics: TopicHealth[] }) {
  return (
    <table className="bags">
      <thead>
        <tr>
          <th>Topic</th>
          <th>Robot · key</th>
          <th>Rate</th>
          <th>Age</th>
          <th>Level</th>
        </tr>
      </thead>
      <tbody>
        {topics.map((t) => (
          <tr key={`${t.robot_id}-${t.key}-${t.topic}`}>
            <td className="mono">{t.topic}</td>
            <td className="dim">
              {t.robot_id} · {t.key}
            </td>
            <td className="dim mono">{t.rate > 0 ? `${t.rate.toFixed(1)} Hz` : '—'}</td>
            <td className="dim mono">{fmtAge(t.age_sec)}</td>
            <td>
              <Badge tone={t.level}>{LEVEL_LABEL[t.level]}</Badge>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
