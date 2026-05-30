import { FormEvent, useState } from 'react';
import { Radar } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { ThemeToggle } from '../components/ThemeToggle';

export function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed');
      setBusy(false);
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-topbar">
        <ThemeToggle />
      </div>

      <main className="auth-card">
        <div className="auth-brand">
          <span className="auth-mark"><Radar size={28} strokeWidth={2.2} /></span>
          <h1 className="auth-wordmark">ATL4S</h1>
          <p className="auth-tagline">Operator Console</p>
        </div>

        <form className="auth-form" onSubmit={onSubmit}>
          <label className="field">
            <span className="field-label">Username</span>
            <input
              className="input"
              value={username}
              autoFocus
              autoComplete="username"
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>

          <label className="field">
            <span className="field-label">Password</span>
            <input
              className="input"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="auth-foot">ATL4S · drone telemetry &amp; perception</p>
      </main>
    </div>
  );
}
