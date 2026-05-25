import { Fragment, useEffect, useState, type FormEvent } from 'react';
import { api, type Bag, type BagFile, type BagMetadata } from '../lib/api';
import { formatBytes, formatDate } from '../lib/format';

export function Bags() {
  const [bags, setBags] = useState<Bag[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [files, setFiles] = useState<Record<string, BagFile[]>>({});
  const [meta, setMeta] = useState<Record<string, BagMetadata | 'missing'>>({});

  const [uploadName, setUploadName] = useState('');
  const [uploadFiles, setUploadFiles] = useState<FileList | null>(null);
  const [uploading, setUploading] = useState(false);

  const refresh = async () => {
    try {
      setBags(await api.listBags());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const toggleExpand = async (name: string) => {
    if (expanded === name) {
      setExpanded(null);
      return;
    }
    setExpanded(name);
    if (!files[name]) {
      try {
        const list = await api.listFiles(name);
        setFiles((f) => ({ ...f, [name]: list }));
      } catch (e) {
        setError((e as Error).message);
      }
    }
    if (!meta[name]) {
      try {
        const m = await api.bagMetadata(name);
        setMeta((s) => ({ ...s, [name]: m }));
      } catch {
        // Older bags or non-ros2 prefixes won't have metadata.yaml.
        setMeta((s) => ({ ...s, [name]: 'missing' }));
      }
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete bag "${name}"? This is irreversible.`)) return;
    try {
      await api.deleteBag(name);
      setFiles((f) => {
        const next = { ...f };
        delete next[name];
        return next;
      });
      await refresh();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!uploadName || !uploadFiles || uploadFiles.length === 0) return;
    setUploading(true);
    try {
      await api.uploadFiles(uploadName, uploadFiles);
      setUploadName('');
      setUploadFiles(null);
      (e.target as HTMLFormElement).reset();
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <section>
      <div className="toolbar" style={{ justifyContent: 'flex-end', marginBottom: 12 }}>
        <button className="ghost" onClick={refresh}>Refresh</button>
      </div>

      {error && <p className="error">{error}</p>}

      <form className="upload-form" onSubmit={handleUpload}>
        <input
          type="text"
          placeholder="bag name (creates new prefix)"
          value={uploadName}
          onChange={(e) => setUploadName(e.target.value)}
          required
        />
        <input
          type="file"
          multiple
          onChange={(e) => setUploadFiles(e.target.files)}
          required
        />
        <button type="submit" disabled={uploading}>
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {bags === null ? (
        <p className="placeholder">Loading…</p>
      ) : bags.length === 0 ? (
        <p className="placeholder">No bags in GCS yet.</p>
      ) : (
        <table className="bags">
          <thead>
            <tr>
              <th>Name</th>
              <th>Size</th>
              <th>Files</th>
              <th>Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {bags.map((b) => (
              <Fragment key={b.name}>
                <tr>
                  <td>
                    <button className="link" onClick={() => toggleExpand(b.name)}>
                      <span className="caret">{expanded === b.name ? '▾' : '▸'}</span>
                      {b.name}
                    </button>
                  </td>
                  <td>{formatBytes(b.size_bytes)}</td>
                  <td>{b.files}</td>
                  <td>{formatDate(b.updated)}</td>
                  <td>
                    <button className="danger" onClick={() => handleDelete(b.name)}>
                      Delete
                    </button>
                  </td>
                </tr>
                {expanded === b.name && (
                  <tr className="files-row">
                    <td colSpan={5}>
                      <BagDetails name={b.name} files={files[b.name]} meta={meta[b.name]} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function BagDetails({
  name,
  files,
  meta,
}: {
  name: string;
  files: BagFile[] | undefined;
  meta: BagMetadata | 'missing' | undefined;
}) {
  return (
    <div className="bag-details">
      <div className="bag-meta">
        <h3>Metadata</h3>
        {meta === undefined ? (
          <p className="placeholder">Loading…</p>
        ) : meta === 'missing' ? (
          <p className="placeholder">No <code>metadata.yaml</code> in this bag.</p>
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

      <div className="bag-files">
        <h3>Files</h3>
        {files === undefined ? (
          <p className="placeholder">Loading…</p>
        ) : (
          <table className="files">
            <tbody>
              {files.map((f) => (
                <tr key={f.name}>
                  <td>{f.name}</td>
                  <td>{formatBytes(f.size_bytes)}</td>
                  <td>{formatDate(f.updated)}</td>
                  <td>
                    <a href={api.fileDownloadUrl(name, f.name)}>Download</a>
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
