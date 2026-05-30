import { useCallback, useEffect, useRef, useState } from 'react';
import { Box, Cpu, Info, ScanLine, Trash2, Upload, X } from 'lucide-react';
import { api, CrackInfo, MlInfo, ModelInfo, ModelStats } from '../../lib/api';
import { formatBytes, formatDateTime } from '../../lib/format';
import { Viewer3D } from '../../components/Viewer3D';

function fmt(n: number): string {
  return n.toLocaleString();
}

export function ModelsView() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selected, setSelected] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [stats, setStats] = useState<ModelStats | null>(null);
  const [panel, setPanel] = useState<'info' | 'ml' | null>('info');
  const [ml, setMl] = useState<MlInfo | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Crack overlay state.
  const [crack, setCrack] = useState<CrackInfo | null>(null);
  const [crackOn, setCrackOn] = useState(false);
  const [overlayUrl, setOverlayUrl] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const [detecting, setDetecting] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await api.inspector.listModels();
      setModels(r.models);
      setError(null);
      setSelected((cur) => {
        if (cur && r.models.some((m) => m.name === cur.name)) return cur;
        return r.models[0] ?? null;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load models');
    }
  }, []);

  useEffect(() => {
    load();
    api.inspector.mlPipelines().then(setMl).catch(() => undefined);
  }, [load]);

  // Poll whether crackseg is running (drives the Cracks toggle).
  useEffect(() => {
    let alive = true;
    const tick = () => api.crackseg.info().then((i) => alive && setCrack(i)).catch(() => undefined);
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Turn the overlay off if crackseg stops.
  useEffect(() => {
    if (crack && !crack.running) setCrackOn(false);
  }, [crack]);

  // Drop the overlay when the model changes or crack mode is toggled off.
  useEffect(() => {
    setMoving(false);
    setOverlayUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return null;
    });
  }, [selected?.name, crackOn]);

  const onMoving = useCallback(() => setMoving(true), []);

  const onCapture = useCallback((blob: Blob) => {
    setDetecting(true);
    api.crackseg
      .infer(blob)
      .then((mask) => {
        const url = URL.createObjectURL(mask);
        setOverlayUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
        setMoving(false);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Crack inference failed'))
      .finally(() => setDetecting(false));
  }, []);

  // Reset mesh stats whenever the selected model changes.
  useEffect(() => setStats(null), [selected?.name]);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError(null);
    setUploadPct(0);
    try {
      const info = await api.inspector.uploadModel(file, setUploadPct);
      await load();
      setSelected(info);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploadPct(null);
    }
  }

  async function remove(name: string) {
    try {
      await api.inspector.deleteModel(name);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
    }
  }

  return (
    <>
      {error && <div className="banner err">{error}</div>}

      <div className="insp-body">
        <div className="insp-rail">
          <div className="insp-rail-head">
            <input
              ref={fileRef}
              type="file"
              className="hidden-input"
              accept=".fbx,.glb,.gltf,.obj,.stl,.ply"
              onChange={onFile}
            />
            <button className="btn btn-primary xs" onClick={() => fileRef.current?.click()} disabled={uploadPct !== null}>
              <Upload size={14} />
              {uploadPct !== null ? `Uploading… ${uploadPct}%` : 'Upload model'}
            </button>
          </div>

          <div className="insp-rail-list">
            {models.length === 0 ? (
              <div className="insp-rail-empty">No models yet. Upload an FBX/GLB to view it.</div>
            ) : (
              models.map((m) => (
                <div
                  key={m.name}
                  className={`insp-row${selected?.name === m.name ? ' active' : ''}`}
                  onClick={() => setSelected(m)}
                >
                  <Box size={16} />
                  <span className="insp-row-meta">
                    <span className="insp-row-name">{m.name}</span>
                    <span className="insp-row-sub">
                      {m.ext.toUpperCase()} · {formatBytes(m.size_bytes)}
                    </span>
                  </span>
                  <button
                    className="icon-btn sm"
                    title="Delete"
                    aria-label={`Delete ${m.name}`}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      remove(m.name);
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="insp-stage">
          <Viewer3D
            url={selected ? api.inspector.modelFileUrl(selected.name) : null}
            ext={selected?.ext ?? ''}
            onStats={setStats}
            crackEnabled={crackOn}
            onCapture={onCapture}
            onMoving={onMoving}
          />

          {crackOn && overlayUrl && !moving && <img className="crack-overlay" src={overlayUrl} alt="" />}
          {crackOn && detecting && (
            <div className="crack-status">
              <span className="spinner" /> Detecting cracks…
            </div>
          )}

          {selected && (
            <div className="insp-toolbar">
              <span className="insp-name">{selected.name}</span>
              <div className="insp-toolbar-spacer" />
              <button
                className={`btn btn-ghost xs${crackOn ? ' on' : ''}`}
                disabled={!crack?.running}
                title={crack?.running ? 'Overlay detected cracks (CrackSeg)' : 'Start CrackSeg in Pipelines to enable'}
                onClick={() => setCrackOn((o) => !o)}
              >
                <ScanLine size={14} /> Cracks
              </button>
              <button
                className={`btn btn-ghost xs${panel === 'info' ? ' on' : ''}`}
                onClick={() => setPanel((p) => (p === 'info' ? null : 'info'))}
              >
                <Info size={14} /> Info
              </button>
              <button
                className={`btn btn-ghost xs${panel === 'ml' ? ' on' : ''}`}
                onClick={() => setPanel((p) => (p === 'ml' ? null : 'ml'))}
              >
                <Cpu size={14} /> ML
              </button>
            </div>
          )}

          {selected && panel === 'info' && (
            <div className="insp-panel">
              <button className="icon-btn sm insp-panel-close" onClick={() => setPanel(null)} aria-label="Close">
                <X size={15} />
              </button>
              <h3>Metadata</h3>
              <div className="kv">
                <div className="kv-row"><span className="kv-label">File</span><span className="kv-value mono">{selected.name}</span></div>
                <div className="kv-row"><span className="kv-label">Format</span><span className="kv-value">{selected.ext.toUpperCase()}</span></div>
                <div className="kv-row"><span className="kv-label">Size</span><span className="kv-value">{formatBytes(selected.size_bytes)}</span></div>
                <div className="kv-row"><span className="kv-label">Modified</span><span className="kv-value">{formatDateTime(new Date(selected.modified * 1000).toISOString())}</span></div>
                {stats ? (
                  <>
                    <div className="kv-row"><span className="kv-label">Meshes</span><span className="kv-value">{fmt(stats.meshes)}</span></div>
                    <div className="kv-row"><span className="kv-label">Vertices</span><span className="kv-value">{fmt(stats.vertices)}</span></div>
                    <div className="kv-row"><span className="kv-label">Triangles</span><span className="kv-value">{fmt(stats.triangles)}</span></div>
                    <div className="kv-row"><span className="kv-label">Bounds</span><span className="kv-value mono">{stats.size.map((s) => s.toFixed(2)).join(' × ')}</span></div>
                  </>
                ) : (
                  <div className="kv-row"><span className="kv-label">Geometry</span><span className="kv-value muted">computing…</span></div>
                )}
              </div>
            </div>
          )}

          {selected && panel === 'ml' && (
            <div className="insp-panel">
              <button className="icon-btn sm insp-panel-close" onClick={() => setPanel(null)} aria-label="Close">
                <X size={15} />
              </button>
              <span className="empty-badge">Coming soon</span>
              <h3>ML pipelines</h3>
              <p className="muted">{ml?.message ?? 'Run a model live on the geometry in view.'}</p>
              <div className="ml-empty">No pipelines available for this model yet.</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
