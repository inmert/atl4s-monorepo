// Phase 1 stub. Today's topic bridge only subscribes to a curated set; Phase 3
// adds a full topic graph endpoint (publishers / subscribers / QoS) plus an
// on-demand sampling WebSocket and renders a namespace-grouped tree here.

import { Share2 } from 'lucide-react';
import { useTopics } from '../lib/topics';
import { Card, EmptyState, PageHeader } from '../lib/components';

function groupByNamespace(topics: string[]): Record<string, string[]> {
  const groups: Record<string, string[]> = {};
  for (const t of topics) {
    const parts = t.split('/').filter(Boolean);
    const ns = parts.length > 1 ? `/${parts[0]}` : '/';
    (groups[ns] ||= []).push(t);
  }
  return groups;
}

export function Ros() {
  const { topics } = useTopics();
  const names = Object.keys(topics).sort();
  const grouped = groupByNamespace(names);

  return (
    <section>
      <PageHeader
        title="ROS"
        subtitle="Topics on the bus, organised by namespace."
      />

      {names.length === 0 ? (
        <EmptyState icon={Share2} title="No topics yet">
          The dashboard is connected but hasn't received any messages on the curated
          topic set. Make sure MAVROS and the gz-bridge containers are running.
        </EmptyState>
      ) : (
        <div className="stack">
          <p className="hint">
            Phase 1 preview — only topics the dashboard subscribes to are listed.
            Phase 3 will expand this to the full ROS graph (every publisher /
            subscriber on the bus, with QoS and on-demand sampling).
          </p>

          {Object.entries(grouped).map(([ns, ts]) => (
            <Card key={ns} title={<span className="mono">{ns}</span>} className="flush">
              <table className="topics">
                <thead>
                  <tr>
                    <th>Topic</th>
                    <th>Rate</th>
                    <th>Last update</th>
                  </tr>
                </thead>
                <tbody>
                  {ts.map((t) => {
                    const msg = topics[t];
                    return (
                      <tr key={t}>
                        <td>{t}</td>
                        <td>{msg.rate.toFixed(1)} Hz</td>
                        <td className="dim">
                          {new Date(msg.ts * 1000).toLocaleTimeString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
