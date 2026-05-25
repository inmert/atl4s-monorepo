// Shared health-snapshot provider. /api/health is polled every 5s and the
// result fanned out to consumers (HealthBadge in the sidebar, Home's
// Health card, the Health page). Single fetch, single source of truth.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, type HealthSnapshot } from './api';

const POLL_MS = 5000;

type Ctx = {
  snap: HealthSnapshot | null;
  error: string | null;
  refresh: () => Promise<void>;
};

const HealthCtx = createContext<Ctx>({ snap: null, error: null, refresh: async () => {} });

export function HealthProvider({ children }: { children: ReactNode }) {
  const [snap, setSnap] = useState<HealthSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setSnap(await api.health());
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

  const value = useMemo(() => ({ snap, error, refresh }), [snap, error]);
  return <HealthCtx.Provider value={value}>{children}</HealthCtx.Provider>;
}

export function useHealth(): Ctx {
  return useContext(HealthCtx);
}
