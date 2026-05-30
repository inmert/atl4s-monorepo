import { Suspense, useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Bounds, Center, Grid, OrbitControls, useFBX, useGLTF, useProgress } from '@react-three/drei';
import { ModelStats } from '../lib/api';
import { ErrorBoundary } from './ErrorBoundary';

// Blender-style navigation: middle-mouse orbits, Shift+MMB pans, Ctrl+MMB and
// the scroll wheel zoom. Left-drag also orbits (kept for trackpad users without
// a middle button); right-drag pans.
function BlenderControls() {
  const ref = useRef<any>(null);
  useEffect(() => {
    const controls = ref.current;
    if (!controls) return;
    controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.ROTATE,
      RIGHT: THREE.MOUSE.PAN,
    };
    const apply = (e: KeyboardEvent) => {
      controls.mouseButtons.MIDDLE = e.shiftKey
        ? THREE.MOUSE.PAN
        : e.ctrlKey
          ? THREE.MOUSE.DOLLY
          : THREE.MOUSE.ROTATE;
    };
    window.addEventListener('keydown', apply);
    window.addEventListener('keyup', apply);
    return () => {
      window.removeEventListener('keydown', apply);
      window.removeEventListener('keyup', apply);
    };
  }, []);
  return <OrbitControls ref={ref} makeDefault enableDamping dampingFactor={0.12} />;
}

// Captures the rendered frame once the camera settles (so we segment the view
// you land on, not every frame). Calls onMoving the moment the camera starts
// moving so the parent can hide the stale overlay.
function SettleCapture({ onCapture, onMoving }: { onCapture: (b: Blob) => void; onMoving: () => void }) {
  const { gl, camera } = useThree();
  const lastPos = useRef(new THREE.Vector3(Infinity, 0, 0));
  const lastQuat = useRef(new THREE.Quaternion());
  const stable = useRef(0);
  const dirty = useRef(true);

  useFrame(() => {
    const moved =
      camera.position.distanceToSquared(lastPos.current) > 1e-7 ||
      Math.abs(camera.quaternion.dot(lastQuat.current)) < 0.9999999;
    if (moved) {
      lastPos.current.copy(camera.position);
      lastQuat.current.copy(camera.quaternion);
      stable.current = 0;
      if (!dirty.current) {
        dirty.current = true;
        onMoving();
      }
    } else if (dirty.current) {
      stable.current += 1;
      if (stable.current > 16) {
        dirty.current = false;
        gl.domElement.toBlob((blob) => blob && onCapture(blob), 'image/png');
      }
    }
  });
  return null;
}

function FBXModel({ url, onStats }: { url: string; onStats?: (s: ModelStats | null) => void }) {
  const object = useFBX(url);
  useReportStats(object, onStats);
  return <primitive object={object} />;
}

function GLTFModel({ url, onStats }: { url: string; onStats?: (s: ModelStats | null) => void }) {
  const gltf = useGLTF(url);
  useReportStats(gltf.scene, onStats);
  return <primitive object={gltf.scene} />;
}

function Model({ url, ext, onStats }: { url: string; ext: string; onStats?: (s: ModelStats | null) => void }) {
  if (ext === 'glb' || ext === 'gltf') return <GLTFModel url={url} onStats={onStats} />;
  return <FBXModel url={url} onStats={onStats} />;
}

function computeStats(object: THREE.Object3D): ModelStats {
  let meshes = 0;
  let vertices = 0;
  let triangles = 0;
  object.traverse((o) => {
    const mesh = o as THREE.Mesh;
    if (mesh.isMesh && mesh.geometry) {
      meshes += 1;
      const pos = mesh.geometry.getAttribute('position');
      if (pos) vertices += pos.count;
      const index = mesh.geometry.getIndex();
      triangles += index ? index.count / 3 : pos ? pos.count / 3 : 0;
    }
  });
  const box = new THREE.Box3().setFromObject(object);
  const size = new THREE.Vector3();
  box.getSize(size);
  return { meshes, vertices, triangles: Math.round(triangles), size: [size.x, size.y, size.z] };
}

function useReportStats(object: THREE.Object3D, onStats?: (s: ModelStats | null) => void) {
  useEffect(() => {
    onStats?.(computeStats(object));
    return () => onStats?.(null);
  }, [object, onStats]);
}

function LoaderOverlay() {
  const { active, progress } = useProgress();
  if (!active) return null;
  return (
    <div className="viewer-overlay">
      <span className="spinner" />
      <span>Loading… {Math.round(progress)}%</span>
    </div>
  );
}

export function Viewer3D({
  url,
  ext,
  onStats,
  crackEnabled = false,
  onCapture,
  onMoving,
}: {
  url: string | null;
  ext: string;
  onStats?: (s: ModelStats | null) => void;
  crackEnabled?: boolean;
  onCapture?: (b: Blob) => void;
  onMoving?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setError(null), [url]);

  if (!url) {
    return <div className="viewer-empty">Upload or select a model to view.</div>;
  }

  return (
    <>
      {/* preserveDrawingBuffer lets us read the canvas for crack inference. */}
      <Canvas camera={{ position: [4, 4, 4], fov: 50 }} dpr={[1, 2]} gl={{ preserveDrawingBuffer: true }}>
        <color attach="background" args={['#0b0b0d']} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[6, 10, 6]} intensity={1.1} />
        <directionalLight position={[-6, 4, -6]} intensity={0.35} />

        <Suspense fallback={null}>
          <ErrorBoundary key={url} fallback={null} onError={(e) => setError(e.message)}>
            <Bounds fit clip observe margin={1.25}>
              <Center>
                <Model url={url} ext={ext} onStats={onStats} />
              </Center>
            </Bounds>
          </ErrorBoundary>
        </Suspense>

        {/* Hide the grid while segmenting so it isn't mistaken for cracks. */}
        {!crackEnabled && (
          <Grid
            infiniteGrid
            cellSize={0.5}
            cellColor="#1a1a1f"
            sectionSize={2.5}
            sectionColor="#0c5cab"
            fadeDistance={45}
            fadeStrength={1}
          />
        )}

        <BlenderControls />
        {crackEnabled && onCapture && onMoving && (
          <SettleCapture onCapture={onCapture} onMoving={onMoving} />
        )}
      </Canvas>

      {!error && <LoaderOverlay />}
      {error && (
        <div className="viewer-overlay viewer-error">
          <span>Couldn't load this model.</span>
          <span className="viewer-hint">
            {ext.toUpperCase()} may be unsupported or reference missing textures.
          </span>
        </div>
      )}
    </>
  );
}
