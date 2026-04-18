"use client";

import { Canvas, useThree } from "@react-three/fiber";
import {
  GizmoHelper,
  GizmoViewport,
  Grid,
  OrbitControls,
} from "@react-three/drei";
import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import * as THREE from "three";
import { SparkRenderer, SplatMesh } from "@sparkjsdev/spark";

type FitFn = () => void;

function SparkSceneSetup() {
  const { gl, scene } = useThree();

  useEffect(() => {
    const spark = new SparkRenderer({ renderer: gl });
    scene.add(spark);
    return () => {
      scene.remove(spark);
    };
  }, [gl, scene]);

  return null;
}

type Vec3 = { x: number; y: number; z: number };

function TransformGroup({
  title,
  values,
  onChange,
  min,
  max,
  step,
}: {
  title: string;
  values: Vec3;
  onChange: (updater: (prev: Vec3) => Vec3) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <div>
      <div className="font-semibold mb-2 text-xs uppercase tracking-wider text-white/70">
        {title}
      </div>
      {(["x", "y", "z"] as const).map((axis) => (
        <div key={axis} className="flex items-center gap-3 mb-2 last:mb-0">
          <label className="w-4 font-mono uppercase">{axis}</label>
          <input
            type="range"
            min={min}
            max={max}
            step={step}
            value={values[axis]}
            onChange={(e) =>
              onChange((v) => ({ ...v, [axis]: Number(e.target.value) }))
            }
            className="flex-1 accent-green-500"
          />
          <input
            type="number"
            step={step}
            value={values[axis]}
            onChange={(e) =>
              onChange((v) => ({ ...v, [axis]: Number(e.target.value) }))
            }
            className="w-16 bg-white/10 rounded px-2 py-1 text-right tabular-nums"
          />
        </div>
      ))}
    </div>
  );
}

type SplatProps = {
  url: string;
  rotationDeg: Vec3;
  positionOffset: Vec3;
  scale: number;
  onReady?: () => void;
  onFitReady?: (fit: FitFn) => void;
};

function Splat({ url, rotationDeg, positionOffset, scale, onReady, onFitReady }: SplatProps) {
  const { camera, controls } = useThree() as unknown as {
    camera: THREE.PerspectiveCamera;
    controls: { target: THREE.Vector3; update: () => void } | null;
  };

  const [mesh, setMesh] = useState<SplatMesh | null>(null);
  const meshRef = useRef<SplatMesh | null>(null);
  const groupRef = useRef<THREE.Group>(null);

  const fitToScene = useCallback(() => {
    const m = meshRef.current;
    if (!m) return;
    if (!m.packedSplats && !m.extSplats) return;

    m.position.set(0, 0, 0);
    m.updateMatrixWorld(true);

    // Robust fit: use median center + percentile-based radius (distance from
    // median). Spark's getBoundingBox and plain min/max are thrown off by a
    // handful of outlier splats far from the main cluster, making the camera
    // sit very far back and the real scene look like a tiny dot.
    const xs: number[] = [];
    const ys: number[] = [];
    const zs: number[] = [];
    m.forEachSplat((_i, c) => {
      xs.push(c.x);
      ys.push(c.y);
      zs.push(c.z);
    });
    const n = xs.length;
    if (n === 0) return;

    const median = (arr: number[]) => {
      const s = [...arr].sort((a, b) => a - b);
      const mid = Math.floor(s.length / 2);
      return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
    };
    const center = new THREE.Vector3(median(xs), median(ys), median(zs));
    if (!isFinite(center.x)) return;

    const dists: number[] = new Array(n);
    for (let i = 0; i < n; i++) {
      const dx = xs[i] - center.x;
      const dy = ys[i] - center.y;
      const dz = zs[i] - center.z;
      dists[i] = Math.sqrt(dx * dx + dy * dy + dz * dz);
    }
    dists.sort((a, b) => a - b);
    // 90th percentile distance-from-median → ignores ~10% outliers.
    const radius = Math.max(0.05, dists[Math.floor(n * 0.9)]);

    // eslint-disable-next-line no-console
    console.log("[SplatViewer] fit", {
      numSplats: n,
      center: center.toArray(),
      radius,
    });

    m.position.sub(center);

    const distance = (radius / Math.tan((camera.fov * Math.PI) / 360)) * 0.2;

    const dir = new THREE.Vector3(1, 0.7, 1).normalize();
    camera.position.copy(dir).multiplyScalar(distance);
    camera.near = Math.max(0.001, distance / 1000);
    camera.far = Math.max(distance * 100, 1000);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();

    if (controls?.target) {
      controls.target.set(0, 0, 0);
      controls.update?.();
    }
  }, [camera, controls]);

  useEffect(() => {
    onFitReady?.(fitToScene);
  }, [fitToScene, onFitReady]);

  useEffect(() => {
    const g = groupRef.current;
    if (!g) return;
    g.position.set(positionOffset.x, positionOffset.y, positionOffset.z);
    g.rotation.set(
      (rotationDeg.x * Math.PI) / 180,
      (rotationDeg.y * Math.PI) / 180,
      (rotationDeg.z * Math.PI) / 180
    );
    g.scale.setScalar(scale);
  }, [rotationDeg, positionOffset, scale, mesh]);

  useEffect(() => {
    let cancelled = false;
    const m = new SplatMesh({ url });
    setMesh(m);
    m.initialized
      .then((loaded) => {
        if (cancelled) return;
        if (!loaded.packedSplats && !loaded.extSplats) return;
        meshRef.current = loaded;
        fitToScene();
        onReady?.();
      })
      .catch((err) => {
        console.error("[SplatViewer] failed to load:", err);
      });

    return () => {
      cancelled = true;
      meshRef.current = null;
      m.dispose();
    };
  }, [url, fitToScene, onReady]);

  if (!mesh) return null;
  return (
    <group ref={groupRef}>
      <primitive object={mesh as unknown as THREE.Object3D} />
    </group>
  );
}

type SplatViewerProps = {
  url: string;
};

export default function SplatViewer({ url }: SplatViewerProps) {
  const [ready, setReady] = useState(false);
  const onReady = useRef(() => setReady(true)).current;
  const fitRef = useRef<FitFn | null>(null);
  const [rotationDeg, setRotationDeg] = useState<Vec3>({ x: 0, y: 0, z: 0 });
  const [positionOffset, setPositionOffset] = useState<Vec3>({ x: 0, y: 0, z: 0 });
  const [scale, setScale] = useState(1);

  useEffect(() => {
    setReady(false);
    setRotationDeg({ x: 0, y: 0, z: 0 });
    setPositionOffset({ x: 0, y: 0, z: 0 });
    setScale(1);
  }, [url]);

  const onFitReady = useCallback((fit: FitFn) => {
    fitRef.current = fit;
  }, []);

  return (
    <div className="relative w-full h-full">
      <Canvas
        camera={{ position: [0, 0, 3], fov: 60, near: 0.01, far: 1000 }}
        gl={{ antialias: false, premultipliedAlpha: true }}
        style={{ background: "#0a0a0a" }}
      >
        <SparkSceneSetup />
        <Suspense fallback={null}>
          <Splat
            url={url}
            rotationDeg={rotationDeg}
            positionOffset={positionOffset}
            scale={scale}
            onReady={onReady}
            onFitReady={onFitReady}
          />
        </Suspense>
        <axesHelper args={[1]} />
        <Grid
          args={[20, 20]}
          cellColor="#3a3a3a"
          sectionColor="#606060"
          sectionSize={5}
          fadeDistance={30}
          fadeStrength={1}
          infiniteGrid
        />
        <OrbitControls enableDamping makeDefault />
        <GizmoHelper alignment="top-right" margin={[64, 64]}>
          <GizmoViewport
            axisColors={["#e53e3e", "#38a169", "#3182ce"]}
            labelColor="white"
          />
        </GizmoHelper>
      </Canvas>
      <button
        onClick={() => fitRef.current?.()}
        className="absolute bottom-3 right-3 z-10 bg-black/60 hover:bg-black/80 backdrop-blur text-white text-sm rounded px-3 py-1.5 transition-colors"
        title="Re-fit camera to the splat"
      >
        Fit to scene
      </button>
      <div className="absolute top-16 left-3 z-10 bg-black/70 backdrop-blur text-white rounded-lg px-5 py-4 text-sm w-80 shadow-lg space-y-4">
        <TransformGroup
          title="Position"
          values={positionOffset}
          onChange={setPositionOffset}
          min={-5}
          max={5}
          step={0.05}
        />
        <TransformGroup
          title="Rotation (deg)"
          values={rotationDeg}
          onChange={setRotationDeg}
          min={-180}
          max={180}
          step={1}
        />
        <div>
          <div className="font-semibold mb-2 text-xs uppercase tracking-wider text-white/70">
            Scale
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={0.1}
              max={5}
              step={0.01}
              value={scale}
              onChange={(e) => setScale(Number(e.target.value))}
              className="flex-1 accent-green-500"
            />
            <input
              type="number"
              min={0.01}
              step={0.05}
              value={scale}
              onChange={(e) => setScale(Number(e.target.value))}
              className="w-16 bg-white/10 rounded px-2 py-1 text-right tabular-nums"
            />
          </div>
        </div>
        <button
          onClick={() => {
            setPositionOffset({ x: 0, y: 0, z: 0 });
            setRotationDeg({ x: 0, y: 0, z: 0 });
            setScale(1);
          }}
          className="w-full text-xs text-white/70 hover:text-white underline underline-offset-2"
        >
          Reset all
        </button>
      </div>
      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none text-white/80 text-sm">
          Decoding splat…
        </div>
      )}
    </div>
  );
}
