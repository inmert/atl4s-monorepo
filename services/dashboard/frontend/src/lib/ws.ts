// WebSocket helpers with auto-reconnect and exponential backoff.

type WsHandle = { close: () => void };

function wsUrl(path: string): string {
  const url = new URL(path, window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  return url.toString();
}

function connect(
  path: string,
  binary: boolean,
  onMessage: (data: any) => void,
  onStatus?: (s: 'open' | 'closed') => void,
): WsHandle {
  let ws: WebSocket | null = null;
  let closed = false;
  let backoff = 500;

  const open = () => {
    if (closed) return;
    ws = new WebSocket(wsUrl(path));
    if (binary) ws.binaryType = 'blob';
    ws.addEventListener('open', () => {
      backoff = 500;
      onStatus?.('open');
    });
    ws.addEventListener('message', (e) => {
      if (binary) {
        if (e.data instanceof Blob) onMessage(e.data);
      } else {
        try {
          onMessage(JSON.parse(e.data));
        } catch {
          // ignore malformed frames
        }
      }
    });
    ws.addEventListener('close', () => {
      onStatus?.('closed');
      if (closed) return;
      setTimeout(open, backoff);
      backoff = Math.min(backoff * 2, 5000);
    });
    ws.addEventListener('error', () => {
      ws?.close();
    });
  };

  open();
  return {
    close: () => {
      closed = true;
      ws?.close();
    },
  };
}

export function jsonSocket<T>(
  path: string,
  onMessage: (msg: T) => void,
  onStatus?: (s: 'open' | 'closed') => void,
): WsHandle {
  return connect(path, false, onMessage, onStatus);
}

export function blobSocket(
  path: string,
  onMessage: (blob: Blob) => void,
  onStatus?: (s: 'open' | 'closed') => void,
): WsHandle {
  return connect(path, true, onMessage, onStatus);
}
