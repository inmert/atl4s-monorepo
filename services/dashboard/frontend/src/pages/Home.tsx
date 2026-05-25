import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Archive,
  Bot,
  Cpu,
  ExternalLink,
  Plane,
  MonitorPlay,
} from 'lucide-react';
import { useTopic, useTopics } from '../lib/topics';
import { api, type Bag } from '../lib/api';
import { foxgloveStudioUrl } from '../lib/foxglove';
import { formatBytes, formatDate } from '../lib/format';
import { Badge, Card, PageHeader, StatTile, StatusDot } from '../lib/components';

function levelNum(level: unknown): number {
  if (typeof level === 'number') return level;
  if (typeof level === 'string' && level.length > 0) return level.charCodeAt(0);
  return 0;
}

export function Home() {
  const state = useTopic('/mavros/state')?.data;
  const battery = useTopic('/mavros/battery')?.data;
  const health = useTopic('/atl4s/health');
  const { topics } = useTopics();

  const [bags, setBags] = useState<Bag[] | null>(null);

  useEffect(() => {
    api.listBags().then(setBags).catch(() => setBags([]));
  }, []);

  // Health summary
  const statuses = (health?.data?.status || []) as Array<{ level: unknown; name: string }>;
  const ok = statuses.filter((s) => levelNum(s.level) === 0).length;
  const warn = statuses.filter((s) => levelNum(s.level) === 1).length;
  const err = statuses.filter((s) => levelNum(s.level) >= 2).length;

  // Pipelines: count discovered perception / fusion outputs
  const perceptionTopics = Object.values(topics).filter(
    (t) => t.topic.startsWith('/perception/') || t.topic.startsWith('/fusion/'),
  );

  // Robots — Phase 1 hardcoded list. Phase 2 reads from the registry.
  const robots = [
    {
      id: 'gazebo-drone',
      name: 'Gazebo Drone',
      kind: 'Simulator',
      icon: MonitorPlay,
      online: Boolean(state?.connected),
      summary: state?.connected
        ? `${state?.mode || '—'} · ${state?.armed ? 'ARMED' : 'disarmed'}`
        : 'no link',
    },
    {
      id: 'orin-drone',
      name: 'Orin Drone',
      kind: 'Drone',
      icon: Plane,
      online: false,
      summary: 'not yet integrated',
    },
  ];

  const recentBags = (bags || []).slice(0, 4);
  const totalBytes = (bags || []).reduce((sum, b) => sum + b.size_bytes, 0);

  return (
    <section>
      <PageHeader
        title="Overview"
        subtitle="Pipeline status at a glance."
        right={
          <a
            className="foxglove-link"
            href={foxgloveStudioUrl()}
            target="_blank"
            rel="noreferrer"
          >
            Foxglove Studio <ExternalLink size={12} style={{ marginLeft: 4 }} />
          </a>
        }
      />

      <div className="stat-grid">
        <StatTile
          label="Battery"
          value={battery?.percentage != null ? `${(battery.percentage * 100).toFixed(0)}%` : '—'}
        />
        <StatTile
          label="Voltage"
          value={battery?.voltage != null ? `${battery.voltage.toFixed(2)} V` : '—'}
        />
        <StatTile
          label="Flight mode"
          value={state?.mode || '—'}
          tone={state?.armed ? 'warn' : undefined}
        />
        <StatTile
          label="Topics seen"
          value={Object.keys(topics).length}
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <Card
          title="Robots"
          right={<Link to="/robots" className="dim">View all →</Link>}
        >
          <div className="stack" style={{ gap: 10 }}>
            {robots.map((r) => (
              <Link
                key={r.id}
                to={`/robots/${r.id}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 12px',
                  borderRadius: 10,
                  background: 'var(--surface-2)',
                  color: 'var(--label)',
                  textDecoration: 'none',
                }}
              >
                <r.icon size={20} style={{ opacity: 0.85, flex: 'none' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600 }}>{r.name}</div>
                  <div className="dim" style={{ fontSize: 12 }}>
                    {r.kind} · {r.summary}
                  </div>
                </div>
                <StatusDot tone={r.online ? 'ok' : undefined} />
              </Link>
            ))}
          </div>
        </Card>

        <Card
          title="Health"
          right={<Link to="/health" className="dim">Details →</Link>}
        >
          {!health ? (
            <p className="placeholder">
              Waiting for <code>/atl4s/health</code>…
            </p>
          ) : (
            <div className="stack" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 8 }}>
                <Badge tone="ok">{ok} OK</Badge>
                {warn > 0 && <Badge tone="warn">{warn} warn</Badge>}
                {err > 0 && <Badge tone="err">{err} error</Badge>}
              </div>
              <div className="dim" style={{ fontSize: 12 }}>
                Aggregated over {statuses.length} tracked topic
                {statuses.length === 1 ? '' : 's'}. Last update at{' '}
                {new Date((health.ts ?? 0) * 1000).toLocaleTimeString()}.
              </div>
            </div>
          )}
        </Card>

        <Card
          title="Pipelines"
          right={<Link to="/pipelines" className="dim">Configure →</Link>}
        >
          {perceptionTopics.length === 0 ? (
            <p className="placeholder">
              No <code>/perception/*</code> or <code>/fusion/*</code> outputs yet. Start
              a perception service to see its topics here.
            </p>
          ) : (
            <div className="stack" style={{ gap: 6 }}>
              {perceptionTopics.slice(0, 4).map((t) => (
                <div key={t.topic} className="row space" style={{ fontSize: 13 }}>
                  <code style={{ color: 'var(--label-2)' }}>{t.topic}</code>
                  <span className="dim mono" style={{ fontSize: 12 }}>
                    {t.rate.toFixed(1)} Hz
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Rosbags"
          right={<Link to="/rosbags" className="dim">Browse →</Link>}
        >
          {bags === null ? (
            <p className="placeholder">Loading…</p>
          ) : bags.length === 0 ? (
            <p className="placeholder">
              No bags in GCS. Record one from <Link to="/rosbags/record">Record</Link>.
            </p>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              <div className="dim" style={{ fontSize: 12 }}>
                {bags.length} bag{bags.length === 1 ? '' : 's'} · {formatBytes(totalBytes)} total
              </div>
              {recentBags.map((b) => (
                <div key={b.name} className="row space" style={{ fontSize: 13 }}>
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {b.name}
                  </span>
                  <span className="dim mono" style={{ fontSize: 12 }}>
                    {formatBytes(b.size_bytes)} · {formatDate(b.updated)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-3">
        <QuickLink to="/robots" icon={Bot} title="Robots" hint="Per-device telemetry, map, camera." />
        <QuickLink to="/pipelines" icon={Cpu} title="Pipelines" hint="Configure perception services." />
        <QuickLink to="/rosbags" icon={Archive} title="Rosbags" hint="Browse, record, replay bags." />
        <QuickLink to="/health" icon={Activity} title="Health" hint="Containers + topic liveness." />
      </div>
    </section>
  );
}

function QuickLink({
  to,
  icon: Icon,
  title,
  hint,
}: {
  to: string;
  icon: typeof Bot;
  title: string;
  hint: string;
}) {
  return (
    <Link
      to={to}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 14,
        padding: 16,
        borderRadius: 'var(--radius-lg)',
        background: 'var(--surface)',
        boxShadow: 'var(--shadow-1)',
        color: 'var(--label)',
        textDecoration: 'none',
        transition: 'transform 0.12s var(--ease), background 0.12s var(--ease)',
      }}
    >
      <Icon size={22} style={{ color: 'var(--accent)', flex: 'none' }} />
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
        <div className="dim" style={{ fontSize: 12 }}>
          {hint}
        </div>
      </div>
    </Link>
  );
}
