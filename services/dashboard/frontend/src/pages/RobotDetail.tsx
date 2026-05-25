// Per-robot detail: telemetry stat strip, Leaflet map, JPEG camera viewport,
// Foxglove deep link. Topic names come from the registry — this component
// doesn't know about /mavros/* specifically.

import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { ExternalLink } from 'lucide-react';
import { api, type Robot } from '../lib/api';
import { useTopic, useTopics } from '../lib/topics';
import { iconFor, isFresh, isOnline, summarize } from '../lib/robots';
import { foxgloveStudioUrl } from '../lib/foxglove';
import { blobSocket } from '../lib/ws';
import { Badge, Card, EmptyState, PageHeader, StatTile, StatusDot } from '../lib/components';

const TRAIL_MAX_POINTS = 1000;

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${(v * 100).toFixed(0)}%`;
}

function fmtNum(v: number | null | undefined, digits: number, unit = ''): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v.toFixed(digits)}${unit}`;
}

export function RobotDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [robot, setRobot] = useState<Robot | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api
      .getRobot(id)
      .then(setRobot)
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) {
    return (
      <section>
        <PageHeader
          title="Robot not found"
          right={<Link to="/robots" className="dim">← All robots</Link>}
        />
        <p className="error">{error}</p>
        <button className="ghost" onClick={() => navigate('/robots')}>Back to Robots</button>
      </section>
    );
  }

  if (!robot) {
    return (
      <section>
        <PageHeader title="Loading…" />
      </section>
    );
  }

  return <RobotView robot={robot} />;
}

function RobotView({ robot }: { robot: Robot }) {
  const { topics } = useTopics();
  const Icon = iconFor(robot.icon);
  const online = isOnline(robot, topics);

  const stateTopic = robot.telemetry.state ? topics[robot.telemetry.state] : undefined;
  const batteryTopic = robot.telemetry.battery ? topics[robot.telemetry.battery] : undefined;
  const gpsTopic = robot.telemetry.gps ? topics[robot.telemetry.gps] : undefined;

  const state = stateTopic?.data;
  const battery = batteryTopic?.data;
  const gps = gpsTopic?.data;

  return (
    <section>
      <PageHeader
        title={
          <span className="robot-header">
            <Icon size={26} style={{ color: 'var(--accent)' }} />
            {robot.name}
          </span>
        }
        subtitle={
          <span style={{ textTransform: 'capitalize' }}>
            {robot.kind} · {summarize(robot, topics)}
          </span>
        }
        right={
          <>
            <a
              className="foxglove-link"
              href={foxgloveStudioUrl()}
              target="_blank"
              rel="noreferrer"
            >
              Foxglove Studio <ExternalLink size={12} style={{ marginLeft: 4 }} />
            </a>
            <Badge tone={online ? 'ok' : undefined}>
              <StatusDot tone={online ? 'ok' : undefined} />
              {online ? 'Online' : 'Offline'}
            </Badge>
            <Link to="/robots" className="dim">← All robots</Link>
          </>
        }
      />

      <div className="telemetry">
        <StatTile
          label="Connected"
          value={state?.connected ? 'yes' : 'no'}
          tone={state?.connected ? 'ok' : 'err'}
        />
        <StatTile label="Mode" value={state?.mode || '—'} />
        <StatTile
          label="Armed"
          value={state?.armed ? 'YES' : 'no'}
          tone={state?.armed ? 'warn' : undefined}
        />
        <StatTile label="Battery" value={fmtPct(battery?.percentage)} />
        <StatTile label="Voltage" value={fmtNum(battery?.voltage, 2, ' V')} />
        <StatTile label="Lat" value={fmtNum(gps?.latitude, 5)} />
        <StatTile label="Lon" value={fmtNum(gps?.longitude, 5)} />
      </div>

      <div className="robot-grid">
        <div className="robot-pane-stack">
          <Card title="Map">
            {robot.telemetry.gps ? (
              <RobotMap topic={robot.telemetry.gps} />
            ) : (
              <p className="placeholder">No GPS topic configured.</p>
            )}
          </Card>

          <Card title="Telemetry topics">
            <TopicTable robot={robot} />
          </Card>
        </div>

        <div className="robot-pane-stack">
          <Card title="Camera">
            {robot.telemetry.camera ? (
              <RobotCamera robotId={robot.id} topic={robot.telemetry.camera} />
            ) : (
              <p className="placeholder">No camera topic configured.</p>
            )}
          </Card>
        </div>
      </div>
    </section>
  );
}

function RobotMap({ topic }: { topic: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.CircleMarker | null>(null);
  const trailRef = useRef<L.Polyline | null>(null);
  const trailPoints = useRef<[number, number][]>([]);
  const centered = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = L.map(containerRef.current).setView([0, 0], 2);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      trailRef.current = null;
      trailPoints.current = [];
      centered.current = false;
    };
  }, []);

  const gps = useTopic(topic);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !gps?.data) return;
    const { latitude, longitude } = gps.data;
    if (typeof latitude !== 'number' || typeof longitude !== 'number') return;
    if (Math.abs(latitude) < 1e-4 && Math.abs(longitude) < 1e-4) return;

    const pt: [number, number] = [latitude, longitude];
    trailPoints.current.push(pt);
    if (trailPoints.current.length > TRAIL_MAX_POINTS) trailPoints.current.shift();

    if (!markerRef.current) {
      markerRef.current = L.circleMarker(pt, {
        radius: 7,
        color: '#0a84ff',
        fillColor: '#0a84ff',
        fillOpacity: 0.85,
        weight: 2,
      }).addTo(map);
    } else {
      markerRef.current.setLatLng(pt);
    }

    if (!trailRef.current) {
      trailRef.current = L.polyline(trailPoints.current, {
        color: '#0a84ff',
        weight: 2,
        opacity: 0.6,
      }).addTo(map);
    } else {
      trailRef.current.setLatLngs(trailPoints.current);
    }

    if (!centered.current) {
      map.setView(pt, 18);
      centered.current = true;
    }
  }, [gps]);

  return <div className="map robot-map" ref={containerRef} />;
}

function RobotCamera({ robotId, topic }: { robotId: string; topic: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const lastUrlRef = useRef<string | null>(null);
  const topicMsg = useTopic(topic);

  useEffect(() => {
    const ws = blobSocket(`/ws/camera/${encodeURIComponent(robotId)}`, (blob) => {
      const u = URL.createObjectURL(blob);
      setUrl(u);
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
      lastUrlRef.current = u;
    });
    return () => {
      ws.close();
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
    };
  }, [robotId]);

  return (
    <>
      {url ? (
        <img src={url} alt="latest camera frame" className="camera-frame" />
      ) : (
        <div className="camera-empty">
          no frames yet on <code>{topic}</code>
        </div>
      )}
      {topicMsg && (
        <div className="hint" style={{ marginTop: 8 }}>
          <code>{topic}</code> · {topicMsg.rate.toFixed(1)} Hz
        </div>
      )}
    </>
  );
}

function TopicTable({ robot }: { robot: Robot }) {
  const { topics } = useTopics();
  const entries = Object.entries(robot.telemetry);
  if (entries.length === 0) {
    return (
      <EmptyState title="No telemetry topics configured">
        Add topics to <code>services/dashboard/config/robots.yaml</code> for this robot.
      </EmptyState>
    );
  }
  return (
    <table className="topics">
      <thead>
        <tr>
          <th>Key</th>
          <th>Topic</th>
          <th>Rate</th>
          <th>Last update</th>
        </tr>
      </thead>
      <tbody>
        {entries.map(([key, topic]) => {
          const msg = topic ? topics[topic] : undefined;
          const fresh = isFresh(msg);
          return (
            <tr key={key}>
              <td>{key}</td>
              <td>{topic}</td>
              <td className={fresh ? '' : 'dim'}>{msg ? `${msg.rate.toFixed(1)} Hz` : '—'}</td>
              <td className="dim">
                {msg ? new Date(msg.ts * 1000).toLocaleTimeString() : '—'}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
