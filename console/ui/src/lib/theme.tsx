import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';

// Theme preference: an explicit choice, or "system" to follow the OS. The
// resolved value (light | dark) is what actually drives the data-theme
// attribute that tokens.css keys off.
export type ThemePref = 'light' | 'dark' | 'system';
type Resolved = 'light' | 'dark';

interface ThemeCtx {
  pref: ThemePref;
  resolved: Resolved;
  setPref: (p: ThemePref) => void;
  toggle: () => void;
}

const Ctx = createContext<ThemeCtx | null>(null);
const STORAGE_KEY = 'atl4s-console-theme';

function systemResolved(): Resolved {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolve(pref: ThemePref): Resolved {
  return pref === 'system' ? systemResolved() : pref;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<ThemePref>(
    () => (localStorage.getItem(STORAGE_KEY) as ThemePref) || 'system',
  );
  const [resolved, setResolved] = useState<Resolved>(() => resolve(pref));

  useEffect(() => {
    const apply = () => {
      const r = resolve(pref);
      setResolved(r);
      document.documentElement.setAttribute('data-theme', r);
    };
    apply();
    // Only follow OS changes while the preference is "system".
    if (pref !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    mq.addEventListener('change', apply);
    return () => mq.removeEventListener('change', apply);
  }, [pref]);

  const setPref = useCallback((p: ThemePref) => {
    localStorage.setItem(STORAGE_KEY, p);
    setPrefState(p);
  }, []);

  const toggle = useCallback(() => {
    setPref(resolve(pref) === 'dark' ? 'light' : 'dark');
  }, [pref, setPref]);

  return <Ctx.Provider value={{ pref, resolved, setPref, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error('useTheme must be used within ThemeProvider');
  return c;
}
