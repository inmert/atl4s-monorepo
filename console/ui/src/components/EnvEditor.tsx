import { useEffect, useState } from 'react';
import { Eye, EyeOff, Pencil, Plus, Trash2 } from 'lucide-react';
import { api, ContainerDetail, EnvVar } from '../lib/api';

type Draft = { key: string; value: string; from_image: boolean };

export function EnvEditor({
  detail,
  onSaved,
}: {
  detail: ContainerDetail;
  onSaved: (d: ContainerDetail) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [reveal, setReveal] = useState(false);
  const [rows, setRows] = useState<Draft[]>(detail.env);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset when the container (or its env) changes underneath us.
  useEffect(() => {
    setRows(detail.env);
    setEditing(false);
    setError(null);
  }, [detail]);

  const startEdit = () => {
    setRows(detail.env);
    setError(null);
    setEditing(true);
  };

  const cancel = () => {
    setRows(detail.env);
    setError(null);
    setEditing(false);
  };

  const setRow = (i: number, patch: Partial<Draft>) =>
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  const removeRow = (i: number) => setRows((rs) => rs.filter((_, j) => j !== i));

  const addRow = () => setRows((rs) => [...rs, { key: '', value: '', from_image: false }]);

  async function save() {
    const env: Record<string, string> = {};
    for (const r of rows) {
      const key = r.key.trim();
      if (!key) continue;
      if (key.includes('=')) {
        setError(`Invalid key "${key}" — keys cannot contain "="`);
        return;
      }
      if (key in env) {
        setError(`Duplicate key "${key}"`);
        return;
      }
      env[key] = r.value;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.setContainerEnv(detail.name, env);
      onSaved(updated);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to apply environment');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="drawer-section">
      <div className="env-head">
        <h3 className="drawer-section-title">Environment</h3>
        <div className="env-head-actions">
          {!editing && (
            <button
              className="btn btn-ghost xs"
              onClick={() => setReveal((r) => !r)}
              title={reveal ? 'Hide values' : 'Reveal values'}
            >
              {reveal ? <EyeOff size={13} /> : <Eye size={13} />}
              {reveal ? 'Hide' : 'Reveal'}
            </button>
          )}
          {editing ? (
            <>
              <button className="btn btn-ghost xs" onClick={cancel} disabled={busy}>
                Cancel
              </button>
              <button className="btn btn-primary xs" onClick={save} disabled={busy}>
                {busy ? 'Applying…' : 'Apply'}
              </button>
            </>
          ) : (
            <button className="btn btn-ghost xs" onClick={startEdit}>
              <Pencil size={13} />
              Edit
            </button>
          )}
        </div>
      </div>

      {error && <div className="banner err">{error}</div>}

      {editing ? (
        <>
          <p className="env-note">
            Applying recreates the container with the new environment (image, mounts, network and
            restart policy are preserved). This is a runtime override, not written to{' '}
            <span className="mono">.env</span> — to revert, force a recreate from compose:{' '}
            <span className="mono">docker compose up -d --force-recreate {detail.service ?? detail.name.replace(/^atl4s-/, '')}</span>.
          </p>
          <div className="env-edit">
            {rows.map((r, i) => (
              <div className="env-edit-row" key={i}>
                <input
                  className="input env-key"
                  placeholder="KEY"
                  value={r.key}
                  onChange={(e) => setRow(i, { key: e.target.value })}
                />
                <input
                  className="input env-val"
                  placeholder="value"
                  value={r.value}
                  onChange={(e) => setRow(i, { value: e.target.value })}
                />
                <button
                  className="icon-btn sm"
                  onClick={() => removeRow(i)}
                  title="Remove"
                  aria-label={`Remove ${r.key || 'variable'}`}
                >
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
            <button className="btn btn-ghost xs env-add" onClick={addRow}>
              <Plus size={14} />
              Add variable
            </button>
          </div>
        </>
      ) : detail.env.length === 0 ? (
        <p className="muted">No environment variables.</p>
      ) : (
        <div className="env-list">
          {detail.env.map((v: EnvVar) => (
            <div className="env-item" key={v.key}>
              <span className="env-item-key mono">
                {v.key}
                {v.from_image && <span className="tag tag-ro">image</span>}
              </span>
              <span className="env-item-val mono">
                {reveal || v.value === '' ? v.value || '—' : '••••••••'}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
