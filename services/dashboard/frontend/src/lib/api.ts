// Typed wrappers around the dashboard backend (robot registry) and the
// proxied rosbag-manager API.

export type RobotKind = 'simulator' | 'drone' | 'rover' | string;
export type RobotIcon = 'simulator' | 'drone' | 'rover' | 'bot' | string;

export type Robot = {
  id: string;
  name: string;
  kind: RobotKind;
  icon: RobotIcon;
  telemetry: Partial<{
    state: string;
    battery: string;
    imu: string;
    gps: string;
    camera: string;
  }>;
};

export type RosEndpoint = { node: string; qos: string };

export type RosTopic = {
  name: string;
  types: string[];
  pub_count: number;
  sub_count: number;
  pubs: RosEndpoint[];
  subs: RosEndpoint[];
};

export type Bag = {
  name: string;
  size_bytes: number;
  size_mib: number;
  files: number;
  updated: string | null;
};

export type BagFile = {
  name: string;
  size_bytes: number;
  updated: string | null;
};

export type BagTopic = {
  name: string | null;
  type: string | null;
  serialization_format: string | null;
  message_count: number;
};

export type BagMetadata = {
  bag: string;
  storage_identifier: string | null;
  version: number | null;
  duration_sec: number;
  starting_time_sec: number | null;
  message_count: number | null;
  topics: BagTopic[];
};

export type RecordStatus = {
  state: 'idle' | 'recording' | 'stopping';
  name: string | null;
  topics: string[] | null;
  output: string | null;
  started_at: string | null;
};

export type ReplayStatus = {
  state: 'idle' | 'downloading' | 'playing' | 'stopping';
  bag: string | null;
  started_at: string | null;
};

export type LocalBag = {
  name: string;
  size_bytes: number;
  files: number;
  mtime: string | null;
  uploaded: boolean;
  in_flight: boolean;
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // body wasn't JSON; keep the status line
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function bagPath(name: string): string {
  return `/api/bags/${encodeURIComponent(name)}`;
}

export const api = {
  // Robots
  listRobots: () => request<Robot[]>('/api/robots'),
  getRobot: (id: string) => request<Robot>(`/api/robots/${encodeURIComponent(id)}`),

  // ROS topic graph
  listRosTopics: () => request<RosTopic[]>('/api/ros/topics'),

  listBags: () => request<Bag[]>('/api/bags'),
  listFiles: (name: string) => request<BagFile[]>(`${bagPath(name)}/files`),
  bagMetadata: (name: string) => request<BagMetadata>(`${bagPath(name)}/metadata`),
  deleteBag: async (name: string) => {
    const res = await fetch(bagPath(name), { method: 'DELETE' });
    if (!res.ok) {
      let detail = `${res.status} ${res.statusText}`;
      try {
        const body = await res.json();
        if (body?.detail) detail = body.detail;
      } catch {}
      throw new Error(detail);
    }
    return res.json();
  },
  uploadFiles: async (name: string, files: FileList) => {
    const fd = new FormData();
    for (const f of Array.from(files)) fd.append('files', f);
    const res = await fetch(`${bagPath(name)}/upload`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(`upload failed: ${res.status}`);
    return res.json();
  },
  fileDownloadUrl: (bag: string, file: string) =>
    `${bagPath(bag)}/files/${file.split('/').map(encodeURIComponent).join('/')}`,

  // Local bags + upload watcher
  listLocal: () => request<LocalBag[]>('/api/uploads'),
  forceUpload: (name: string) =>
    request<{ name: string; files_uploaded: number }>(
      `/api/uploads/${encodeURIComponent(name)}`,
      { method: 'POST' },
    ),

  // Record
  recordStatus: () => request<RecordStatus>('/api/record/status'),
  recordStart: (body: { name?: string; topics?: string[]; duration?: number }) =>
    request<RecordStatus>('/api/record/start', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  recordStop: () => request<RecordStatus>('/api/record/stop', { method: 'POST' }),

  // Replay
  replayStatus: () => request<ReplayStatus>('/api/replay/status'),
  replayStart: (bag: string) =>
    request<ReplayStatus>('/api/replay/start', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ bag }),
    }),
  replayStop: () => request<ReplayStatus>('/api/replay/stop', { method: 'POST' }),
};
