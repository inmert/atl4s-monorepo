import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Bag, type ReplayStatus } from '../lib/api';
import { foxgloveStudioUrl } from '../lib/foxglove';
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

export function Replay() {
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [bags, setBags] = useState<Bag[] | null>(null);
  const [selected, setSelected] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const pollStatus = async () => {
    try {
      setStatus(await api.replayStatus());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const refreshBags = async () => {
    try {
      const bs = await api.listBags();
      setBags(bs);
      if (!selected && bs.length) setSelected(bs[0].name);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    pollStatus();
    refreshBags();
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

  const idle = !status || status.state === 'idle';

  return (
    <section>
      <div className="page-header">
        <h1>Replay</h1>
        <button className="ghost" onClick={() => { pollStatus(); refreshBags(); }}>Refresh</button>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="status-row">
        <Stat label="State" value={status?.state || '—'} />
        <Stat label="Bag" value={status?.bag || '—'} />
        <Stat label="Started" value={status?.started_at ? formatDate(status.started_at) : '—'} />
      </div>

      <div className="form-card">
        <h2>Start a replay</h2>
        <label>
          <span>Bag from GCS</span>
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            disabled={!idle}
          >
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
          <button onClick={onStart} disabled={!idle || !selected}>Start</button>
          <button className="danger" onClick={onStop} disabled={idle}>Stop</button>
        </div>
        <p className="hint">
          Replays publish recorded topics back onto the DDS bus with their original QoS.
          Open <Link to="/live">Live</Link> for the in-app view, or{' '}
          <a href={foxgloveStudioUrl()} target="_blank" rel="noreferrer">Foxglove Studio ↗</a>{' '}
          for 3D inspection.
        </p>
      </div>
    </section>
  );
}
