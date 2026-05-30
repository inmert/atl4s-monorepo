import { useCallback, useEffect, useState } from 'react';
import { Play, RotateCw, Square, Workflow } from 'lucide-react';
import { api, Pipeline, PipelineAction } from '../lib/api';
import { StatusBadge } from '../components/StatusBadge';
import { Spinner } from '../components/Spinner';
import { PipelineDrawer } from '../components/PipelineDrawer';

const REFRESH_MS = 4000;

const STATUS = {
  running: { level: 'ok' as const, text: 'Running' },
  stopped: { level: 'idle' as const, text: 'Stopped' },
  not_deployed: { level: 'warn' as const, text: 'Not deployed' },
};

export function Pipelines() {
  const [list, setList] = useState<Pipeline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, PipelineAction | undefined>>({});

  const load = useCallback(async () => {
    try {
      const r = await api.pipelines.list();
      setList(r.pipelines);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load pipelines');
      setList([]);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  async function act(id: string, action: PipelineAction) {
    setBusy((b) => ({ ...b, [id]: action }));
    setError(null);
    try {
      await api.pipelines.action(id, action);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy((b) => ({ ...b, [id]: undefined }));
    }
  }

  const selectedPipeline = list?.find((p) => p.id === selected) ?? null;

  return (
    <div className="page">
      <header className="page-header">
        <span className="page-header-icon">
          <Workflow size={22} strokeWidth={2} />
        </span>
        <div>
          <h1 className="page-title">Pipelines</h1>
          <p className="page-desc">Perception &amp; ML services — start, stop, and configure.</p>
        </div>
      </header>

      {error && <div className="banner err">{error}</div>}

      {list == null ? (
        <div className="loading-row">
          <Spinner />
        </div>
      ) : (
        <div className="dep-grid">
          {list.map((p) => {
            const isRunning = p.status === 'running';
            const deployed = p.status !== 'not_deployed';
            const pending = busy[p.id];
            return (
              <div className="dep-card" key={p.id} onClick={() => setSelected(p.id)}>
                <div className="dep-card-head">
                  <span className="dep-icon">
                    <Workflow size={20} strokeWidth={2} />
                  </span>
                  <StatusBadge level={STATUS[p.status].level} text={STATUS[p.status].text} />
                </div>
                <div className="dep-name">{p.name}</div>
                <div className="pipeline-desc">{p.description}</div>
                <div className="ctr-actions" onClick={(e) => e.stopPropagation()}>
                  {isRunning ? (
                    <button className="icon-btn sm" title="Stop" disabled={!!pending} onClick={() => act(p.id, 'stop')}>
                      <Square size={15} />
                    </button>
                  ) : (
                    <button className="icon-btn sm" title="Start" disabled={!!pending || !deployed} onClick={() => act(p.id, 'start')}>
                      <Play size={15} />
                    </button>
                  )}
                  <button className="icon-btn sm" title="Restart" disabled={!!pending || !deployed} onClick={() => act(p.id, 'restart')}>
                    <RotateCw size={15} className={pending === 'restart' ? 'spin' : ''} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedPipeline && (
        <PipelineDrawer pipeline={selectedPipeline} onClose={() => setSelected(null)} onChanged={load} />
      )}
    </div>
  );
}
