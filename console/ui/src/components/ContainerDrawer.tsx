import { ReactNode, useCallback, useEffect, useState } from 'react';
import { Play, RotateCw, Square } from 'lucide-react';
import { api, ContainerAction, ContainerDetail, StatsFrame, wsUrl } from '../lib/api';
import { displayName, formatBytes, formatDateTime, formatUptime } from '../lib/format';
import { Drawer } from './Drawer';
import { StatusBadge } from './StatusBadge';
import { LiveLogs } from './LiveLogs';
import { EnvEditor } from './EnvEditor';

// `gen` bumps whenever the container is acted on or recreated (env edit), so
// the stats socket reconnects to the new container instead of the dead one.
function useLiveStats(name: string, running: boolean, gen: number): StatsFrame | null {
  const [frame, setFrame] = useState<StatsFrame | null>(null);
  useEffect(() => {
    setFrame(null);
    if (!running) return;
    const ws = new WebSocket(wsUrl(`/ws/containers/${encodeURIComponent(name)}/stats`));
    ws.onmessage = (e) => {
      try {
        setFrame(JSON.parse(e.data as string));
      } catch {
        /* ignore malformed frame */
      }
    };
    return () => ws.close();
  }, [name, running, gen]);
  return frame;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{children}</span>
    </div>
  );
}

function Meter({ label, percent, detail }: { label: string; percent: number; detail: string }) {
  const level = percent >= 90 ? 'err' : percent >= 70 ? 'warn' : 'ok';
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <span className="mono">{detail}</span>
      </div>
      <div className="meter-track">
        <div className={`meter-fill level-${level}`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
    </div>
  );
}

export function ContainerDrawer({
  name,
  onClose,
  onChanged,
}: {
  name: string;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<ContainerDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<ContainerAction | null>(null);
  const [gen, setGen] = useState(0);

  const refresh = useCallback(async () => {
    try {
      setDetail(await api.getContainer(name));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load container');
    }
  }, [name]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const running = detail?.state === 'running';
  const stats = useLiveStats(name, !!running, gen);

  async function act(action: ContainerAction) {
    setBusy(action);
    setError(null);
    try {
      await api.containerAction(name, action);
      await refresh();
      setGen((g) => g + 1);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(null);
    }
  }

  function onEnvSaved(updated: ContainerDetail) {
    setDetail(updated);
    setGen((g) => g + 1);
    onChanged();
  }

  const actions = (
    <div className="drawer-actions">
      <button className="btn btn-ghost xs" disabled={!!busy} onClick={() => act('restart')}>
        <RotateCw size={14} /> Restart
      </button>
      {running ? (
        <button className="btn btn-ghost xs" disabled={!!busy} onClick={() => act('stop')}>
          <Square size={14} /> Stop
        </button>
      ) : (
        <button className="btn btn-ghost xs" disabled={!!busy} onClick={() => act('start')}>
          <Play size={14} /> Start
        </button>
      )}
    </div>
  );

  return (
    <Drawer
      open
      onClose={onClose}
      title={<span className="mono">{displayName(name)}</span>}
      subtitle={detail && <StatusBadge level={detail.level} text={detail.health ?? detail.state} />}
      actions={actions}
    >
      {error && <div className="banner err">{error}</div>}

      {detail && (
        <>
          <section className="drawer-section">
            <h3 className="drawer-section-title">Resources</h3>
            {running ? (
              <div className="meters">
                <Meter
                  label="CPU"
                  percent={stats?.cpu_percent ?? 0}
                  detail={stats ? `${stats.cpu_percent}%` : '…'}
                />
                <Meter
                  label="Memory"
                  percent={stats?.mem_percent ?? 0}
                  detail={
                    stats
                      ? `${formatBytes(stats.mem_bytes)} / ${formatBytes(stats.mem_limit)}`
                      : '…'
                  }
                />
              </div>
            ) : (
              <p className="muted">Not running — no live resource stats.</p>
            )}
          </section>

          <section className="drawer-section">
            <h3 className="drawer-section-title">Details</h3>
            <div className="kv">
              <Row label="Name"><span className="mono">{detail.name}</span></Row>
              <Row label="Container ID"><span className="mono">{detail.id}</span></Row>
              {detail.service && <Row label="Compose service">{detail.service}</Row>}
              <Row label="Image"><span className="mono">{detail.image ?? '—'}</span></Row>
              <Row label="State">{detail.state}{detail.health ? ` · ${detail.health}` : ''}</Row>
              <Row label="Uptime">{formatUptime(detail.uptime_sec)}</Row>
              <Row label="Restarts">{detail.restart_count}</Row>
              <Row label="Restart policy">{detail.restart_policy ?? '—'}</Row>
              <Row label="Network">{detail.network_mode ?? '—'}</Row>
              <Row label="Created">{formatDateTime(detail.created)}</Row>
              <Row label="Started">{formatDateTime(detail.started_at)}</Row>
              {detail.exit_code != null && detail.state !== 'running' && (
                <Row label="Exit code">{detail.exit_code}</Row>
              )}
              {detail.state_error && <Row label="Error">{detail.state_error}</Row>}
              {detail.command && <Row label="Command"><span className="mono wrap">{detail.command}</span></Row>}
              {detail.ports.length > 0 && (
                <Row label="Ports"><span className="mono">{detail.ports.join(', ')}</span></Row>
              )}
            </div>
          </section>

          <EnvEditor detail={detail} onSaved={onEnvSaved} />

          {detail.mounts.length > 0 && (
            <section className="drawer-section">
              <h3 className="drawer-section-title">Mounts</h3>
              <div className="mounts">
                {detail.mounts.map((m, i) => (
                  <div className="mount" key={i}>
                    <span className="mono">{m.source ?? '—'}</span>
                    <span className="mount-arrow">→</span>
                    <span className="mono">{m.destination ?? '—'}</span>
                    <span className={`tag ${m.rw ? '' : 'tag-ro'}`}>{m.rw ? 'rw' : 'ro'}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}

      <section className="drawer-section logs-section">
        <h3 className="drawer-section-title">Logs</h3>
        <LiveLogs key={`${name}-${gen}`} name={name} />
      </section>
    </Drawer>
  );
}
