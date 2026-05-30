import { useCallback, useEffect, useState } from 'react';
import { Box, Play, RotateCw, Square } from 'lucide-react';
import { api, ContainerAction, ContainerSummary } from '../lib/api';
import { displayName, formatUptime } from '../lib/format';
import { StatusBadge } from '../components/StatusBadge';
import { Spinner } from '../components/Spinner';
import { ContainerDrawer } from '../components/ContainerDrawer';

const REFRESH_MS = 4000;

export function Containers() {
  const [list, setList] = useState<ContainerSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, ContainerAction | undefined>>({});

  const load = useCallback(async () => {
    try {
      const r = await api.listContainers();
      setList(r.containers);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load containers');
      setList([]);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  async function act(name: string, action: ContainerAction) {
    setBusy((b) => ({ ...b, [name]: action }));
    setError(null);
    try {
      await api.containerAction(name, action);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy((b) => ({ ...b, [name]: undefined }));
    }
  }

  const running = list?.filter((c) => c.state === 'running').length ?? 0;

  return (
    <div className="page">
      <header className="page-header">
        <span className="page-header-icon">
          <Box size={22} strokeWidth={2} />
        </span>
        <div>
          <h1 className="page-title">Containers</h1>
          <p className="page-desc">
            {list == null
              ? 'Per-service container state from the host Docker daemon.'
              : `${running}/${list.length} running · auto-refreshing`}
          </p>
        </div>
      </header>

      {error && <div className="banner err">{error}</div>}

      {list == null ? (
        <div className="loading-row">
          <Spinner />
        </div>
      ) : list.length === 0 && !error ? (
        <div className="empty-card">
          <span className="empty-badge">Empty</span>
          <p>No atl4s-* containers found on the host.</p>
        </div>
      ) : (
        <div className="ctr-grid">
          {list.map((c) => {
            const isRunning = c.state === 'running';
            const pending = busy[c.name];
            return (
              <div className="ctr-card" key={c.name} onClick={() => setSelected(c.name)}>
                <div className="ctr-card-top">
                  <StatusBadge level={c.level} text={c.health ?? c.state} />
                  <div className="ctr-actions" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="icon-btn sm"
                      disabled={!!pending}
                      title="Restart"
                      aria-label={`Restart ${c.name}`}
                      onClick={() => act(c.name, 'restart')}
                    >
                      <RotateCw size={16} className={pending === 'restart' ? 'spin' : ''} />
                    </button>
                    {isRunning ? (
                      <button
                        className="icon-btn sm"
                        disabled={!!pending}
                        title="Stop"
                        aria-label={`Stop ${c.name}`}
                        onClick={() => act(c.name, 'stop')}
                      >
                        <Square size={15} />
                      </button>
                    ) : (
                      <button
                        className="icon-btn sm"
                        disabled={!!pending}
                        title="Start"
                        aria-label={`Start ${c.name}`}
                        onClick={() => act(c.name, 'start')}
                      >
                        <Play size={15} />
                      </button>
                    )}
                  </div>
                </div>

                <div className="ctr-card-name mono">{displayName(c.name)}</div>
                <div className="ctr-card-image mono" title={c.image ?? ''}>
                  {c.image ?? '—'}
                </div>

                <div className="ctr-card-foot">
                  <span>{formatUptime(c.uptime_sec)}</span>
                  <span className="dot-sep">·</span>
                  <span>
                    {c.restart_count} restart{c.restart_count === 1 ? '' : 's'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selected && (
        <ContainerDrawer name={selected} onClose={() => setSelected(null)} onChanged={load} />
      )}
    </div>
  );
}
