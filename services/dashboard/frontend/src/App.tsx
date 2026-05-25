import { NavLink, Route, Routes } from 'react-router-dom';
import { TopicProvider, useTopic } from './lib/topics';
import { Home } from './pages/Home';
import { Bags } from './pages/Bags';
import { Live } from './pages/Live';
import { Record } from './pages/Record';
import { Replay } from './pages/Replay';
import { Pipelines } from './pages/Pipelines';
import { Health } from './pages/Health';

const tabs = [
  { to: '/', label: 'Home', end: true },
  { to: '/live', label: 'Live' },
  { to: '/bags', label: 'Bags' },
  { to: '/record', label: 'Record' },
  { to: '/replay', label: 'Replay' },
  { to: '/pipelines', label: 'Pipelines' },
  { to: '/health', label: 'Health' },
];

// DiagnosticStatus.level is `byte` in ROS; message_to_ordereddict serializes
// it as a single-character string, so we coerce via charCodeAt on the client.
function levelNum(level: unknown): number {
  if (typeof level === 'number') return level;
  if (typeof level === 'string' && level.length > 0) return level.charCodeAt(0);
  return 0;
}

function HealthBadge() {
  const health = useTopic('/atl4s/health');
  if (!health) {
    return <span className="health-badge dim" title="no /atl4s/health yet">● —</span>;
  }
  const statuses = (health.data?.status || []) as Array<{ level: unknown }>;
  const max = statuses.reduce((m, s) => Math.max(m, levelNum(s.level)), 0);
  const tone = max === 0 ? 'ok' : max === 1 ? 'warn' : 'err';
  const label = max === 0 ? 'OK' : max === 1 ? 'WARN' : max === 3 ? 'STALE' : 'ERR';
  return <span className={`health-badge ${tone}`} title={`health: ${label}`}>● {label}</span>;
}

export function App() {
  return (
    <TopicProvider>
      <div className="app">
        <header className="nav">
          <div className="brand">ATL4S</div>
          <nav>
            {tabs.map((t) => (
              <NavLink key={t.to} to={t.to} end={t.end}>
                {t.label}
              </NavLink>
            ))}
          </nav>
          <div className="nav-right">
            <HealthBadge />
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/live" element={<Live />} />
            <Route path="/bags" element={<Bags />} />
            <Route path="/record" element={<Record />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="/pipelines" element={<Pipelines />} />
            <Route path="/health" element={<Health />} />
          </Routes>
        </main>
      </div>
    </TopicProvider>
  );
}
