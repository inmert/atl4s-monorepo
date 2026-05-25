import { Fragment, useEffect, useRef, useState } from 'react';
import { jsonSocket, blobSocket } from '../lib/ws';

type TopicMsg = {
  topic: string;
  data: any;
  rate: number;
  ts: number;
};

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(0)}%`;
}

function fmtNum(v: number | null | undefined, digits: number, unit = ''): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v.toFixed(digits)}${unit}`;
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: 'ok' | 'warn' | 'err';
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ''}`}>{value}</div>
    </div>
  );
}

export function Live() {
  const [topics, setTopics] = useState<Record<string, TopicMsg>>({});
  const [cameraUrl, setCameraUrl] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [wsStatus, setWsStatus] = useState<'open' | 'closed'>('closed');
  const lastUrlRef = useRef<string | null>(null);

  useEffect(() => {
    const ws = jsonSocket<TopicMsg>(
      '/ws/topics',
      (msg) => setTopics((s) => ({ ...s, [msg.topic]: msg })),
      setWsStatus,
    );
    return () => ws.close();
  }, []);

  useEffect(() => {
    const ws = blobSocket('/ws/camera', (blob) => {
      const url = URL.createObjectURL(blob);
      setCameraUrl(url);
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
      lastUrlRef.current = url;
    });
    return () => {
      ws.close();
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
    };
  }, []);

  const toggle = (topic: string) => {
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(topic)) next.delete(topic);
      else next.add(topic);
      return next;
    });
  };

  const state = topics['/mavros/state']?.data;
  const battery = topics['/mavros/battery']?.data;
  const gps = topics['/mavros/global_position/global']?.data;

  return (
    <section>
      <div className="page-header">
        <h1>Live</h1>
        <div className={`ws-status ${wsStatus}`}>{wsStatus === 'open' ? '● connected' : '○ disconnected'}</div>
      </div>

      <div className="telemetry">
        <Stat label="Connected" value={state?.connected ? 'yes' : 'no'} tone={state?.connected ? 'ok' : 'err'} />
        <Stat label="Mode" value={state?.mode || '—'} />
        <Stat label="Armed" value={state?.armed ? 'YES' : 'no'} tone={state?.armed ? 'warn' : undefined} />
        <Stat label="Battery" value={fmtPct(battery?.percentage)} />
        <Stat label="Voltage" value={fmtNum(battery?.voltage, 2, ' V')} />
        <Stat label="Lat" value={fmtNum(gps?.latitude, 5)} />
        <Stat label="Lon" value={fmtNum(gps?.longitude, 5)} />
      </div>

      <div className="live-grid">
        <div className="camera-panel">
          <h2>Camera</h2>
          {cameraUrl ? (
            <img src={cameraUrl} alt="latest camera frame" className="camera-frame" />
          ) : (
            <div className="camera-empty">no frames yet</div>
          )}
        </div>

        <div className="topics-panel">
          <h2>Topics</h2>
          {Object.keys(topics).length === 0 ? (
            <p className="placeholder">Waiting for messages…</p>
          ) : (
            <table className="topics">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Rate</th>
                  <th>Last update</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(topics)
                  .sort((a, b) => a.topic.localeCompare(b.topic))
                  .map((t) => (
                    <Fragment key={t.topic}>
                      <tr className="row-clickable" onClick={() => toggle(t.topic)}>
                        <td>
                          <span className="caret">{expanded.has(t.topic) ? '▾' : '▸'}</span>
                          {t.topic}
                        </td>
                        <td>{t.rate.toFixed(1)} Hz</td>
                        <td>{new Date(t.ts * 1000).toLocaleTimeString()}</td>
                      </tr>
                      {expanded.has(t.topic) && (
                        <tr className="data-row">
                          <td colSpan={3}>
                            <pre>{JSON.stringify(t.data, null, 2)}</pre>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </section>
  );
}
