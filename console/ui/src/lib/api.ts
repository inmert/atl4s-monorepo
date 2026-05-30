// The single seam between the design layer and the logic layer (the console
// FastAPI backend on the same origin). Every backend call goes through here, so
// pages never touch fetch directly.

export interface AuthState {
  authenticated: boolean;
  username: string | null;
  auth_required: boolean;
}

export type Level = 'ok' | 'warn' | 'err' | 'idle';

export interface ContainerSummary {
  name: string;
  service: string | null;
  state: string;
  health: string | null;
  level: Level;
  image: string | null;
  started_at: string | null;
  uptime_sec: number | null;
  restart_count: number;
}

export interface ContainerMount {
  source: string | null;
  destination: string | null;
  mode: string | null;
  rw: boolean | null;
}

export interface EnvVar {
  key: string;
  value: string;
  from_image: boolean;
}

export interface ContainerDetail extends ContainerSummary {
  id: string;
  created: string | null;
  command: string | null;
  restart_policy: string | null;
  network_mode: string | null;
  networks: string[];
  ports: string[];
  mounts: ContainerMount[];
  env: EnvVar[];
  compose_project: string | null;
  exit_code: number | null;
  state_error: string | null;
}

export interface StatsFrame {
  cpu_percent: number;
  mem_bytes: number;
  mem_limit: number;
  mem_percent: number;
}

export type ContainerAction = 'start' | 'stop' | 'restart';

export type DeploymentType = 'drone' | 'rover' | 'sensor';
export type DeploymentMode = 'simulator' | 'real';
export type DeploymentStatus = 'online' | 'offline' | 'degraded';

// What the form submits (everything except the server-assigned id + derived
// status). telemetry is carried through unchanged so edits don't drop it.
export interface DeploymentInput {
  name: string;
  type: DeploymentType;
  mode: DeploymentMode;
  protocol: string;
  host: string;
  port: number;
  description: string;
  containers: string[];
  telemetry: Record<string, string>;
}

export interface Deployment extends DeploymentInput {
  id: string;
  status: DeploymentStatus;
}

export interface DeploymentOptions {
  types: DeploymentType[];
  modes: DeploymentMode[];
  protocols: string[];
}

async function jsonOrThrow(res: Response): Promise<unknown> {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = (data as { detail?: string })?.detail;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data;
}

// Build a same-origin ws:// or wss:// URL for the streaming endpoints. The
// session cookie rides along on the upgrade automatically.
export function wsUrl(path: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}${path}`;
}

export const api = {
  async me(): Promise<AuthState> {
    return jsonOrThrow(await fetch('/api/auth/me', { credentials: 'same-origin' })) as Promise<AuthState>;
  },

  async login(username: string, password: string): Promise<AuthState> {
    return jsonOrThrow(
      await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password }),
      }),
    ) as Promise<AuthState>;
  },

  async logout(): Promise<void> {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
  },

  async listContainers(): Promise<{ available: boolean; containers: ContainerSummary[] }> {
    return jsonOrThrow(
      await fetch('/api/containers', { credentials: 'same-origin' }),
    ) as Promise<{ available: boolean; containers: ContainerSummary[] }>;
  },

  async getContainer(name: string): Promise<ContainerDetail> {
    return jsonOrThrow(
      await fetch(`/api/containers/${encodeURIComponent(name)}`, { credentials: 'same-origin' }),
    ) as Promise<ContainerDetail>;
  },

  async containerAction(name: string, action: ContainerAction): Promise<ContainerSummary> {
    return jsonOrThrow(
      await fetch(`/api/containers/${encodeURIComponent(name)}/${action}`, {
        method: 'POST',
        credentials: 'same-origin',
      }),
    ) as Promise<ContainerSummary>;
  },

  async setContainerEnv(name: string, env: Record<string, string>): Promise<ContainerDetail> {
    return jsonOrThrow(
      await fetch(`/api/containers/${encodeURIComponent(name)}/env`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ env }),
      }),
    ) as Promise<ContainerDetail>;
  },

  deployments: {
    async list(): Promise<{ deployments: Deployment[]; options: DeploymentOptions }> {
      return jsonOrThrow(
        await fetch('/api/deployments', { credentials: 'same-origin' }),
      ) as Promise<{ deployments: Deployment[]; options: DeploymentOptions }>;
    },

    async create(input: DeploymentInput): Promise<Deployment> {
      return jsonOrThrow(
        await fetch('/api/deployments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(input),
        }),
      ) as Promise<Deployment>;
    },

    async update(id: string, input: DeploymentInput): Promise<Deployment> {
      return jsonOrThrow(
        await fetch(`/api/deployments/${encodeURIComponent(id)}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify(input),
        }),
      ) as Promise<Deployment>;
    },

    async remove(id: string): Promise<void> {
      await jsonOrThrow(
        await fetch(`/api/deployments/${encodeURIComponent(id)}`, {
          method: 'DELETE',
          credentials: 'same-origin',
        }),
      );
    },
  },
};

// Same-origin URL for the streaming log download (cookie auth rides along).
export function logsDownloadUrl(name: string): string {
  return `/api/containers/${encodeURIComponent(name)}/logs/download?tail=all`;
}
