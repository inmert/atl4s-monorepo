// Full ROS topic graph: every topic on the bus from the rclpy node's view,
// with type, pub/sub counts + per-endpoint node names and QoS. Click a row
// to open the inspect drawer — opens /ws/ros/sample/{topic}, streams parsed
// JSON messages until closed. Subscriptions are persistent on the backend
// (created on first sample, kept alive across clients).

import { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Search, Share2 } from 'lucide-react';
import { api, type RosTopic } from '../lib/api';
import { jsonSocket } from '../lib/ws';
import { Badge, Card, EmptyState, PageHeader } from '../lib/components';

const POLL_MS = 5000;

export function Ros() {
  const [topics, setTopics] = useState<RosTopic[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [collapsedNs, setCollapsedNs] = useState<Set<string>>(new Set());

  const refresh = async () => {
    try {
      setTopics(await api.listRosTopics());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  const filtered = useMemo(() => {
    if (!topics) return null;
    const needle = filter.trim().toLowerCase();
    if (!needle) return topics;
    return topics.filter(
      (t) =>
        t.name.toLowerCase().includes(needle) ||
        t.types.some((ty) => ty.toLowerCase().includes(needle)),
    );
  }, [topics, filter]);

  const grouped = useMemo(() => {
    if (!filtered) return null;
    const out = new Map<string, RosTopic[]>();
    for (const t of filtered) {
      const parts = t.name.split('/').filter(Boolean);
      const ns = parts.length > 1 ? `/${parts[0]}` : '/';
      const bucket = out.get(ns) || [];
      bucket.push(t);
      out.set(ns, bucket);
    }
    return out;
  }, [filtered]);

  const toggleNs = (ns: string) => {
    setCollapsedNs((prev) => {
      const next = new Set(prev);
      if (next.has(ns)) next.delete(ns);
      else next.add(ns);
      return next;
    });
  };

  return (
    <section>
      <PageHeader
        title="ROS"
        subtitle={
          topics ? `${topics.length} topics on the bus` : 'Reading graph…'
        }
        right={
          <>
            <div className="ros-search">
              <Search size={14} />
              <input
                type="text"
                placeholder="Filter topics or types"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
            </div>
            <button className="ghost" onClick={refresh} title="Refresh graph">
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      {error && <p className="error">{error}</p>}

      {grouped === null ? (
        <p className="placeholder">Loading…</p>
      ) : grouped.size === 0 ? (
        <EmptyState icon={Share2} title="No topics match">
          {topics?.length === 0
            ? 'No topics on the bus. Make sure MAVROS / gz-bridge / commander are up.'
            : 'Try a different filter.'}
        </EmptyState>
      ) : (
        <div className="stack">
          {Array.from(grouped.entries()).map(([ns, ts]) => {
            const collapsed = collapsedNs.has(ns);
            return (
              <Card
                key={ns}
                className="flush"
                title={
                  <button
                    className="link ns-toggle"
                    onClick={() => toggleNs(ns)}
                  >
                    <span className="caret">{collapsed ? '▸' : '▾'}</span>
                    <span className="mono">{ns}</span>
                    <span className="dim" style={{ marginLeft: 8, fontWeight: 500 }}>
                      {ts.length}
                    </span>
                  </button>
                }
              >
                {!collapsed && (
                  <table className="topics">
                    <thead>
                      <tr>
                        <th>Topic</th>
                        <th>Type</th>
                        <th style={{ textAlign: 'right' }}>Pubs</th>
                        <th style={{ textAlign: 'right' }}>Subs</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ts.map((t) => (
                        <TopicRow
                          key={t.name}
                          topic={t}
                          expanded={expanded === t.name}
                          onToggle={() =>
                            setExpanded((cur) => (cur === t.name ? null : t.name))
                          }
                        />
                      ))}
                    </tbody>
                  </table>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </section>
  );
}

function TopicRow({
  topic,
  expanded,
  onToggle,
}: {
  topic: RosTopic;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr className="row-clickable" onClick={onToggle}>
        <td>
          <span className="caret">{expanded ? '▾' : '▸'}</span>
          {topic.name}
        </td>
        <td className="dim">{topic.types.join(', ') || '—'}</td>
        <td style={{ textAlign: 'right' }}>{topic.pub_count}</td>
        <td style={{ textAlign: 'right' }}>{topic.sub_count}</td>
      </tr>
      {expanded && (
        <tr className="data-row">
          <td colSpan={4}>
            <TopicInspector topic={topic} />
          </td>
        </tr>
      )}
    </>
  );
}

function EndpointList({
  label,
  endpoints,
}: {
  label: string;
  endpoints: { node: string; qos: string }[];
}) {
  if (endpoints.length === 0) {
    return (
      <div className="endpoint-block">
        <div className="endpoint-label">{label}</div>
        <div className="dim mono" style={{ fontSize: 12 }}>—</div>
      </div>
    );
  }
  return (
    <div className="endpoint-block">
      <div className="endpoint-label">{label}</div>
      {endpoints.map((ep, i) => (
        <div key={`${ep.node}-${i}`} className="endpoint-row">
          <span className="mono">{ep.node}</span>
          <Badge>{ep.qos}</Badge>
        </div>
      ))}
    </div>
  );
}

type SamplePayload = { topic: string; data: unknown; rate: number; ts: number };

function TopicInspector({ topic }: { topic: RosTopic }) {
  const [sample, setSample] = useState<SamplePayload | null>(null);
  const [status, setStatus] = useState<'open' | 'closed'>('closed');

  useEffect(() => {
    setSample(null);
    setStatus('closed');
    const ws = jsonSocket<SamplePayload>(
      `/ws/ros/sample${topic.name}`,
      (msg) => setSample(msg),
      setStatus,
    );
    return () => ws.close();
  }, [topic.name]);

  return (
    <div className="inspector">
      <div className="inspector-meta">
        <EndpointList label="Publishers" endpoints={topic.pubs} />
        <EndpointList label="Subscribers" endpoints={topic.subs} />
      </div>

      <div className="inspector-sample">
        <div className="row space" style={{ marginBottom: 6 }}>
          <span className="endpoint-label">Latest message</span>
          <span className={`ws-status ${status}`}>
            {status === 'open' ? '● sampling' : '○ waiting'}
            {sample && status === 'open' && ` · ${sample.rate.toFixed(1)} Hz`}
          </span>
        </div>
        {sample ? (
          <pre className="sample-pre">{JSON.stringify(sample.data, null, 2)}</pre>
        ) : (
          <p className="dim" style={{ fontSize: 12 }}>
            Waiting for first message… (no publishers, low-rate topic, or unresolvable type)
          </p>
        )}
      </div>
    </div>
  );
}
