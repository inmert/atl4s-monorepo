// Phase 1 stub. The registry is hardcoded here; Phase 2 moves it to a backend
// YAML and replaces the placeholder right pane with real per-robot telemetry,
// map, and camera. Legacy /live and /map routes stay accessible so nothing is
// lost between phases.

import { Link, useParams } from 'react-router-dom';
import { Bot, MonitorPlay, Plane } from 'lucide-react';
import { useTopic } from '../lib/topics';
import { Badge, Card, EmptyState, PageHeader, StatusDot } from '../lib/components';

type Robot = {
  id: string;
  name: string;
  kind: string;
  icon: typeof Bot;
  online: boolean;
  summary: string;
  legacyHint?: string;
};

function useRobots(): Robot[] {
  const state = useTopic('/mavros/state')?.data;
  return [
    {
      id: 'gazebo-drone',
      name: 'Gazebo Drone',
      kind: 'Simulator',
      icon: MonitorPlay,
      online: Boolean(state?.connected),
      summary: state?.connected
        ? `${state?.mode || '—'} · ${state?.armed ? 'ARMED' : 'disarmed'}`
        : 'no MAVROS link',
      legacyHint: 'live',
    },
    {
      id: 'orin-drone',
      name: 'Orin Drone',
      kind: 'Drone',
      icon: Plane,
      online: false,
      summary: 'awaiting Orin integration',
    },
  ];
}

export function Robots() {
  const { id } = useParams();
  const robots = useRobots();
  const selected = id ? robots.find((r) => r.id === id) : undefined;

  if (selected) {
    return <RobotDetail robot={selected} />;
  }
  return <RobotList robots={robots} />;
}

function RobotList({ robots }: { robots: Robot[] }) {
  return (
    <section>
      <PageHeader
        title="Robots"
        subtitle="Connected drones, rovers, and simulators."
      />

      <div className="grid grid-2">
        {robots.map((r) => (
          <Link
            key={r.id}
            to={`/robots/${r.id}`}
            style={{
              display: 'flex',
              gap: 14,
              padding: 18,
              borderRadius: 'var(--radius-lg)',
              background: 'var(--surface)',
              boxShadow: 'var(--shadow-1)',
              color: 'var(--label)',
              textDecoration: 'none',
              transition: 'transform 0.12s var(--ease)',
            }}
          >
            <r.icon size={28} style={{ color: 'var(--accent)', flex: 'none', marginTop: 2 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="row space">
                <div style={{ fontWeight: 600, fontSize: 15 }}>{r.name}</div>
                <Badge tone={r.online ? 'ok' : undefined}>
                  <StatusDot tone={r.online ? 'ok' : undefined} />
                  {r.online ? 'Online' : 'Offline'}
                </Badge>
              </div>
              <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                {r.kind}
              </div>
              <div style={{ fontSize: 13, marginTop: 10, color: 'var(--label-2)' }}>
                {r.summary}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}

function RobotDetail({ robot }: { robot: Robot }) {
  const Icon = robot.icon;
  return (
    <section>
      <PageHeader
        title={
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
            <Icon size={26} style={{ color: 'var(--accent)' }} />
            {robot.name}
          </span>
        }
        subtitle={`${robot.kind} · ${robot.summary}`}
        right={
          <>
            <Badge tone={robot.online ? 'ok' : undefined}>
              <StatusDot tone={robot.online ? 'ok' : undefined} />
              {robot.online ? 'Online' : 'Offline'}
            </Badge>
            <Link to="/robots" className="dim">← All robots</Link>
          </>
        }
      />

      <Card title="Telemetry">
        <EmptyState icon={Icon} title="Per-robot telemetry comes in Phase 2">
          The robot registry, telemetry, map, and camera will be wired up next.{' '}
          {robot.legacyHint === 'live' ? (
            <>
              In the meantime, the legacy{' '}
              <Link to="/live">Live</Link> and <Link to="/map">Map</Link> views still work
              for the Gazebo Drone.
            </>
          ) : (
            <>This robot will appear here once it's integrated.</>
          )}
        </EmptyState>
      </Card>
    </section>
  );
}
