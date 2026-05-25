// Rosbag Manager — single surface for record / browse / replay / upload.
//
// Replaces the phase-1 Subnav wrapper around three separate pages with one
// unified table that lists every bag (local + GCS) and exposes per-row
// actions inline. Active record / replay state lives in a persistent strip
// at the top so it never falls off-screen while browsing.
//
// Backend contract (proxied via /api/* → rosbag-manager):
//   /api/bags                — GCS bag list
//   /api/uploads             — local bag stage state (uploaded / in_flight)
//   /api/record/{start,stop,status}
//   /api/replay/{start,stop,status}
//   /api/bags/{name}/{metadata,files,upload,…}

import { Fragment, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import {
  Disc,
  Download,
  ExternalLink,
  Play,
  RefreshCw,
  Square,
  Trash2,
  Upload as UploadIcon,
  UploadCloud,
  X,
} from 'lucide-react';
import {
  api,
  type Bag,
  type BagFile,
  type BagMetadata,
  type LocalBag,
  type RecordStatus,
  type ReplayStatus,
} from '../lib/api';
import { formatBytes, formatDate } from '../lib/format';
import { foxgloveStudioUrl } from '../lib/foxglove';
import { Badge, Card, EmptyState, PageHeader, StatusDot } from '../lib/components';

const POLL_MS = 3000;

type UnifiedRow =
  | { kind: 'gcs'; name: string; bag: Bag; local?: LocalBag }
  | { kind: 'local'; name: string; local: LocalBag };

function combine(bags: Bag[], locals: LocalBag[]): UnifiedRow[] {
  const localByName = new Map(locals.map((l) => [l.name, l]));
  const rows: UnifiedRow[] = [];

  // GCS bags first (newest first, by `updated`).
  const sortedBags = [...bags].sort((a, b) =>
    (b.updated || '').localeCompare(a.updated || ''),
  );
  for (const b of sortedBags) {
    rows.push({ kind: 'gcs', name: b.name, bag: b, local: localByName.get(b.name) });
    localByName.delete(b.name);
  }

  // Then local-only bags (recording, pending upload, or uploading).
  const sortedLocals = [...localByName.values()].sort((a, b) =>
    (b.mtime || '').localeCompare(a.mtime || ''),
  );
  for (const l of sortedLocals) {
    // Uploaded-but-not-in-GCS-listing shouldn't really happen, but if it does
    // we surface it so the user can investigate.
    rows.push({ kind: 'local', name: l.name, local: l });
  }

  return rows;
}

export function RosbagManager() {
  const [bags, setBags] = useState<Bag[] | null>(null);
  const [locals, setLocals] = useState<LocalBag[] | null>(null);
  const [recordStatus, setRecordStatus] = useState<RecordStatus | null>(null);
  const [replayStatus, setReplayStatus] = useState<ReplayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [recordOpen, setRecordOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [meta, setMeta] = useState<Record<string, BagMetadata | 'missing'>>({});
  const [files, setFiles] = useState<Record<string, BagFile[]>>({});

  const refresh = async () => {
    try {
      const [b, l, rs, ps] = await Promise.all([
        api.listBags(),
        api.listLocal(),
        api.recordStatus(),
        api.replayStatus(),
      ]);
      setBags(b);
      setLocals(l);
      setRecordStatus(rs);
      setReplayStatus(ps);
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

  const rows = useMemo(() => combine(bags || [], locals || []), [bags, locals]);

  const onExpand = async (name: string) => {
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    if (!files[name]) {
      try {
        const list = await api.listFiles(name);
        setFiles((s) => ({ ...s, [name]: list }));
      } catch {
        // Local-only bag — files endpoint isn't available, just skip.
      }
    }
    if (!meta[name]) {
      try {
        const m = await api.bagMetadata(name);
        setMeta((s) => ({ ...s, [name]: m }));
      } catch {
        setMeta((s) => ({ ...s, [name]: 'missing' }));
      }
    }
  };

  const onDelete = async (name: string) => {
    if (!confirm(`Delete bag "${name}" from GCS? This is irreversible.`)) return;
    try {
      await api.deleteBag(name);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onForceUpload = async (name: string) => {
    try {
      await api.forceUpload(name);
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onReplayStart = async (name: string) => {
    try {
      const s = await api.replayStart(name);
      setReplayStatus(s);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onReplayStop = async () => {
    try {
      const s = await api.replayStop();
      setReplayStatus(s);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const onRecordStop = async () => {
    try {
      const s = await api.recordStop();
      setRecordStatus(s);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const recording = recordStatus?.state === 'recording';
  const replayBusy = replayStatus && replayStatus.state !== 'idle';

  return (
    <section>
      <PageHeader
        title="Rosbag Manager"
        subtitle={
          bags === null
            ? 'Loading…'
            : `${bags.length} in GCS · ${(locals || []).filter((l) => !l.uploaded).length} local pending`
        }
        right={
          <>
            <button
              className="ghost"
              onClick={() => setUploadOpen(true)}
              title="Upload local files into a GCS bag prefix"
            >
              <UploadIcon size={14} style={{ marginRight: 4 }} />
              Upload
            </button>
            <button
              onClick={() => setRecordOpen(true)}
              disabled={recording}
              title={recording ? 'A recording is already active' : 'Start a new recording'}
            >
              <Disc size={14} style={{ marginRight: 4 }} />
              New Recording
            </button>
            <button className="ghost" onClick={refresh} title="Refresh">
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      {error && <p className="error">{error}</p>}

      <ActiveStrip
        recordStatus={recordStatus}
        replayStatus={replayStatus}
        onRecordStop={onRecordStop}
        onReplayStop={onReplayStop}
      />

      {rows.length === 0 ? (
        <EmptyState icon={Disc} title="No bags yet">
          Start a recording with <strong>New Recording</strong> above, or upload local
          files into a GCS prefix with <strong>Upload</strong>.
        </EmptyState>
      ) : (
        <Card className="flush">
          <table className="bags">
            <thead>
              <tr>
                <th>Name</th>
                <th>Size</th>
                <th>Files</th>
                <th>Updated</th>
                <th>Where</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.name}>
                  <BagRow
                    row={r}
                    expanded={expanded === r.name}
                    onExpand={() => onExpand(r.name)}
                    onDelete={() => onDelete(r.name)}
                    onForceUpload={() => onForceUpload(r.name)}
                    onReplayStart={() => onReplayStart(r.name)}
                    onReplayStop={onReplayStop}
                    onRecordStop={onRecordStop}
                    isRecording={recording && recordStatus?.name === r.name}
                    isReplaying={Boolean(replayBusy && replayStatus?.bag === r.name)}
                    replayBusy={Boolean(replayBusy)}
                  />
                  {expanded === r.name && (
                    <tr className="files-row">
                      <td colSpan={6}>
                        <BagDetails
                          name={r.name}
                          meta={meta[r.name]}
                          files={files[r.name]}
                          isLocal={r.kind === 'local'}
                        />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {recordOpen && (
        <RecordModal
          onClose={() => setRecordOpen(false)}
          onStarted={async () => {
            setRecordOpen(false);
            await refresh();
          }}
        />
      )}

      {uploadOpen && (
        <UploadModal
          onClose={() => setUploadOpen(false)}
          onUploaded={async () => {
            setUploadOpen(false);
            await refresh();
          }}
        />
      )}
    </section>
  );
}

function ActiveStrip({
  recordStatus,
  replayStatus,
  onRecordStop,
  onReplayStop,
}: {
  recordStatus: RecordStatus | null;
  replayStatus: ReplayStatus | null;
  onRecordStop: () => void;
  onReplayStop: () => void;
}) {
  const recording = recordStatus?.state === 'recording';
  const stoppingRec = recordStatus?.state === 'stopping';
  const replayBusy = replayStatus && replayStatus.state !== 'idle';
  if (!recording && !stoppingRec && !replayBusy) return null;

  return (
    <div className="grid grid-2" style={{ marginBottom: 20 }}>
      {(recording || stoppingRec) && (
        <div className="active-strip">
          <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
            <StatusDot tone="err" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="active-title">
                {stoppingRec ? 'Stopping recording…' : 'Recording'}
              </div>
              <div className="dim mono" style={{ fontSize: 12, marginTop: 2 }}>
                {recordStatus?.name || '—'}
              </div>
              <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                started {recordStatus?.started_at ? formatDate(recordStatus.started_at) : '—'}{' '}
                · {recordStatus?.topics?.length ?? 0} topics
              </div>
            </div>
            <button className="danger" onClick={onRecordStop} disabled={stoppingRec}>
              <Square size={14} style={{ marginRight: 4 }} />
              Stop
            </button>
          </div>
        </div>
      )}
      {replayBusy && (
        <div className="active-strip">
          <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
            <StatusDot tone="accent" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="active-title">
                {replayStatus?.state === 'downloading'
                  ? 'Downloading bag…'
                  : replayStatus?.state === 'stopping'
                    ? 'Stopping replay…'
                    : 'Replaying'}
              </div>
              <div className="dim mono" style={{ fontSize: 12, marginTop: 2 }}>
                {replayStatus?.bag || '—'}
              </div>
              <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                started {replayStatus?.started_at ? formatDate(replayStatus.started_at) : '—'}
              </div>
              {replayStatus?.state === 'playing' && (
                <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                  <a
                    className="foxglove-link"
                    href={foxgloveStudioUrl()}
                    target="_blank"
                    rel="noreferrer"
                    style={{ marginTop: 6, display: 'inline-flex' }}
                  >
                    View in Foxglove <ExternalLink size={12} style={{ marginLeft: 4 }} />
                  </a>
                </div>
              )}
            </div>
            <button
              className="danger"
              onClick={onReplayStop}
              disabled={replayStatus?.state === 'stopping'}
            >
              <Square size={14} style={{ marginRight: 4 }} />
              Stop
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function BagRow({
  row,
  expanded,
  onExpand,
  onDelete,
  onForceUpload,
  onReplayStart,
  onReplayStop,
  onRecordStop,
  isRecording,
  isReplaying,
  replayBusy,
}: {
  row: UnifiedRow;
  expanded: boolean;
  onExpand: () => void;
  onDelete: () => void;
  onForceUpload: () => void;
  onReplayStart: () => void;
  onReplayStop: () => void;
  onRecordStop: () => void;
  isRecording: boolean;
  isReplaying: boolean;
  replayBusy: boolean;
}) {
  const isGcs = row.kind === 'gcs';
  const local = isGcs ? row.local : row.local;
  const bag = isGcs ? row.bag : null;

  const size = bag ? bag.size_bytes : (local?.size_bytes ?? 0);
  const files = bag ? bag.files : (local?.files ?? 0);
  const updated = bag ? bag.updated : (local?.mtime ?? null);

  let where: ReactNode;
  if (isGcs) {
    if (isReplaying) where = <Badge tone="accent"><StatusDot tone="accent" />Replaying</Badge>;
    else if (local && local.in_flight) where = <Badge tone="warn">Uploading + in GCS</Badge>;
    else where = <Badge tone="ok"><StatusDot tone="ok" />GCS</Badge>;
  } else {
    if (isRecording) where = <Badge tone="err"><StatusDot tone="err" />Recording</Badge>;
    else if (local?.in_flight) where = <Badge tone="warn"><StatusDot tone="warn" />Uploading</Badge>;
    else if (local?.uploaded) where = <Badge tone="ok">Uploaded (local stub)</Badge>;
    else where = <Badge tone="idle">Local · pending</Badge>;
  }

  return (
    <tr>
      <td>
        <button className="link" onClick={onExpand}>
          <span className="caret">{expanded ? '▾' : '▸'}</span>
          {row.name}
        </button>
      </td>
      <td>{formatBytes(size)}</td>
      <td>{files}</td>
      <td className="dim">{updated ? formatDate(updated) : '—'}</td>
      <td>{where}</td>
      <td style={{ textAlign: 'right' }}>
        <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
          {isGcs && !isReplaying && (
            <button
              className="ghost"
              onClick={onReplayStart}
              disabled={replayBusy}
              title={replayBusy ? 'Another replay is active' : 'Replay this bag'}
            >
              <Play size={13} style={{ marginRight: 4 }} />
              Replay
            </button>
          )}
          {isGcs && isReplaying && (
            <button className="danger" onClick={onReplayStop}>
              <Square size={13} style={{ marginRight: 4 }} />
              Stop replay
            </button>
          )}
          {!isGcs && isRecording && (
            <button className="danger" onClick={onRecordStop}>
              <Square size={13} style={{ marginRight: 4 }} />
              Stop
            </button>
          )}
          {!isGcs && !isRecording && local && !local.uploaded && !local.in_flight && (
            <button className="ghost" onClick={onForceUpload}>
              <UploadCloud size={13} style={{ marginRight: 4 }} />
              Upload now
            </button>
          )}
          {isGcs && (
            <button
              className="danger"
              onClick={onDelete}
              disabled={isReplaying}
              title={isReplaying ? 'Stop the replay first' : 'Delete from GCS'}
            >
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

function BagDetails({
  name,
  meta,
  files,
  isLocal,
}: {
  name: string;
  meta: BagMetadata | 'missing' | undefined;
  files: BagFile[] | undefined;
  isLocal: boolean;
}) {
  return (
    <div className="bag-details">
      <div>
        <h3>Metadata</h3>
        {meta === undefined ? (
          <p className="placeholder">Loading…</p>
        ) : meta === 'missing' ? (
          <p className="placeholder">
            No <code>metadata.yaml</code> in this bag.
          </p>
        ) : (
          <>
            <div className="meta-row">
              <span>{meta.duration_sec.toFixed(2)} s</span>
              <span>{meta.message_count?.toLocaleString() ?? '—'} messages</span>
              <span>{meta.topics.length} topics</span>
              <span>{meta.storage_identifier || '—'}</span>
            </div>
            <table className="files">
              <thead>
                <tr>
                  <th>Topic</th>
                  <th>Type</th>
                  <th>Messages</th>
                </tr>
              </thead>
              <tbody>
                {meta.topics.map((t) => (
                  <tr key={t.name || Math.random()}>
                    <td>{t.name}</td>
                    <td><code>{t.type}</code></td>
                    <td>{t.message_count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div>
        <h3>Files</h3>
        {isLocal ? (
          <p className="placeholder">
            Local bag — files become listable in GCS once uploaded.
          </p>
        ) : files === undefined ? (
          <p className="placeholder">Loading…</p>
        ) : files.length === 0 ? (
          <p className="placeholder">No files reported.</p>
        ) : (
          <table className="files">
            <tbody>
              {files.map((f) => (
                <tr key={f.name}>
                  <td>{f.name}</td>
                  <td>{formatBytes(f.size_bytes)}</td>
                  <td>{formatDate(f.updated)}</td>
                  <td>
                    <a href={api.fileDownloadUrl(name, f.name)}>
                      <Download size={13} style={{ verticalAlign: 'middle' }} />
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function Modal({
  title,
  onClose,
  children,
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="ghost icon-only" onClick={onClose} title="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function RecordModal({
  onClose,
  onStarted,
}: {
  onClose: () => void;
  onStarted: () => void;
}) {
  const [name, setName] = useState('');
  const [topicsText, setTopicsText] = useState('');
  const [duration, setDuration] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      const body: { name?: string; topics?: string[]; duration?: number } = {};
      if (name.trim()) body.name = name.trim();
      const topics = topicsText
        .split(/[\s,]+/)
        .map((t) => t.trim())
        .filter((t) => t.length > 0);
      if (topics.length) body.topics = topics;
      if (duration.trim()) {
        const d = Number(duration);
        if (!Number.isNaN(d) && d > 0) body.duration = d;
      }
      await api.recordStart(body);
      onStarted();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="New recording" onClose={onClose}>
      <form className="form-card" onSubmit={submit} style={{ boxShadow: 'none', padding: 0 }}>
        {err && <p className="error">{err}</p>}
        <label>
          <span>Bag name</span>
          <input
            type="text"
            placeholder="auto-generated if blank"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          <span>Topics (space- or newline-separated; blank = server default)</span>
          <textarea
            rows={3}
            placeholder="/mavros/state /mavros/battery /camera/image …"
            value={topicsText}
            onChange={(e) => setTopicsText(e.target.value)}
          />
        </label>
        <label>
          <span>Duration in seconds (blank = manual stop)</span>
          <input
            type="number"
            min={1}
            placeholder="30"
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
          />
        </label>
        <div className="form-actions">
          <button type="submit" disabled={submitting}>
            <Disc size={13} style={{ marginRight: 4 }} />
            Start recording
          </button>
          <button type="button" className="ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

function UploadModal({
  onClose,
  onUploaded,
}: {
  onClose: () => void;
  onUploaded: () => void;
}) {
  const [name, setName] = useState('');
  const [files, setFiles] = useState<FileList | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !files || files.length === 0) return;
    setSubmitting(true);
    setErr(null);
    try {
      await api.uploadFiles(name.trim(), files);
      onUploaded();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal title="Upload to GCS" onClose={onClose}>
      <form className="form-card" onSubmit={submit} style={{ boxShadow: 'none', padding: 0 }}>
        {err && <p className="error">{err}</p>}
        <label>
          <span>GCS bag prefix (will be created)</span>
          <input
            type="text"
            placeholder="e.g. flight-2026-05-25"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </label>
        <label>
          <span>Files</span>
          <input
            type="file"
            multiple
            onChange={(e) => setFiles(e.target.files)}
            required
          />
        </label>
        <div className="form-actions">
          <button type="submit" disabled={submitting || !name.trim() || !files?.length}>
            <UploadCloud size={13} style={{ marginRight: 4 }} />
            {submitting ? 'Uploading…' : 'Upload'}
          </button>
          <button type="button" className="ghost" onClick={onClose}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

