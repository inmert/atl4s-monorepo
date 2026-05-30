import { useCallback, useEffect, useState } from 'react';
import { Database, Pause, Play, RefreshCw } from 'lucide-react';
import { api, ReplayStatus, RosbagInfo, RosbagMeta } from '../../lib/api';
import { formatBytes, formatDateTime, formatUptime } from '../../lib/format';

const STATE_LABEL: Record<ReplayStatus['state'], string> = {
  idle: 'Idle',
  downloading: 'Downloading',
  playing: 'Playing',
  stopping: 'Stopping',
};

export function RosbagsView() {
  const [bags, setBags] = useState<RosbagInfo[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [meta, setMeta] = useState<RosbagMeta | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadBags = useCallback(async () => {
    try {
      const r = await api.inspector.listRosbags();
      setBags(r.bags);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load rosbags');
      setBags([]);
    }
  }, []);

  useEffect(() => {
    loadBags();
  }, [loadBags]);

  // Poll replay status while on this view.
  useEffect(() => {
    let alive = true;
    const tick = () =>
      api.inspector
        .rosbagStatus()
        .then((s) => alive && setStatus(s))
        .catch(() => undefined);
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Load metadata for the selected bag.
  useEffect(() => {
    if (!selected) {
      setMeta(null);
      return;
    }
    let alive = true;
    setMeta(null);
    setMetaLoading(true);
    api.inspector
      .rosbagMetadata(selected)
      .then((m) => alive && setMeta(m))
      .catch((e) => alive && setError(e instanceof Error ? e.message : 'Failed to read metadata'))
      .finally(() => alive && setMetaLoading(false));
    return () => {
      alive = false;
    };
  }, [selected]);

  const active = status && status.state !== 'idle';
  const playingThis = status?.bag === selected && active;

  async function play(name: string) {
    setBusy(true);
    setError(null);
    try {
      await api.inspector.playRosbag(name);
      setStatus(await api.inspector.rosbagStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start playback');
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    setError(null);
    try {
      await api.inspector.stopRosbag();
      setStatus(await api.inspector.rosbagStatus());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to stop playback');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {error && <div className="banner err">{error}</div>}

      <div className="insp-body">
        <div className="insp-rail">
          <div className="insp-rail-head">
            <button className="btn btn-ghost xs" onClick={loadBags}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>
          <div className="insp-rail-list">
            {bags == null ? (
              <div className="insp-rail-empty">Loading…</div>
            ) : bags.length === 0 ? (
              <div className="insp-rail-empty">No bags in GCS.</div>
            ) : (
              bags.map((b) => (
                <div
                  key={b.name}
                  className={`insp-row${selected === b.name ? ' active' : ''}`}
                  onClick={() => setSelected(b.name)}
                >
                  <Database size={16} />
                  <span className="insp-row-meta">
                    <span className="insp-row-name">{b.name}</span>
                    <span className="insp-row-sub">
                      {formatBytes(b.size_bytes)}
                      {b.updated ? ` · ${formatDateTime(b.updated)}` : ''}
                    </span>
                  </span>
                  {status?.bag === b.name && active && <span className="badge level-ok">{STATE_LABEL[status.state]}</span>}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="insp-detail">
          {!selected ? (
            <div className="viewer-empty">Select a rosbag to see its metadata.</div>
          ) : (
            <div className="bag-detail">
              <div className="bag-detail-head">
                <h2 className="bag-title mono">{selected}</h2>
                <div className="insp-toolbar-spacer" />
                {playingThis ? (
                  <button className="btn btn-ghost" onClick={stop} disabled={busy}>
                    <Pause size={15} /> Stop
                  </button>
                ) : (
                  <button className="btn btn-primary" onClick={() => play(selected)} disabled={busy || !!active}>
                    <Play size={15} /> Play
                  </button>
                )}
              </div>

              {active && (
                <div className="bag-status">
                  <span className="status-dot level-ok" />
                  {STATE_LABEL[status!.state]}
                  {status!.bag ? ` · ${status!.bag}` : ''}
                </div>
              )}

              {metaLoading ? (
                <div className="loading-row"><span className="spinner" /></div>
              ) : meta ? (
                <>
                  <div className="bag-meta-grid">
                    <div className="bag-stat">
                      <span className="bag-stat-val">{formatUptime(meta.duration_sec)}</span>
                      <span className="bag-stat-label">Duration</span>
                    </div>
                    <div className="bag-stat">
                      <span className="bag-stat-val">{meta.message_count.toLocaleString()}</span>
                      <span className="bag-stat-label">Messages</span>
                    </div>
                    <div className="bag-stat">
                      <span className="bag-stat-val">{meta.topics.length}</span>
                      <span className="bag-stat-label">Topics</span>
                    </div>
                  </div>

                  <h3 className="bag-section">Topics</h3>
                  <div className="bag-topics">
                    <div className="bag-topic-row head">
                      <span>Topic</span><span>Type</span><span className="num">Messages</span>
                    </div>
                    {meta.topics.map((t) => (
                      <div className="bag-topic-row" key={t.name}>
                        <span className="mono">{t.name}</span>
                        <span className="mono bag-topic-type">{t.type}</span>
                        <span className="num">{t.message_count.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>

                  <p className="bag-note">
                    Play streams the bag onto the ROS bus (via rosbag-manager); view the topics in
                    Foxglove. In-inspector 3D playback is coming.
                  </p>
                </>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
