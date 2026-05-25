import { NavLink, Route, Routes } from 'react-router-dom';
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

export function App() {
  return (
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
  );
}
