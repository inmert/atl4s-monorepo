import { NavLink, Route, Routes } from 'react-router-dom';
import {
  Activity,
  Archive,
  Bot,
  Cpu,
  Home as HomeIcon,
  Share2,
} from 'lucide-react';
import { TopicProvider, useTopic } from './lib/topics';
import { Home } from './pages/Home';
import { Robots } from './pages/Robots';
import { Pipelines } from './pages/Pipelines';
import { RosbagManager } from './pages/RosbagManager';
import { Ros } from './pages/Ros';
import { Health } from './pages/Health';
// Legacy pages — still routable during the redesign so functionality isn't
// lost while Robots / Rosbag Manager are filled out. Removed in later phases.
import { Live } from './pages/Live';
import { Map } from './pages/Map';

const nav = [
  { to: '/', label: 'Home', icon: HomeIcon, end: true },
  { to: '/robots', label: 'Robots', icon: Bot },
  { to: '/pipelines', label: 'Pipelines', icon: Cpu },
  { to: '/rosbags', label: 'Rosbag Manager', icon: Archive },
  { to: '/ros', label: 'ROS', icon: Share2 },
  { to: '/health', label: 'Health', icon: Activity },
];

function levelNum(level: unknown): number {
  if (typeof level === 'number') return level;
  if (typeof level === 'string' && level.length > 0) return level.charCodeAt(0);
  return 0;
}

function HealthBadge() {
  const health = useTopic('/atl4s/health');
  if (!health) {
    return (
      <span className="health-badge dim" title="no /atl4s/health yet">
        <span className="dot" /> idle
      </span>
    );
  }
  const statuses = (health.data?.status || []) as Array<{ level: unknown }>;
  const max = statuses.reduce((m, s) => Math.max(m, levelNum(s.level)), 0);
  const tone = max === 0 ? 'ok' : max === 1 ? 'warn' : 'err';
  const label = max === 0 ? 'Healthy' : max === 1 ? 'Warn' : max === 3 ? 'Stale' : 'Error';
  return (
    <span className={`health-badge ${tone}`} title={`health: ${label}`}>
      <span className={`dot ${tone}`} /> {label}
    </span>
  );
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-dot">A</span>
        <span>ATL4S</span>
      </div>

      {nav.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `sidebar-link${isActive ? ' active' : ''}`}
        >
          <item.icon className="icon" />
          <span>{item.label}</span>
        </NavLink>
      ))}

      <div className="sidebar-footer">
        <HealthBadge />
      </div>
    </aside>
  );
}

export function App() {
  return (
    <TopicProvider>
      <div className="app">
        <Sidebar />
        <main className="main">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/robots" element={<Robots />} />
            <Route path="/robots/:id" element={<Robots />} />
            <Route path="/pipelines" element={<Pipelines />} />
            <Route path="/rosbags/*" element={<RosbagManager />} />
            <Route path="/ros" element={<Ros />} />
            <Route path="/health" element={<Health />} />
            {/* Legacy: kept routable during the redesign, hidden from nav. */}
            <Route path="/live" element={<Live />} />
            <Route path="/map" element={<Map />} />
          </Routes>
        </main>
      </div>
    </TopicProvider>
  );
}
