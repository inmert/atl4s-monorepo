import { useEffect, useState, type FormEvent } from 'react';
import { api, type LocalBag, type RecordStatus } from '../lib/api';
import { formatBytes, formatDate } from '../lib/format';

const POLL_MS = 2000;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export function Record() {
  const [status, setStatus] = useState<RecordStatus | null>(null);
  const [locals, setLocals] = useState<LocalBag[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [topicsText, setTopicsText] = useState('');
  const [duration, setDuration] = useState('');

  const poll = async () => {
    try {
      const [s, l] = await Promise.all([api.recordStatus(), api.listLocal()]);
      setStatus(s);
      setLocals(l);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    poll();
    const id = window.setInterval(poll, POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  const onStart = async (e: FormEvent) => {
    e.preventDefault();
    const body: { name?: string; topics?: string[]; duration?: number } = {};
    if (name.trim()) body.name = name.trim();
    const topics = topicsText
      .split(/[\s,]+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 0);
    if (topics.length) body.topics = topics;
    if (duration.trim()) {
      const d = Number(duration);
      if (!Number.isNaN(d) && d > 0) body.duration = d;
    }
    try {
      const s = await api.recordStart(body);
      setStatus(s);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onStop = async () => {
    try {
      const s = await api.recordStop();
      setStatus(s);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const onForceUpload = async (n: string) => {
    try {
      await api.forceUpload(n);
      await poll();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  const recording = status?.state === 'recording';

  return (
    <section>
      <div className="page-header">
        <h1>Record</h1>
        <button className="ghost" onClick={poll}>Refresh</button>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="status-row">
        <Stat label="State" value={status?.state || '—'} />
        <Stat label="Name" value={status?.name || '—'} />
        <Stat label="Started" value={status?.started_at ? formatDate(status.started_at) : '—'} />
        <Stat label="Topics" value={status?.topics ? String(status.topics.length) : '—'} />
      </div>

      <form className="form-card" onSubmit={onStart}>
        <h2>Start a recording</h2>
        <label>
          <span>Bag name</span>
          <input
            type="text"
            placeholder="auto-generated if blank"
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={recording}
          />
        </label>
        <label>
          <span>Topics (space- or newline-separated; blank = server default)</span>
          <textarea
            rows={3}
            placeholder="/mavros/state /mavros/battery /camera/image …"
            value={topicsText}
            onChange={(e) => setTopicsText(e.target.value)}
            disabled={recording}
          />
        </label>
        <label>
          <span>Duration in seconds (blank = manual stop)</span>
          <input
            type="number"
            min={1}
            placeholder="30"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            disabled={recording}
          />
        </label>
        <div className="form-actions">
          <button type="submit" disabled={recording}>Start</button>
          <button type="button" className="danger" disabled={!recording} onClick={onStop}>
            Stop
          </button>
        </div>
      </form>

      <h2 className="section-h2">Local bags</h2>
      {locals === null ? (
        <p className="placeholder">Loading…</p>
      ) : locals.length === 0 ? (
        <p className="placeholder">No local bags. Start a recording above.</p>
      ) : (
        <table className="bags">
          <thead>
            <tr>
              <th>Name</th>
              <th>Size</th>
              <th>Files</th>
              <th>Last write</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {locals.map((b) => (
              <tr key={b.name}>
                <td>{b.name}</td>
                <td>{formatBytes(b.size_bytes)}</td>
                <td>{b.files}</td>
                <td>{formatDate(b.mtime)}</td>
                <td>
                  {b.uploaded ? (
                    <span className="badge ok">uploaded</span>
                  ) : b.in_flight ? (
                    <span className="badge warn">uploading</span>
                  ) : (
                    <span className="badge">pending</span>
                  )}
                </td>
                <td>
                  {!b.uploaded && !b.in_flight && (
                    <button onClick={() => onForceUpload(b.name)}>Upload now</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
