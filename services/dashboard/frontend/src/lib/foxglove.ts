// Deep-link to Foxglove Studio against this host's foxglove-bridge service
// (TCP 8765). Browser hostname → ws URL; the user must already be on the
// same network as the bridge.

export const FOXGLOVE_BRIDGE_PORT = 8765;

export function foxgloveStudioUrl(): string {
  const host = window.location.hostname || 'localhost';
  const wsUrl = `ws://${host}:${FOXGLOVE_BRIDGE_PORT}`;
  return `https://studio.foxglove.dev/?ds=foxglove-websocket&ds.url=${encodeURIComponent(wsUrl)}`;
}
