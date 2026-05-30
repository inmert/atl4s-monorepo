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

export interface ModelInfo {
  name: string;
  ext: string;
  size_bytes: number;
  modified: number;
}

export interface MlInfo {
  supported: boolean;
  pipelines: string[];
  message: string;
}

// Mesh-level metadata, computed in the viewer once a model loads.
export interface ModelStats {
  meshes: number;
  vertices: number;
  triangles: number;
  size: [number, number, number];
}

export interface RosbagInfo {
  name: string;
  size_bytes?: number;
  size_mib?: number;
  files?: number;
  updated?: string;
}

export interface RosbagTopic {
  name: string;
  type: string;
  message_count: number;
}

export interface RosbagMeta {
  duration_sec: number;
  message_count: number;
  topics: RosbagTopic[];
}

export type ReplayState = 'idle' | 'downloading' | 'playing' | 'stopping';

export interface ReplayStatus {
  state: ReplayState;
  bag: string | null;
  started_at?: number | null;
}

export type PipelineFieldType = 'select' | 'slider' | 'number' | 'string' | 'boolean' | 'color';

export interface PipelineField {
  key: string;
  label: string;
  type: PipelineFieldType;
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  default?: unknown;
}

export type PipelineStatus = 'running' | 'stopped' | 'not_deployed';
export type PipelineAction = 'start' | 'stop' | 'restart';

export interface Pipeline {
  id: string;
  name: string;
  container: string;
  description: string;
  fields: PipelineField[];
  status: PipelineStatus;
  config: Record<string, unknown>;
}

export interface CrackInfo {
  running: boolean;
  device?: string;
  model_variant?: string;
  status?: string;
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

  inspector: {
    async listModels(): Promise<{ models: ModelInfo[]; allowed_ext?: string[] }> {
      return jsonOrThrow(
        await fetch('/api/inspector/models', { credentials: 'same-origin' }),
      ) as Promise<{ models: ModelInfo[]; allowed_ext?: string[] }>;
    },

    // XHR (not fetch) so we can report upload progress for large models.
    uploadModel(file: File, onProgress?: (pct: number) => void): Promise<ModelInfo> {
      return new Promise((resolve, reject) => {
        const form = new FormData();
        form.append('file', file);
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/inspector/models');
        xhr.withCredentials = true;
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
        };
        xhr.onload = () => {
          let data: { detail?: string } = {};
          try {
            data = JSON.parse(xhr.responseText);
          } catch {
            /* non-JSON response */
          }
          if (xhr.status >= 200 && xhr.status < 300) resolve(data as ModelInfo);
          else reject(new Error(data?.detail || `Upload failed (${xhr.status})`));
        };
        xhr.onerror = () => reject(new Error('Upload failed'));
        xhr.send(form);
      });
    },

    async deleteModel(name: string): Promise<void> {
      await jsonOrThrow(
        await fetch(`/api/inspector/models/${encodeURIComponent(name)}`, {
          method: 'DELETE',
          credentials: 'same-origin',
        }),
      );
    },

    modelFileUrl(name: string): string {
      return `/api/inspector/models/${encodeURIComponent(name)}/file`;
    },

    async mlPipelines(): Promise<MlInfo> {
      return jsonOrThrow(
        await fetch('/api/inspector/ml/pipelines', { credentials: 'same-origin' }),
      ) as Promise<MlInfo>;
    },

    async listRosbags(): Promise<{ supported: boolean; bags: RosbagInfo[] }> {
      return jsonOrThrow(
        await fetch('/api/inspector/rosbags', { credentials: 'same-origin' }),
      ) as Promise<{ supported: boolean; bags: RosbagInfo[] }>;
    },

    async rosbagMetadata(name: string): Promise<RosbagMeta> {
      return jsonOrThrow(
        await fetch(`/api/inspector/rosbags/${encodeURIComponent(name)}/metadata`, {
          credentials: 'same-origin',
        }),
      ) as Promise<RosbagMeta>;
    },

    async rosbagStatus(): Promise<ReplayStatus> {
      return jsonOrThrow(
        await fetch('/api/inspector/rosbags/status', { credentials: 'same-origin' }),
      ) as Promise<ReplayStatus>;
    },

    async playRosbag(name: string): Promise<void> {
      await jsonOrThrow(
        await fetch(`/api/inspector/rosbags/${encodeURIComponent(name)}/play`, {
          method: 'POST',
          credentials: 'same-origin',
        }),
      );
    },

    async stopRosbag(): Promise<void> {
      await jsonOrThrow(
        await fetch('/api/inspector/rosbags/stop', { method: 'POST', credentials: 'same-origin' }),
      );
    },
  },

  pipelines: {
    async list(): Promise<{ pipelines: Pipeline[] }> {
      return jsonOrThrow(
        await fetch('/api/pipelines', { credentials: 'same-origin' }),
      ) as Promise<{ pipelines: Pipeline[] }>;
    },

    async updateConfig(id: string, config: Record<string, unknown>): Promise<Pipeline> {
      return jsonOrThrow(
        await fetch(`/api/pipelines/${encodeURIComponent(id)}/config`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ config }),
        }),
      ) as Promise<Pipeline>;
    },

    async action(id: string, action: PipelineAction): Promise<Pipeline> {
      return jsonOrThrow(
        await fetch(`/api/pipelines/${encodeURIComponent(id)}/${action}`, {
          method: 'POST',
          credentials: 'same-origin',
        }),
      ) as Promise<Pipeline>;
    },
  },

  crackseg: {
    async info(): Promise<CrackInfo> {
      return jsonOrThrow(
        await fetch('/api/crackseg/info', { credentials: 'same-origin' }),
      ) as Promise<CrackInfo>;
    },

    // POST the rendered frame; get an RGBA crack-mask PNG back.
    async infer(blob: Blob): Promise<Blob> {
      const res = await fetch('/api/crackseg/infer', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'image/png' },
        body: blob,
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(d.detail || `inference failed (${res.status})`);
      }
      return res.blob();
    },
  },
};

// Same-origin URL for the streaming log download (cookie auth rides along).
export function logsDownloadUrl(name: string): string {
  return `/api/containers/${encodeURIComponent(name)}/logs/download?tail=all`;
}
