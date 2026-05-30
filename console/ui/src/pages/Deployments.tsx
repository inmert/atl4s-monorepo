import { useCallback, useEffect, useState } from 'react';
import { Plus, Rocket } from 'lucide-react';
import { api, Deployment, DeploymentInput, DeploymentOptions } from '../lib/api';
import { STATUS_LEVEL, TYPE_ICON, TYPE_LABEL, blankDeployment } from '../lib/deployments';
import { StatusBadge } from '../components/StatusBadge';
import { Spinner } from '../components/Spinner';
import { Modal } from '../components/Modal';
import { DeploymentForm } from '../components/DeploymentForm';
import { DeploymentDrawer } from '../components/DeploymentDrawer';

const REFRESH_MS = 5000;

export function Deployments() {
  const [list, setList] = useState<Deployment[] | null>(null);
  const [options, setOptions] = useState<DeploymentOptions | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<DeploymentInput>(blankDeployment);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await api.deployments.list();
      setList(r.deployments);
      setOptions(r.options);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load deployments');
      setList([]);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  function openAdd() {
    setDraft(blankDeployment());
    setCreateError(null);
    setAdding(true);
  }

  async function create() {
    setCreating(true);
    setCreateError(null);
    try {
      await api.deployments.create(draft);
      setAdding(false);
      await load();
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create deployment');
    } finally {
      setCreating(false);
    }
  }

  const selectedDep = list?.find((d) => d.id === selected) ?? null;
  const online = list?.filter((d) => d.status === 'online').length ?? 0;

  return (
    <div className="page">
      <header className="page-header">
        <span className="page-header-icon">
          <Rocket size={22} strokeWidth={2} />
        </span>
        <div className="page-header-text">
          <h1 className="page-title">Deployments</h1>
          <p className="page-desc">
            {list == null ? 'Robots, vehicles, and sensors.' : `${online}/${list.length} online`}
          </p>
        </div>
        <button className="btn btn-primary page-header-action" onClick={openAdd}>
          <Plus size={16} /> Add deployment
        </button>
      </header>

      {error && <div className="banner err">{error}</div>}

      {list == null ? (
        <div className="loading-row">
          <Spinner />
        </div>
      ) : list.length === 0 && !error ? (
        <div className="empty-card">
          <span className="empty-badge">Empty</span>
          <p>No deployments yet. Add one to start tracking a robot or sensor.</p>
        </div>
      ) : (
        <div className="dep-grid">
          {list.map((d) => {
            const Icon = TYPE_ICON[d.type];
            return (
              <div className="dep-card" key={d.id} onClick={() => setSelected(d.id)}>
                <div className="dep-card-head">
                  <span className="dep-icon">
                    <Icon size={20} strokeWidth={2} />
                  </span>
                  <StatusBadge level={STATUS_LEVEL[d.status]} text={d.status} />
                </div>
                <div className="dep-name">{d.name}</div>
                <div className="dep-tags">
                  <span className="chip">{TYPE_LABEL[d.type]}</span>
                  <span className="chip chip-muted">{d.mode === 'simulator' ? 'Simulator' : 'Real'}</span>
                </div>
                <div className="dep-conn mono">
                  {d.protocol} · {d.host || '—'}:{d.port}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {selectedDep && (
        <DeploymentDrawer
          deployment={selectedDep}
          options={options}
          onClose={() => setSelected(null)}
          onChanged={load}
        />
      )}

      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        title="Add deployment"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setAdding(false)} disabled={creating}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={create} disabled={creating || !draft.name.trim()}>
              {creating ? 'Creating…' : 'Create'}
            </button>
          </>
        }
      >
        {createError && <div className="banner err">{createError}</div>}
        <DeploymentForm value={draft} onChange={(p) => setDraft((d) => ({ ...d, ...p }))} options={options} />
      </Modal>
    </div>
  );
}
