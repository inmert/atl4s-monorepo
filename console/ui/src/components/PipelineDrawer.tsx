import { useEffect, useState } from 'react';
import { Play, RotateCw, Square } from 'lucide-react';
import { api, Pipeline, PipelineAction, PipelineField } from '../lib/api';
import { Drawer } from './Drawer';
import { StatusBadge } from './StatusBadge';

const STATUS = {
  running: { level: 'ok' as const, text: 'Running' },
  stopped: { level: 'idle' as const, text: 'Stopped' },
  not_deployed: { level: 'warn' as const, text: 'Not deployed' },
};

function fieldValue(field: PipelineField, draft: Record<string, unknown>): unknown {
  return field.key in draft ? draft[field.key] : field.default;
}

function Field({
  field,
  value,
  onChange,
}: {
  field: PipelineField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const label = <span className="field-label">{field.label}</span>;

  if (field.type === 'select') {
    return (
      <label className="field">
        {label}
        <select className="select" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
          {(field.options ?? []).map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
      </label>
    );
  }

  if (field.type === 'slider') {
    return (
      <label className="field">
        <span className="field-label slider-label">
          {field.label}
          <span className="mono">{Number(value ?? 0)}</span>
        </span>
        <input
          type="range"
          className="slider"
          min={field.min ?? 0}
          max={field.max ?? 1}
          step={field.step ?? 0.05}
          value={Number(value ?? 0)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </label>
    );
  }

  if (field.type === 'number') {
    return (
      <label className="field">
        {label}
        <input
          type="number"
          className="input"
          min={field.min}
          max={field.max}
          step={field.step}
          value={Number(value ?? 0)}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </label>
    );
  }

  if (field.type === 'boolean') {
    return (
      <label className="field field-inline">
        {label}
        <button
          type="button"
          className={`toggle${value ? ' on' : ''}`}
          onClick={() => onChange(!value)}
          aria-pressed={!!value}
        >
          <span className="toggle-knob" />
        </button>
      </label>
    );
  }

  if (field.type === 'color') {
    return (
      <label className="field">
        {label}
        <span className="color-row">
          <input type="color" className="color-input" value={String(value ?? '#000000')} onChange={(e) => onChange(e.target.value)} />
          <input className="input mono" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} />
        </span>
      </label>
    );
  }

  // string
  return (
    <label className="field">
      {label}
      <input className="input" value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

export function PipelineDrawer({
  pipeline,
  onClose,
  onChanged,
}: {
  pipeline: Pipeline;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState<Record<string, unknown>>(pipeline.config);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState(false);

  useEffect(() => {
    setDraft(pipeline.config);
  }, [pipeline.config]);

  const running = pipeline.status === 'running';
  const deployed = pipeline.status !== 'not_deployed';

  async function act(action: PipelineAction) {
    setBusy(action);
    setError(null);
    try {
      await api.pipelines.action(pipeline.id, action);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : `${action} failed`);
    } finally {
      setBusy(null);
    }
  }

  async function save() {
    setBusy('save');
    setError(null);
    try {
      await api.pipelines.updateConfig(pipeline.id, draft);
      onChanged();
      setSavedMsg(true);
      setTimeout(() => setSavedMsg(false), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setBusy(null);
    }
  }

  const actions = (
    <div className="drawer-actions">
      {running ? (
        <button className="btn btn-ghost xs" disabled={!!busy} onClick={() => act('stop')}>
          <Square size={14} /> Stop
        </button>
      ) : (
        <button className="btn btn-ghost xs" disabled={!!busy || !deployed} onClick={() => act('start')}>
          <Play size={14} /> Start
        </button>
      )}
      <button className="btn btn-ghost xs" disabled={!!busy || !deployed} onClick={() => act('restart')}>
        <RotateCw size={14} className={busy === 'restart' ? 'spin' : ''} /> Restart
      </button>
    </div>
  );

  return (
    <Drawer
      open
      onClose={onClose}
      title={pipeline.name}
      subtitle={<StatusBadge level={STATUS[pipeline.status].level} text={STATUS[pipeline.status].text} />}
      actions={actions}
    >
      {error && <div className="banner err">{error}</div>}
      {!deployed && (
        <div className="banner warn">
          Container <span className="mono">{pipeline.container}</span> isn't created yet — run{' '}
          <span className="mono">docker compose up -d {pipeline.id}</span> once.
        </div>
      )}

      <section className="drawer-section">
        <p className="muted">{pipeline.description}</p>
      </section>

      <section className="drawer-section">
        <h3 className="drawer-section-title">Configuration</h3>
        <p className="env-note">Saved to the pipeline's config file. <strong>Restart</strong> to apply.</p>
        <div className="form">
          {pipeline.fields.map((f) => (
            <Field key={f.key} field={f} value={fieldValue(f, draft)} onChange={(v) => setDraft((d) => ({ ...d, [f.key]: v }))} />
          ))}
        </div>
        <div className="form-actions">
          {savedMsg && <span className="saved-msg">Saved ✓</span>}
          <button className="btn btn-primary" disabled={busy === 'save'} onClick={save}>
            {busy === 'save' ? 'Saving…' : 'Save config'}
          </button>
        </div>
      </section>
    </Drawer>
  );
}
