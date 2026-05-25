import { NavLink, Route, Routes } from 'react-router-dom';
import {
  Activity,
  Archive,
  Bot,
  Cpu,
  Home as HomeIcon,
  Share2,
} from 'lucide-react';
import { TopicProvider } from './lib/topics';
import { HealthProvider, useHealth } from './lib/health';
import { Home } from './pages/Home';
import { Robots } from './pages/Robots';
import { RobotDetail } from './pages/RobotDetail';
import { Pipelines } from './pages/Pipelines';
import { RosbagManager } from './pages/RosbagManager';
import { Ros } from './pages/Ros';
import { Health } from './pages/Health';

const nav = [
  { to: '/', label: 'Home', icon: HomeIcon, end: true },
  { to: '/robots', label: 'Robots', icon: Bot },
  { to: '/pipelines', label: 'Pipelines', icon: Cpu },
  { to: '/rosbags', label: 'Rosbag Manager', icon: Archive },
  { to: '/ros', label: 'ROS', icon: Share2 },
  { to: '/health', label: 'Health', icon: Activity },
];

function HealthBadge() {
  const { snap } = useHealth();
  if (!snap) {
    return (
      <span className="health-badge dim" title="health pending">
        <span className="dot" /> idle
      </span>
    );
  }
  const tone = snap.level;
  const label =
    snap.level === 'ok'
      ? 'Healthy'
      : snap.level === 'warn'
        ? 'Warn'
        : 'Error';
  const title = `${snap.summary.ok} OK, ${snap.summary.warn} warn, ${snap.summary.err} err`;
  return (
    <span className={`health-badge ${tone}`} title={title}>
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
      <HealthProvider>
        <div className="app">
          <Sidebar />
          <main className="main">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/robots" element={<Robots />} />
              <Route path="/robots/:id" element={<RobotDetail />} />
              <Route path="/pipelines" element={<Pipelines />} />
              <Route path="/rosbags" element={<RosbagManager />} />
              {/* phase-5 left-overs from the old /rosbags/{record,replay} routes
                  collapse into the merged page so saved tabs still resolve. */}
              <Route path="/rosbags/record" element={<RosbagManager />} />
              <Route path="/rosbags/replay" element={<RosbagManager />} />
              <Route path="/ros" element={<Ros />} />
              <Route path="/health" element={<Health />} />
            </Routes>
          </main>
        </div>
      </HealthProvider>
    </TopicProvider>
  );
}
