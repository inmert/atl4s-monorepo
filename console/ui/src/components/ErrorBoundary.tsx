import { Component, ErrorInfo, ReactNode } from 'react';

// Catches errors thrown by the model loaders (useFBX/useGLTF reject into the
// React tree). Lives inside <Canvas>, so its fallback must be 3D-safe (null) —
// the human-facing message is surfaced by the parent via onError.
export class ErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode; onError?: (e: Error) => void },
  { hasError: boolean }
> {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error, _info: ErrorInfo) {
    this.props.onError?.(error);
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}
