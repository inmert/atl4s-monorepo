import { useTopic } from '../lib/topics';

const LEVEL_LABEL: Record<number, string> = { 0: 'OK', 1: 'WARN', 2: 'ERROR', 3: 'STALE' };
const LEVEL_TONE: Record<number, string> = { 0: 'ok', 1: 'warn', 2: 'err', 3: 'err' };

type KV = { key: string; value: string };
type DiagnosticStatus = {
  level: unknown;
  name: string;
  message: string;
  hardware_id: string;
  values: KV[];
};

// ROS `byte` arrives as a single-char string via message_to_ordereddict.
function levelNum(level: unknown): number {
  if (typeof level === 'number') return level;
  if (typeof level === 'string' && level.length > 0) return level.charCodeAt(0);
  return 0;
}

export function Health() {
  const msg = useTopic('/atl4s/health');

  if (!msg) {
    return (
      <section>
        <h1>Health</h1>
        <p className="placeholder">Waiting for <code>/atl4s/health</code>…</p>
      </section>
    );
  }

  const statuses = (msg.data?.status || []) as DiagnosticStatus[];
  const lastSeen = new Date(msg.ts * 1000).toLocaleTimeString();

  return (
    <section>
      <div className="page-header">
        <h1>Health</h1>
        <span className="hint">last update {lastSeen} ({msg.rate.toFixed(1)} Hz)</span>
      </div>

      {statuses.length === 0 ? (
        <p className="placeholder">No diagnostic statuses reported.</p>
      ) : (
        <table className="bags">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Level</th>
              <th>Message</th>
              <th>Values</th>
            </tr>
          </thead>
          <tbody>
            {statuses.map((s) => {
              const lvl = levelNum(s.level);
              return (
                <tr key={s.name}>
                  <td>{s.name}</td>
                  <td>
                    <span className={`badge ${LEVEL_TONE[lvl] || ''}`}>
                      {LEVEL_LABEL[lvl] || `LVL ${lvl}`}
                    </span>
                  </td>
                  <td>{s.message}</td>
                  <td className="kvs">
                    {(s.values || []).map((kv) => (
                      <div key={kv.key}><code>{kv.key}</code>: {kv.value}</div>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
}
