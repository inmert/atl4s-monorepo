// Phase 1 wrapper. Routes /rosbags, /rosbags/record, /rosbags/replay to the
// existing Bags / Record / Replay pages under a single page header with
// segmented sub-navigation. Phase 5 will consolidate them visually into one
// surface; for now the IA is in place and the underlying pages still work.

import { useEffect } from 'react';
import { useLocation, useNavigate, Route, Routes } from 'react-router-dom';
import { Bags } from './Bags';
import { Record } from './Record';
import { Replay } from './Replay';
import { PageHeader, Subnav } from '../lib/components';

const tabs = [
  { id: 'browse', label: 'Browse' },
  { id: 'record', label: 'Record' },
  { id: 'replay', label: 'Replay' },
];

function tabFromPath(pathname: string): string {
  if (pathname.endsWith('/record')) return 'record';
  if (pathname.endsWith('/replay')) return 'replay';
  return 'browse';
}

export function RosbagManager() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = tabFromPath(location.pathname);

  // Vite HMR / direct nav: normalize "/rosbags/" → "/rosbags".
  useEffect(() => {
    if (location.pathname === '/rosbags/') navigate('/rosbags', { replace: true });
  }, [location.pathname, navigate]);

  return (
    <section>
      <PageHeader
        title="Rosbag Manager"
        subtitle="Browse, record, and replay bags."
      />

      <Subnav
        items={tabs}
        active={active}
        onSelect={(id) => navigate(id === 'browse' ? '/rosbags' : `/rosbags/${id}`)}
      />

      <Routes>
        <Route index element={<Bags />} />
        <Route path="record" element={<Record />} />
        <Route path="replay" element={<Replay />} />
      </Routes>
    </section>
  );
}
