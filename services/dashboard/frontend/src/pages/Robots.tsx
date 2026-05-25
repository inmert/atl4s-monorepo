// Robot registry list view. Robots come from /api/robots (loaded once at
// mount); online status is derived in real time from the shared /ws/topics
// stream via lib/robots.ts.

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Robot } from '../lib/api';
import { useTopics } from '../lib/topics';
import { iconFor, isOnline, summarize } from '../lib/robots';
import { Badge, EmptyState, PageHeader, StatusDot } from '../lib/components';
import { Bot } from 'lucide-react';

export function Robots() {
  const [robots, setRobots] = useState<Robot[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { topics } = useTopics();

  useEffect(() => {
    api.listRobots().then(setRobots).catch((e) => setError(e.message));
  }, []);

  return (
    <section>
      <PageHeader
        title="Robots"
        subtitle="Drones, rovers, and simulators connected to the pipeline."
      />

      {error && <p className="error">{error}</p>}

      {robots === null ? (
        <p className="placeholder">Loading…</p>
      ) : robots.length === 0 ? (
        <EmptyState icon={Bot} title="No robots configured">
          Edit <code>services/dashboard/config/robots.yaml</code> and{' '}
          <code>docker compose restart dashboard</code> to register one.
        </EmptyState>
      ) : (
        <div className="grid grid-2">
          {robots.map((r) => {
            const Icon = iconFor(r.icon);
            const online = isOnline(r, topics);
            return (
              <Link
                key={r.id}
                to={`/robots/${r.id}`}
                className="robot-card"
              >
                <Icon size={28} className="robot-card-icon" />
                <div className="robot-card-body">
                  <div className="row space">
                    <div className="robot-card-name">{r.name}</div>
                    <Badge tone={online ? 'ok' : undefined}>
                      <StatusDot tone={online ? 'ok' : undefined} />
                      {online ? 'Online' : 'Offline'}
                    </Badge>
                  </div>
                  <div className="dim robot-card-kind">{r.kind}</div>
                  <div className="robot-card-summary">{summarize(r, topics)}</div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
