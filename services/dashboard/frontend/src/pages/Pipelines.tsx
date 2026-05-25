import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Bag, type ReplayStatus } from '../lib/api';
import { useTopics } from '../lib/topics';
import { formatDate } from '../lib/format';

const POLL_MS = 2000;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export function Pipelines() {
  const { topics } = useTopics();
  const [bags, setBags] = useState<Bag[] | null>(null);
  const [selected, setSelected] = useState<string>('');
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshBags = async () => {
    try {
      const bs = await api.listBags();
      setBags(bs);
      if (!selected && bs.length) setSelected(bs[0].name);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const pollStatus = async () => {
    try {
      setStatus(await api.replayStatus());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    refreshBags();
    pollStatus();
    const id = window.setInterval(pollStatus, POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  const onStart = async () => {
    if (!selected) return;
    try {
      const s = await api.replayStart(selected);
      setStatus(s);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onStop = async () => {
    try {
      const s = await api.replayStop();
      setStatus(s);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const perceptionTopics = Object.values(topics)
    .filter((t) => t.topic.startsWith('/perception/') || t.topic.startsWith('/fusion/'))
    .sort((a, b) => a.topic.localeCompare(b.topic));

  const idle = !status || status.state === 'idle';

  return (
    <section>
      <div className="page-header">
        <h1>Pipelines</h1>
        <button className="ghost" onClick={() => { refreshBags(); pollStatus(); }}>Refresh</button>
      </div>

      {error && <p className="error">{error}</p>}

      <p className="hint">
        Run a recorded bag through the perception stack. Replay publishes the bag's topics
        onto the DDS bus; any running <code>perception-*</code> services consume them and emit
        outputs under <code>/perception/*</code> or <code>/fusion/*</code>, which appear below
        as they're discovered.
      </p>

      <div className="form-card">
        <h2>Replay against the pipeline</h2>
        <label>
          <span>Bag from GCS</span>
          <select value={selected} onChange={(e) => setSelected(e.target.value)} disabled={!idle}>
            {bags === null ? (
              <option>Loading…</option>
            ) : bags.length === 0 ? (
              <option>No bags in GCS</option>
            ) : (
              bags.map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name} — {b.size_mib} MiB
                </option>
              ))
            )}
          </select>
        </label>
        <div className="form-actions">
          <button onClick={onStart} disabled={!idle || !selected}>Start replay</button>
          <button className="danger" onClick={onStop} disabled={idle}>Stop</button>
        </div>
        <p className="hint">
          See <Link to="/live">Live</Link> for the camera viewport + raw mavros stream during replay.
        </p>
      </div>

      <div className="status-row" style={{ marginTop: 20 }}>
        <Stat label="State" value={status?.state || '—'} />
        <Stat label="Bag" value={status?.bag || '—'} />
        <Stat label="Started" value={status?.started_at ? formatDate(status.started_at) : '—'} />
      </div>

      <h2 className="section-h2">Perception outputs</h2>
      {perceptionTopics.length === 0 ? (
        <p className="placeholder">
          No <code>/perception/*</code> or <code>/fusion/*</code> topics observed.
          Start a perception service (e.g. <code>perception-detector</code>) and replay
          a bag to see outputs here. The bridge auto-discovers new topics every 5s.
        </p>
      ) : (
        <table className="bags">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Rate</th>
              <th>Last update</th>
            </tr>
          </thead>
          <tbody>
            {perceptionTopics.map((t) => (
              <tr key={t.topic}>
                <td>{t.topic}</td>
                <td>{t.rate.toFixed(1)} Hz</td>
                <td>{new Date(t.ts * 1000).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
