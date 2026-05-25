// Pipelines page — perception / fusion service config + on/off toggle.
//
// Each card describes one entry from services/dashboard/config/pipelines.yaml
// and shows its docker container status (resolved through /var/run/docker.sock,
// same mechanism as the Health page). Expanding a card reveals the live
// output-topic strip and a config form generated from the registry schema;
// saving writes services/dashboard/config/pipelines/{id}.yaml, which the
// perception service is expected to mount and read at startup.

import { useEffect, useMemo, useState } from 'react';
import {
  Cpu,
  Play,
  RefreshCw,
  Save,
  Scan,
  Square,
  Target,
  Workflow,
  type LucideIcon,
} from 'lucide-react';
import {
  api,
  type HealthLevel,
  type Pipeline,
  type PipelineDetail,
  type PipelineField,
} from '../lib/api';
import { useTopics } from '../lib/topics';
import { Badge, Card, EmptyState, PageHeader, StatusDot } from '../lib/components';

const POLL_MS = 5000;

const ICONS: Record<string, LucideIcon> = {
  perception: Scan,
  fusion: Workflow,
  target: Target,
  scan: Scan,
  brain: Cpu,
};

function iconFor(hint: string): LucideIcon {
  return ICONS[hint] || Cpu;
}

const LEVEL_LABEL: Record<HealthLevel, string> = {
  ok: 'Running',
  idle: 'Not deployed',
  warn: 'Restarting',
  err: 'Stopped',
};

export function Pipelines() {
  const [pipelines, setPipelines] = useState<Pipeline[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setPipelines(await api.listPipelines());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    refresh();
    const id = window.setInterval(refresh, POLL_MS);
    return () => window.clearInterval(id);
  }, []);

  return (
    <section>
      <PageHeader
        title="Pipelines"
        subtitle={
          pipelines
            ? `${pipelines.length} configured · ${pipelines.filter((p) => p.status.level === 'ok').length} running`
            : 'Loading…'
        }
        right={
          <button className="ghost" onClick={refresh} title="Refresh">
            <RefreshCw size={14} />
          </button>
        }
      />

      {error && <p className="error">{error}</p>}

      {pipelines === null ? (
        <p className="placeholder">Loading…</p>
      ) : pipelines.length === 0 ? (
        <EmptyState icon={Cpu} title="No pipelines configured">
          Add an entry to <code>services/dashboard/config/pipelines.yaml</code> and{' '}
          <code>docker compose restart dashboard</code>.
        </EmptyState>
      ) : (
        <div className="stack">
          {pipelines.map((p) => (
            <PipelineCard
              key={p.id}
              pipeline={p}
              expanded={expanded === p.id}
              onToggle={() => setExpanded((cur) => (cur === p.id ? null : p.id))}
              onAction={refresh}
              onError={setError}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function PipelineCard({
  pipeline,
  expanded,
  onToggle,
  onAction,
  onError,
}: {
  pipeline: Pipeline;
  expanded: boolean;
  onToggle: () => void;
  onAction: () => Promise<void>;
  onError: (msg: string) => void;
}) {
  const Icon = iconFor(pipeline.icon);
  const { state, level, message } = pipeline.status;
  const running = state === 'running';
  const absent = state === 'absent';

  const doStart = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.startPipeline(pipeline.id);
      await onAction();
    } catch (e) {
      onError((e as Error).message);
    }
  };
  const doStop = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.stopPipeline(pipeline.id);
      await onAction();
    } catch (e) {
      onError((e as Error).message);
    }
  };

  return (
    <Card className="flush pipeline-card">
      <div className="pipeline-head" onClick={onToggle}>
        <Icon size={26} className="pipeline-icon" />
        <div className="pipeline-meta">
          <div className="row space" style={{ gap: 12 }}>
            <div>
              <div className="pipeline-name">{pipeline.name}</div>
              <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                {pipeline.description}
              </div>
            </div>
            <Badge tone={level}>
              <StatusDot tone={level} />
              {LEVEL_LABEL[level] || state}
            </Badge>
          </div>
          <div className="pipeline-topic-row">
            <span className="dim">In:</span>
            {pipeline.input_topics.length === 0 ? (
              <code className="dim">—</code>
            ) : (
              pipeline.input_topics.map((t) => (
                <code key={t} className="mono">{t}</code>
              ))
            )}
            <span className="dim">·</span>
            <span className="dim">Out:</span>
            {pipeline.output_topics.length === 0 ? (
              <code className="dim">—</code>
            ) : (
              pipeline.output_topics.map((t) => (
                <code key={t} className="mono">{t}</code>
              ))
            )}
          </div>
        </div>
        <div className="row" style={{ gap: 6 }} onClick={(e) => e.stopPropagation()}>
          {running ? (
            <button className="danger" onClick={doStop}>
              <Square size={13} style={{ marginRight: 4 }} />
              Stop
            </button>
          ) : (
            <button onClick={doStart} disabled={absent} title={absent ? message : ''}>
              <Play size={13} style={{ marginRight: 4 }} />
              Start
            </button>
          )}
          <button className="ghost icon-only" onClick={onToggle} title={expanded ? 'Collapse' : 'Configure'}>
            <span className="caret">{expanded ? '▾' : '▸'}</span>
          </button>
        </div>
      </div>

      {expanded && (
        <div className="pipeline-body">
          <OutputsPanel topics={pipeline.output_topics} />
          <ConfigPanel pipeline={pipeline} onError={onError} />
        </div>
      )}
    </Card>
  );
}

function OutputsPanel({ topics }: { topics: string[] }) {
  const { topics: live } = useTopics();
  if (topics.length === 0) return null;
  return (
    <div className="outputs-panel">
      <div className="endpoint-label">Live outputs</div>
      <table className="topics">
        <thead>
          <tr>
            <th>Topic</th>
            <th>Rate</th>
            <th>Last message</th>
          </tr>
        </thead>
        <tbody>
          {topics.map((t) => {
            const msg = live[t];
            return (
              <tr key={t}>
                <td>{t}</td>
                <td className={msg ? '' : 'dim'}>
                  {msg ? `${msg.rate.toFixed(1)} Hz` : '—'}
                </td>
                <td className="dim">
                  {msg ? new Date(msg.ts * 1000).toLocaleTimeString() : 'not yet seen'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ConfigPanel({
  pipeline,
  onError,
}: {
  pipeline: Pipeline;
  onError: (msg: string) => void;
}) {
  const [detail, setDetail] = useState<PipelineDetail | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    api
      .getPipeline(pipeline.id)
      .then((d) => {
        setDetail(d);
        setValues(d.config);
        setDirty(false);
      })
      .catch((e) => onError((e as Error).message));
    // pipeline.id is stable per card render; we only want this once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pipeline.id]);

  const defaults = useMemo(() => {
    const out: Record<string, unknown> = {};
    for (const f of pipeline.config_schema) out[f.name] = f.default;
    return out;
  }, [pipeline.config_schema]);

  const set = (name: string, v: unknown) => {
    setValues((prev) => ({ ...prev, [name]: v }));
    setDirty(true);
    setSavedAt(null);
  };

  const save = async () => {
    setSaving(true);
    try {
      const r = await api.setPipelineConfig(pipeline.id, values);
      setValues(r.config);
      setDirty(false);
      setSavedAt(Date.now());
    } catch (e) {
      onError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const restart = async () => {
    try {
      await api.restartPipeline(pipeline.id);
    } catch (e) {
      onError((e as Error).message);
    }
  };

  const resetDefaults = () => {
    setValues({ ...defaults });
    setDirty(true);
    setSavedAt(null);
  };

  if (!detail) {
    return <p className="placeholder">Loading config…</p>;
  }

  return (
    <div className="config-panel">
      <div className="row space" style={{ marginBottom: 10 }}>
        <span className="endpoint-label">Configuration</span>
        {savedAt && (
          <span className="dim" style={{ fontSize: 12 }}>
            Saved {new Date(savedAt).toLocaleTimeString()}
          </span>
        )}
      </div>
      <div className="config-fields">
        {pipeline.config_schema.map((field) => (
          <FieldRow
            key={field.name}
            field={field}
            value={values[field.name]}
            onChange={(v) => set(field.name, v)}
          />
        ))}
      </div>
      <div className="form-actions" style={{ marginTop: 16 }}>
        <button onClick={save} disabled={saving || !dirty}>
          <Save size={13} style={{ marginRight: 4 }} />
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button className="ghost" onClick={resetDefaults} disabled={saving}>
          Reset to defaults
        </button>
        <button className="ghost" onClick={restart} title="Restart container so changes take effect">
          <RefreshCw size={13} style={{ marginRight: 4 }} />
          Restart
        </button>
        {dirty && <span className="dim" style={{ fontSize: 12, marginLeft: 8 }}>Unsaved changes</span>}
      </div>
      <p className="hint" style={{ marginTop: 14 }}>
        Saving writes <code className="mono">config/pipelines/{pipeline.id}.yaml</code>.
        Most services only read config at startup — click Restart to apply.
      </p>
    </div>
  );
}

function FieldRow({
  field,
  value,
  onChange,
}: {
  field: PipelineField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  return (
    <label className="config-field">
      <span className="config-field-label">{field.label}</span>
      <FieldInput field={field} value={value} onChange={onChange} />
    </label>
  );
}

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: PipelineField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  switch (field.type) {
    case 'boolean':
      return (
        <span
          className={`toggle${value ? ' on' : ''}`}
          role="switch"
          aria-checked={value === true}
          tabIndex={0}
          onClick={() => onChange(!value)}
          onKeyDown={(e) => {
            if (e.key === ' ' || e.key === 'Enter') {
              e.preventDefault();
              onChange(!value);
            }
          }}
        >
          <span className="toggle-knob" />
        </span>
      );
    case 'select':
      return (
        <select value={String(value ?? '')} onChange={(e) => onChange(e.target.value)}>
          {(field.options || []).map((o) => (
            <option key={String(o)} value={String(o)}>
              {String(o)}
            </option>
          ))}
        </select>
      );
    case 'slider': {
      const n = typeof value === 'number' ? value : Number(value || 0);
      return (
        <div className="slider-row">
          <input
            type="range"
            min={field.min ?? 0}
            max={field.max ?? 1}
            step={field.step ?? 0.01}
            value={Number.isFinite(n) ? n : 0}
            onChange={(e) => onChange(Number(e.target.value))}
            className="slider"
          />
          <span className="mono slider-value">{n.toFixed(2)}</span>
        </div>
      );
    }
    case 'number':
      return (
        <input
          type="number"
          value={typeof value === 'number' ? value : String(value ?? '')}
          min={field.min}
          max={field.max}
          step={field.step}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      );
    case 'list_string': {
      const text = Array.isArray(value) ? (value as string[]).join(', ') : String(value ?? '');
      return (
        <input
          type="text"
          value={text}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(/[\s,]+/)
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
          placeholder="comma- or space-separated"
        />
      );
    }
    case 'string':
    default:
      return (
        <input
          type="text"
          value={String(value ?? '')}
          onChange={(e) => onChange(e.target.value)}
        />
      );
  }
}

