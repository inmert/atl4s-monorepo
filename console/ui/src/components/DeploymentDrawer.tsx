import { ReactNode, useState } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { api, Deployment, DeploymentInput, DeploymentOptions } from '../lib/api';
import { PROTOCOL_LABEL, STATUS_LEVEL, TYPE_ICON, TYPE_LABEL } from '../lib/deployments';
import { Drawer } from './Drawer';
import { StatusBadge } from './StatusBadge';
import { DeploymentForm } from './DeploymentForm';

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="kv-row">
      <span className="kv-label">{label}</span>
      <span className="kv-value">{children}</span>
    </div>
  );
}

function toInput(d: Deployment): DeploymentInput {
  const { name, type, mode, protocol, host, port, description, containers, telemetry } = d;
  return { name, type, mode, protocol, host, port, description, containers, telemetry };
}

export function DeploymentDrawer({
  deployment,
  options,
  onClose,
  onChanged,
}: {
  deployment: Deployment;
  options: DeploymentOptions | null;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DeploymentInput>(() => toInput(deployment));
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const Icon = TYPE_ICON[deployment.type];

  function startEdit() {
    setDraft(toInput(deployment));
    setError(null);
    setEditing(true);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.deployments.update(deployment.id, draft);
      onChanged();
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deployments.remove(deployment.id);
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete');
      setBusy(false);
    }
  }

  const headerActions = !editing && (
    <div className="drawer-actions">
      <button className="btn btn-ghost xs" onClick={startEdit}>
        <Pencil size={14} /> Edit
      </button>
    </div>
  );

  const telemetryEntries = Object.entries(deployment.telemetry ?? {});

  return (
    <Drawer
      open
      onClose={onClose}
      title={
        <span className="drawer-title-row">
          <span className="dep-icon sm">
            <Icon size={16} />
          </span>
          {deployment.name}
        </span>
      }
      subtitle={<StatusBadge level={STATUS_LEVEL[deployment.status]} text={deployment.status} />}
      actions={headerActions}
    >
      {error && <div className="banner err">{error}</div>}

      {editing ? (
        <section className="drawer-section">
          <DeploymentForm value={draft} onChange={(p) => setDraft((d) => ({ ...d, ...p }))} options={options} />
          <div className="form-actions">
            <button className="btn btn-ghost" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={save} disabled={busy || !draft.name.trim()}>
              {busy ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </section>
      ) : (
        <>
          <section className="drawer-section">
            <h3 className="drawer-section-title">Settings</h3>
            <div className="kv">
              <Row label="ID"><span className="mono">{deployment.id}</span></Row>
              <Row label="Type">{TYPE_LABEL[deployment.type]}</Row>
              <Row label="Mode">{deployment.mode === 'simulator' ? 'Simulator' : 'Real'}</Row>
              <Row label="Protocol">{PROTOCOL_LABEL[deployment.protocol] ?? deployment.protocol}</Row>
              <Row label="Connection">
                <span className="mono">
                  {deployment.host || '—'}:{deployment.port}
                </span>
              </Row>
              {deployment.description && <Row label="Description">{deployment.description}</Row>}
              <Row label="Linked containers">
                {deployment.containers.length === 0 ? (
                  <span className="muted">none</span>
                ) : (
                  <span className="chips">
                    {deployment.containers.map((c) => (
                      <span className="chip mono" key={c}>
                        {c}
                      </span>
                    ))}
                  </span>
                )}
              </Row>
            </div>
          </section>

          {telemetryEntries.length > 0 && (
            <section className="drawer-section">
              <h3 className="drawer-section-title">Telemetry topics</h3>
              <div className="kv">
                {telemetryEntries.map(([key, topic]) => (
                  <Row key={key} label={key}>
                    <span className="mono">{topic}</span>
                  </Row>
                ))}
              </div>
            </section>
          )}

          <section className="drawer-section">
            <h3 className="drawer-section-title">Danger zone</h3>
            {confirmDelete ? (
              <div className="confirm">
                <span>Delete “{deployment.name}”? This can't be undone.</span>
                <div className="confirm-actions">
                  <button className="btn btn-ghost xs" onClick={() => setConfirmDelete(false)} disabled={busy}>
                    Cancel
                  </button>
                  <button className="btn btn-danger xs" onClick={remove} disabled={busy}>
                    {busy ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </div>
            ) : (
              <button className="btn btn-danger xs" onClick={() => setConfirmDelete(true)}>
                <Trash2 size={14} /> Delete deployment
              </button>
            )}
          </section>
        </>
      )}
    </Drawer>
  );
}
