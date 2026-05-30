import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { api, AuthState } from './api';

interface AuthCtx {
  state: AuthState | null; // null while the initial /me check is in flight
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);

const SIGNED_OUT: AuthState = { authenticated: false, username: null, auth_required: true };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState | null>(null);

  useEffect(() => {
    let alive = true;
    api.me()
      .then((s) => alive && setState(s))
      .catch(() => alive && setState(SIGNED_OUT));
    return () => {
      alive = false;
    };
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setState(await api.login(username, password));
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    setState(SIGNED_OUT);
  }, []);

  return <Ctx.Provider value={{ state, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useAuth must be used within AuthProvider');
  return c;
}
