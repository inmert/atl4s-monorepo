import { useEffect, useRef, useState } from 'react';
import { Download, Pause, Play, Trash2 } from 'lucide-react';
import { logsDownloadUrl, wsUrl } from '../lib/api';

// Keep memory bounded — a long-running follow can produce a lot of output.
const MAX_CHARS = 200_000;

// Live log viewer backed by /ws/containers/{name}/logs. Auto-scrolls while the
// user is at the bottom; pausing stops appending without dropping the socket.
export function LiveLogs({ name }: { name: string }) {
  const [text, setText] = useState('');
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);
  const followRef = useRef(true);
  const preRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    pausedRef.current = paused;
  }, [paused]);

  useEffect(() => {
    setText('');
    followRef.current = true;
    const ws = new WebSocket(wsUrl(`/ws/containers/${encodeURIComponent(name)}/logs?tail=400`));
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (e) => {
      if (pausedRef.current) return;
      setText((prev) => {
        const next = prev + (e.data as string);
        return next.length > MAX_CHARS ? next.slice(next.length - MAX_CHARS) : next;
      });
    };
    return () => ws.close();
  }, [name]);

  // Stick to the bottom while following.
  useEffect(() => {
    const el = preRef.current;
    if (el && followRef.current) el.scrollTop = el.scrollHeight;
  }, [text]);

  const onScroll = () => {
    const el = preRef.current;
    if (!el) return;
    followRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
  };

  return (
    <div className="logs">
      <div className="logs-toolbar">
        <span className={`logs-status ${connected ? 'on' : 'off'}`}>
          {connected ? 'streaming' : 'disconnected'}
        </span>
        <div className="logs-toolbar-actions">
          <button className="btn btn-ghost xs" onClick={() => setPaused((p) => !p)}>
            {paused ? <Play size={13} /> : <Pause size={13} />}
            {paused ? 'Resume' : 'Pause'}
          </button>
          <button className="btn btn-ghost xs" onClick={() => setText('')}>
            <Trash2 size={13} />
            Clear
          </button>
          <a
            className="btn btn-ghost xs"
            href={logsDownloadUrl(name)}
            download={`${name}.log`}
            title="Download the full container log"
          >
            <Download size={13} />
            Export
          </a>
        </div>
      </div>
      <pre className="logs-view" ref={preRef} onScroll={onScroll}>
        {text || 'Waiting for log output…'}
      </pre>
    </div>
  );
}
