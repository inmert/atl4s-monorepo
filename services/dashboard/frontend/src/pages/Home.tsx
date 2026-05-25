import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  Archive,
  Bot,
  Cpu,
  Disc,
  ExternalLink,
  Play,
} from 'lucide-react';
import { useTopics } from '../lib/topics';
import { useHealth } from '../lib/health';
import {
  api,
  type Bag,
  type Pipeline,
  type RecordStatus,
  type ReplayStatus,
  type Robot,
} from '../lib/api';
import { foxgloveStudioUrl } from '../lib/foxglove';
import { formatBytes, formatDate } from '../lib/format';
import { iconFor, isOnline, summarize } from '../lib/robots';
import { Badge, Card, PageHeader, StatTile, StatusDot } from '../lib/components';

const POLL_MS = 3000;

export function Home() {
  const { topics } = useTopics();
  const { snap: health } = useHealth();

  const [robots, setRobots] = useState<Robot[] | null>(null);
  const [bags, setBags] = useState<Bag[] | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[] | null>(null);
  const [recordStatus, setRecordStatus] = useState<RecordStatus | null>(null);
  const [replayStatus, setReplayStatus] = useState<ReplayStatus | null>(null);

  // One initial fetch for the (rarely-changing) registries; one polled fetch
  // for the things that update during a session (record/replay state + bag
  // list since recordings land there).
  useEffect(() => {
    api.listRobots().then(setRobots).catch(() => setRobots([]));
    api.listPipelines().then(setPipelines).catch(() => setPipelines([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const [b, rs, ps] = await Promise.all([
          api.listBags(),
          api.recordStatus(),
          api.replayStatus(),
        ]);
        if (cancelled) return;
        setBags(b);
        setRecordStatus(rs);
        setReplayStatus(ps);
      } catch {
        if (!cancelled && bags === null) setBags([]);
      }
    };
    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Headline tiles take from the first online robot (single-drone case stays
  // useful; multi-robot picks the first that's actually live).
  const primaryRobot = (robots || []).find((r) => isOnline(r, topics));
  const state = primaryRobot?.telemetry.state ? topics[primaryRobot.telemetry.state]?.data : undefined;
  const battery = primaryRobot?.telemetry.battery ? topics[primaryRobot.telemetry.battery]?.data : undefined;

  const recording = recordStatus?.state === 'recording';
  const replayBusy = replayStatus && replayStatus.state !== 'idle';

  const runningPipelines = (pipelines || []).filter((p) => p.status.state === 'running');

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

      <ActiveBanner recordStatus={recordStatus} replayStatus={replayStatus} />

      <div className="stat-grid">
        <StatTile
          label={primaryRobot ? `${primaryRobot.name} · Battery` : 'Battery'}
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
          label="Pipelines running"
          value={pipelines === null ? '—' : `${runningPipelines.length} / ${pipelines.length}`}
        />
      </div>

      <div className="grid grid-2" style={{ marginBottom: 20 }}>
        <Card
          title="Robots"
          right={<Link to="/robots" className="dim">View all →</Link>}
        >
          {robots === null ? (
            <p className="placeholder">Loading…</p>
          ) : robots.length === 0 ? (
            <p className="placeholder">
              No robots configured. Edit <code>config/robots.yaml</code>.
            </p>
          ) : (
            <div className="stack" style={{ gap: 10 }}>
              {robots.map((r) => {
                const Icon = iconFor(r.icon);
                const online = isOnline(r, topics);
                return (
                  <Link key={r.id} to={`/robots/${r.id}`} className="home-row">
                    <Icon size={20} style={{ opacity: 0.85, flex: 'none' }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{r.name}</div>
                      <div className="dim" style={{ fontSize: 12, textTransform: 'capitalize' }}>
                        {r.kind} · {summarize(r, topics)}
                      </div>
                    </div>
                    <StatusDot tone={online ? 'ok' : undefined} />
                  </Link>
                );
              })}
            </div>
          )}
        </Card>

        <Card
          title="Health"
          right={<Link to="/health" className="dim">Details →</Link>}
        >
          {!health ? (
            <p className="placeholder">Loading…</p>
          ) : (
            <div className="stack" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 8 }}>
                <Badge tone="ok">{health.summary.ok} OK</Badge>
                {health.summary.idle > 0 && <Badge tone="idle">{health.summary.idle} idle</Badge>}
                {health.summary.warn > 0 && <Badge tone="warn">{health.summary.warn} warn</Badge>}
                {health.summary.err > 0 && <Badge tone="err">{health.summary.err} error</Badge>}
              </div>
              <div className="dim" style={{ fontSize: 12 }}>
                {health.containers.length} container
                {health.containers.length === 1 ? '' : 's'} ·{' '}
                {health.topics.length} topic
                {health.topics.length === 1 ? '' : 's'} tracked.
                {!health.docker_available && ' Docker socket unavailable.'}
              </div>
            </div>
          )}
        </Card>

        <Card
          title="Pipelines"
          right={<Link to="/pipelines" className="dim">Configure →</Link>}
        >
          {pipelines === null ? (
            <p className="placeholder">Loading…</p>
          ) : pipelines.length === 0 ? (
            <p className="placeholder">
              No pipelines configured. Edit <code>config/pipelines.yaml</code>.
            </p>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {pipelines.map((p) => (
                <Link key={p.id} to="/pipelines" className="home-row">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600 }}>{p.name}</div>
                    <div className="dim" style={{ fontSize: 12 }}>
                      {p.input_topics[0] || '—'} → {p.output_topics[0] || '—'}
                    </div>
                  </div>
                  <Badge tone={p.status.level}>
                    <StatusDot tone={p.status.level} />
                    {p.status.state === 'running'
                      ? 'Running'
                      : p.status.state === 'absent'
                        ? 'Not deployed'
                        : p.status.state}
                  </Badge>
                </Link>
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
              No bags in GCS. Start one from <Link to="/rosbags">Rosbag Manager</Link>.
            </p>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              <div className="dim" style={{ fontSize: 12 }}>
                {bags.length} bag{bags.length === 1 ? '' : 's'} · {formatBytes(totalBytes)} total
                {recording && ' · 1 recording'}
                {replayBusy && ' · 1 replaying'}
              </div>
              {recentBags.map((b) => (
                <div key={b.name} className="row space" style={{ fontSize: 13 }}>
                  <span
                    style={{
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
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

function ActiveBanner({
  recordStatus,
  replayStatus,
}: {
  recordStatus: RecordStatus | null;
  replayStatus: ReplayStatus | null;
}) {
  const recording = recordStatus?.state === 'recording' || recordStatus?.state === 'stopping';
  const replayBusy = replayStatus && replayStatus.state !== 'idle';
  if (!recording && !replayBusy) return null;
  return (
    <div className="row" style={{ gap: 10, marginBottom: 20, flexWrap: 'wrap' }}>
      {recording && (
        <Link to="/rosbags" className="active-pill rec">
          <Disc size={13} />
          <span>
            {recordStatus?.state === 'stopping' ? 'Stopping recording' : 'Recording'}
            {recordStatus?.name ? ` — ${recordStatus.name}` : ''}
          </span>
        </Link>
      )}
      {replayBusy && (
        <Link to="/rosbags" className="active-pill rep">
          <Play size={13} />
          <span>
            {replayStatus?.state === 'downloading'
              ? 'Downloading'
              : replayStatus?.state === 'stopping'
                ? 'Stopping replay'
                : 'Replaying'}
            {replayStatus?.bag ? ` — ${replayStatus.bag}` : ''}
          </span>
        </Link>
      )}
    </div>
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
    <Link to={to} className="quick-link">
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
