import { DeploymentInput, DeploymentMode, DeploymentOptions, DeploymentType } from '../lib/api';
import { FUTURE_PROTOCOLS, PROTOCOL_LABEL, TYPE_LABEL } from '../lib/deployments';

// Controlled form shared by the Add modal and the edit drawer. The parent owns
// the value + submit; this only renders fields and emits patches.
export function DeploymentForm({
  value,
  onChange,
  options,
}: {
  value: DeploymentInput;
  onChange: (patch: Partial<DeploymentInput>) => void;
  options: DeploymentOptions | null;
}) {
  const types = options?.types ?? (['drone', 'rover', 'sensor'] as DeploymentType[]);
  const modes = options?.modes ?? (['simulator', 'real'] as DeploymentMode[]);
  const protocols = options?.protocols ?? ['mavlink'];

  return (
    <div className="form">
      <label className="field">
        <span className="field-label">Name</span>
        <input
          className="input"
          value={value.name}
          autoFocus
          placeholder="e.g. Field Rover 1"
          onChange={(e) => onChange({ name: e.target.value })}
        />
      </label>

      <div className="form-grid">
        <label className="field">
          <span className="field-label">Type</span>
          <select
            className="select"
            value={value.type}
            onChange={(e) => onChange({ type: e.target.value as DeploymentType })}
          >
            {types.map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t] ?? t}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Mode</span>
          <select
            className="select"
            value={value.mode}
            onChange={(e) => onChange({ mode: e.target.value as DeploymentMode })}
          >
            {modes.map((m) => (
              <option key={m} value={m}>
                {m === 'simulator' ? 'Simulator' : 'Real'}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="field">
        <span className="field-label">Communication protocol</span>
        <select
          className="select"
          value={value.protocol}
          onChange={(e) => onChange({ protocol: e.target.value })}
        >
          {protocols.map((p) => (
            <option key={p} value={p}>
              {PROTOCOL_LABEL[p] ?? p}
            </option>
          ))}
          {FUTURE_PROTOCOLS.filter((p) => !protocols.includes(p)).map((p) => (
            <option key={p} value={p} disabled>
              {PROTOCOL_LABEL[p] ?? p} — coming soon
            </option>
          ))}
        </select>
      </label>

      <div className="form-grid">
        <label className="field">
          <span className="field-label">Host</span>
          <input
            className="input"
            value={value.host}
            placeholder="127.0.0.1 or device IP"
            onChange={(e) => onChange({ host: e.target.value })}
          />
        </label>

        <label className="field">
          <span className="field-label">Port</span>
          <input
            className="input"
            type="number"
            min={1}
            max={65535}
            value={value.port}
            onChange={(e) => onChange({ port: Number(e.target.value) })}
          />
        </label>
      </div>

      <label className="field">
        <span className="field-label">Description</span>
        <textarea
          className="textarea"
          rows={2}
          value={value.description}
          placeholder="Optional notes"
          onChange={(e) => onChange({ description: e.target.value })}
        />
      </label>

      <label className="field">
        <span className="field-label">
          Linked containers <span className="field-hint">(optional · drives simulator status)</span>
        </span>
        <input
          className="input mono"
          value={value.containers.join(', ')}
          placeholder="atl4s-mavros, atl4s-sitl"
          onChange={(e) =>
            onChange({
              containers: e.target.value
                .split(',')
                .map((c) => c.trim())
                .filter(Boolean),
            })
          }
        />
      </label>
    </div>
  );
}
