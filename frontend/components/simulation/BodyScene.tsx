"use client";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RotateCcw, HeartPulse, Wind, Droplets, Activity, Eye, Orbit, Layers, UserRound, Sparkles } from "lucide-react";
import { Organ, ORGANS, ORGAN_COLORS, ORGAN_LABELS, VisualResponse } from "../../lib/contracts";

type Props = {
  selected: Organ;
  onSelect: (organ: Organ) => void;
  playing: boolean;
  time: number;
  sex: "male" | "female";
  responses?: Record<Organ, VisualResponse>;
};

const FILES: Record<Organ, string[]> = {
  cardiovascular: ["Heart"],
  respiratory: ["Lung"],
  hepatic: ["Liver"],
  renal: ["Kidney_L", "Kidney_R"],
};

const ICONS = {
  cardiovascular: HeartPulse,
  respiratory: Wind,
  renal: Droplets,
  hepatic: Activity,
};

// Anatomical biological material parameters
const ORGAN_BASE_COLORS: Record<Organ, number> = {
  cardiovascular: 0xba2b3b, // Myocardial cardiac crimson
  respiratory: 0xba6878,    // Pulmonary vascular rose
  hepatic: 0x6e2820,        // Hepatic deep mahogany
  renal: 0x982e3f,          // Renal cortex deep red
};

export default function BodyScene(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const current = useRef(props);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [xrayMode, setXrayMode] = useState(false);
  const [autoRotate, setAutoRotate] = useState(false);
  const [viewAngle, setViewAngle] = useState<"front" | "back" | "lateral">("front");

  useEffect(() => { current.current = props; }, [props]);

  // Set camera to specific anatomical view focused on the thoracic & abdominal cavity
  const setCameraView = (angle: "front" | "back" | "lateral") => {
    setViewAngle(angle);
    if (!controlsRef.current || !cameraRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (angle === "front") {
      camera.position.set(0, 2.1, 7.8);
      controls.target.set(0, 1.95, 0);
    } else if (angle === "back") {
      // Direct view of kidneys and posterior spine
      camera.position.set(0, 2.05, -7.8);
      controls.target.set(0, 1.95, 0);
    } else if (angle === "lateral") {
      camera.position.set(7.5, 2.0, 2.5);
      controls.target.set(0, 1.95, 0);
    }
    controls.update();
  };

  useEffect(() => {
    if (props.selected === "renal" && viewAngle === "front") {
      // Highlight: encourage posterior or activate focus
    }
  }, [props.selected, viewAngle]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let disposed = false;
    let frame = 0;
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    } catch {
      setFailed(true);
      setLoading(false);
      return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.7));
    renderer.setClearColor(0x0a1413);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.6;
    renderer.localClippingEnabled = true;
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute("aria-label", "Interactive 3D anatomical body with selectable heart, lungs, liver and kidneys");
    element.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a1413);

    // Subtle atmospheric fog for visual depth
    scene.fog = new THREE.FogExp2(0x0a1413, 0.025);

    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 50);
    camera.position.set(0, 2.1, 7.8);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 1.95, 0);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.enablePan = false;
    controls.minDistance = 4.5;
    controls.maxDistance = 12;
    controls.maxPolarAngle = Math.PI * 0.65;
    controls.minPolarAngle = Math.PI * 0.35;
    controls.autoRotate = autoRotate;
    controls.autoRotateSpeed = 1.8;
    controls.saveState();
    controlsRef.current = controls;

    // Advanced Clinical Studio Lighting
    scene.add(new THREE.HemisphereLight(0xdcf8f2, 0x182c28, 2.8));
    const key = new THREE.DirectionalLight(0xfff6ec, 4.2);
    key.position.set(-3, 6, 7);
    scene.add(key);

    const fill = new THREE.DirectionalLight(0x7dd3fc, 2.6);
    fill.position.set(4, 2, -4);
    scene.add(fill);

    const rim = new THREE.DirectionalLight(0x34d399, 2.2);
    rim.position.set(0, 5, -6);
    scene.add(rim);

    const stage = new THREE.Group();
    stage.scale.setScalar(5.2);
    scene.add(stage);

    const pivots = {} as Record<Organ, THREE.Group>;
    const organMeshes = {} as Record<Organ, THREE.Mesh[]>;
    const pickable: THREE.Mesh[] = [];
    const loader = new GLTFLoader();
    const prefix = props.sex === "female" ? "VH_F" : "VH_M";

    async function load() {
      try {
        const skin = await loader.loadAsync(`/anatomy/${prefix}_Skin.glb`);
        if (disposed) return;

        skin.scene.traverse(object => {
          if (!(object instanceof THREE.Mesh)) return;
          // Ultra-sleek holographic digital twin glass mannequin
          object.material = new THREE.MeshPhysicalMaterial({
            color: 0x4f9689,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.20,
            transmission: 0.65,
            roughness: 0.32,
            metalness: 0.05,
            clearcoat: 0.7,
            clearcoatRoughness: 0.3,
            depthWrite: false,
            clippingPlanes: [new THREE.Plane(new THREE.Vector3(0, 1, 0), 0.05 * 5.2)],
          });
          object.renderOrder = 5;
        });
        stage.add(skin.scene);

        await Promise.all(ORGANS.map(async organ => {
          const loaded = await Promise.all(FILES[organ].map(name => loader.loadAsync(`/anatomy/${prefix}_${name}.glb`)));
          if (disposed) return;
          const group = new THREE.Group();
          loaded.forEach(gltf => group.add(gltf.scene));

          const center = new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3());
          const pivot = new THREE.Group();
          pivot.position.copy(center);
          if (organ === "renal") {
            // Position kidneys in anatomically natural lumbar flank region (below liver, T12-L3)
            pivot.position.y -= (prefix === "VH_M" ? 0.08 : 0.045);
          }
          group.position.copy(center.clone().negate());
          pivot.add(group);
          stage.add(pivot);

          pivots[organ] = pivot;
          organMeshes[organ] = [];

          group.traverse(object => {
            if (!(object instanceof THREE.Mesh)) return;
            const originalMat = (Array.isArray(object.material) ? object.material[0] : object.material);
            
            // Rich biological PBR material
            const baseColor = ORGAN_BASE_COLORS[organ];
            const pbrMat = new THREE.MeshPhysicalMaterial({
              color: baseColor,
              roughness: organ === "hepatic" ? 0.42 : organ === "cardiovascular" ? 0.28 : organ === "renal" ? 0.32 : 0.52,
              metalness: 0.04,
              clearcoat: organ === "cardiovascular" ? 0.85 : organ === "renal" ? 0.75 : 0.45,
              clearcoatRoughness: 0.2,
              side: THREE.DoubleSide,
              transparent: true,
              opacity: 1.0,
              depthWrite: true,
            });

            object.material = pbrMat;
            object.userData.organ = organ;
            pickable.push(object);
            organMeshes[organ].push(object);
          });
        }));

        if (!disposed) setLoading(false);
      } catch {
        if (!disposed) {
          setFailed(true);
          setLoading(false);
        }
      }
    }
    void load();

    const pointer = new THREE.Vector2(), ray = new THREE.Raycaster();
    let down: { x: number; y: number } | null = null;
    const onDown = (event: PointerEvent) => { down = { x: event.clientX, y: event.clientY }; };
    const onUp = (event: PointerEvent) => {
      if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 6) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObjects(pickable)[0];
      if (hit) current.current.onSelect(hit.object.userData.organ as Organ);
    };

    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);

    const resize = () => {
      const width = element.clientWidth, height = element.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(element);
    resize();

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const start = performance.now();
    let lastFrame = start;
    const cueColors = {
      caution: new THREE.Color(0xef4444),
      selectedRenal: new THREE.Color(0xa855f7),
      selected: new THREE.Color(0x10b981),
      condition: new THREE.Color(0xd97706),
      exposure: new THREE.Color(0x06b6d4),
      quiet: new THREE.Color(0x000000),
    };

    function animate() {
      const props = current.current;
      const now = performance.now();
      const elapsed = (now - start) / 1000;
      const blend = reduced.matches ? 1 : 1 - Math.exp(-Math.min(now - lastFrame, 50) / 180);
      lastFrame = now;
      const motion = props.playing && !reduced.matches;

      for (const organ of ORGANS) {
        const pivot = pivots[organ];
        if (!pivot) continue;

        const response = props.responses?.[organ];
        const activeCaution = response?.cues.some(cue => cue.kind === "source_linked_caution" && cue.time <= props.time);
        const activeExposure = response?.cues.some(cue => cue.time <= props.time);
        const condition = Boolean(response?.condition_mechanisms.length);
        const selected = props.selected === organ;

        // Realistic biological pulsation
        const phase = response?.pattern === "irregular_rhythm"
          ? Math.sin(elapsed * 6 + Math.sin(elapsed * 1.8))
          : Math.sin(elapsed * (organ === "cardiovascular" ? 5.8 : 1.8));

        const range = organ === "cardiovascular"
          ? 0.048
          : organ === "respiratory"
          ? response?.pattern?.startsWith("restricted") ? 0.014 : 0.032
          : organ === "renal" ? 0.012 : 0.006;

        const pulse = motion ? phase * range : 0;
        pivot.scale.set(1 + pulse, 1 + pulse * (organ === "respiratory" ? 1.35 : 1), 1 + pulse);

        // Smart Visibility & Transparency
        // When renal (Kidneys) is selected, or in X-Ray mode, fade liver and lungs so kidneys are 100% visible
        const meshes = organMeshes[organ] || [];
        for (const object of meshes) {
          const material = object.material as THREE.MeshPhysicalMaterial;

          let targetOpacity = 1.0;
          if (xrayMode) {
            targetOpacity = selected ? 1.0 : 0.28;
          } else if (props.selected === "renal" && (organ === "hepatic" || organ === "respiratory")) {
            // Obscuring anterior organs become semi-translucent glass so kidneys shine through
            targetOpacity = 0.24;
          } else if (props.selected === "cardiovascular" && organ === "respiratory") {
            // Lungs become semi-translucent glass so beating heart is fully visible
            targetOpacity = 0.22;
          } else if (!selected && (props.selected === "renal" || props.selected === "cardiovascular")) {
            targetOpacity = 0.65;
          }

          material.opacity = THREE.MathUtils.lerp(material.opacity, targetOpacity, blend);
          material.depthWrite = material.opacity > 0.5;

          // Ease visual cues; this colour is an evidence/association signal, not organ function.
          let targetColor = cueColors.quiet;
          let targetIntensity = 0;
          if (activeCaution) {
            targetColor = cueColors.caution;
            targetIntensity = 0.45 + (motion ? Math.max(0, phase) * 0.45 : 0);
          } else if (selected) {
            targetColor = organ === "renal" ? cueColors.selectedRenal : cueColors.selected;
            targetIntensity = 0.35 + (motion ? Math.max(0, phase) * 0.25 : 0);
          } else if (condition) {
            targetColor = cueColors.condition;
            targetIntensity = 0.16;
          } else if (activeExposure) {
            targetColor = cueColors.exposure;
            targetIntensity = 0.12;
          }
          material.emissive.lerp(targetColor, blend);
          material.emissiveIntensity = THREE.MathUtils.lerp(material.emissiveIntensity, targetIntensity, blend);

          material.roughness = response?.pattern === "fibrotic_texture" ? 0.90 : material.roughness;
        }
      }

      controls.update();
      renderer.render(scene, camera);
      frame = requestAnimationFrame(animate);
    }
    animate();

    return () => {
      disposed = true;
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      controlsRef.current = null;
      cameraRef.current = null;
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      const geometries = new Set<THREE.BufferGeometry>(), materials = new Set<THREE.Material>();
      scene.traverse(object => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          (Array.isArray(object.material) ? object.material : [object.material]).forEach(material => materials.add(material));
        }
      });
      geometries.forEach(geometry => geometry.dispose());
      materials.forEach(material => material.dispose());
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [props.sex, xrayMode]);

  // Update autoRotate when toggled
  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
    }
  }, [autoRotate]);

  return (
    <div className="anatomy-scene anatomical-3d">
      <div ref={host} className="scene-canvas" />
      {loading && !failed && (
        <div className="scene-loading">
          <Activity className="spin" size={24} style={{ marginBottom: 10, color: "#14b8a6" }} />
          <strong>Loading 3D Anatomical Digital Twin...</strong>
          <span style={{ fontSize: 11, color: "#99b6ad", marginTop: 4 }}>HuBMAP CCF 3D Biological Meshes</span>
        </div>
      )}
      {failed && (
        <div className="scene-loading">
          3D model unavailable on this device. Organ findings remain available at right.
        </div>
      )}

      {/* Top Bar with Status and Mode Tools */}
      <div className="scene-topline">
        <div className="digital-twin-badge">
          <Sparkles size={13} color="#14b8a6" />
          <span>3D ANATOMICAL DIGITAL TWIN</span>
        </div>
        <span className="scene-time">{props.time.toFixed(0)} s</span>
      </div>

      {/* View Presets & Tools Toolbar */}
      <div className="scene-tools-bar" role="toolbar" aria-label="3D Anatomical View Controls">
        <button
          type="button"
          className={`scene-tool-btn ${viewAngle === "front" ? "active" : ""}`}
          title="Anterior Front View"
          aria-label="Anterior Front View"
          onClick={() => setCameraView("front")}
        >
          <UserRound size={15} />
          <span>Front</span>
        </button>

        <button
          type="button"
          className={`scene-tool-btn ${viewAngle === "back" ? "active" : ""}`}
          title="Posterior Kidneys & Spine View (Unobstructed view of both kidneys)"
          aria-label="Posterior Kidneys View"
          onClick={() => setCameraView("back")}
        >
          <Droplets size={15} color="#c084fc" />
          <span>Kidneys (Back)</span>
        </button>

        <button
          type="button"
          className={`scene-tool-btn ${viewAngle === "lateral" ? "active" : ""}`}
          title="Lateral Side View"
          aria-label="Lateral Side View"
          onClick={() => setCameraView("lateral")}
        >
          <span>Side</span>
        </button>

        <div className="tool-divider" />

        <button
          type="button"
          className={`scene-tool-btn ${xrayMode ? "active highlight" : ""}`}
          title={xrayMode ? "Disable X-Ray Glass Mode" : "Enable X-Ray Glass Mode (See all internal organs in depth)"}
          aria-label="Toggle X-Ray Transparency Mode"
          onClick={() => setXrayMode(!xrayMode)}
        >
          <Eye size={15} />
          <span>X-Ray</span>
        </button>

        <button
          type="button"
          className={`scene-tool-btn ${autoRotate ? "active highlight" : ""}`}
          title={autoRotate ? "Stop 360° Auto-Orbit" : "Start 360° Auto-Orbit (Continuous rotation for presentations)"}
          aria-label="Toggle 360 Auto-Orbit"
          onClick={() => setAutoRotate(!autoRotate)}
        >
          <Orbit size={15} />
          <span>Orbit</span>
        </button>

        <button
          type="button"
          className="scene-tool-btn icon-only"
          title="Reset Camera"
          aria-label="Reset Camera"
          onClick={() => {
            setViewAngle("front");
            controlsRef.current?.reset();
          }}
        >
          <RotateCcw size={15} />
        </button>
      </div>

      {/* Floating Organ Selector Pills */}
      <div className="anatomy-labels">
        {ORGANS.map(organ => {
          const Icon = ICONS[organ];
          const response = props.responses?.[organ];
          const caution = response?.cues.some(cue => cue.kind === "source_linked_caution" && cue.time <= props.time);
          const isSelected = props.selected === organ;

          return (
            <button
              type="button"
              key={organ}
              className={`anatomy-label ${organ} ${isSelected ? "active" : ""}`}
              onClick={() => {
                props.onSelect(organ);
                if (organ === "renal" && viewAngle === "front") {
                  // If user clicks Kidneys, suggest or switch to posterior view so kidneys are directly seen!
                  setCameraView("back");
                }
              }}
              style={{ "--organ-color": ORGAN_COLORS[organ] } as React.CSSProperties}
            >
              <Icon size={16} />
              <span>{organ === "cardiovascular" ? "Heart" : organ === "respiratory" ? "Lungs" : ORGAN_LABELS[organ]}</span>
              <i className={caution ? "organ-dot caution" : "organ-dot"} />
            </button>
          );
        })}
      </div>

      <div className="scene-caption">
        <strong>HuBMAP CCF 3D Anatomical Reference Library</strong> · Click organ or use <b>Kidneys (Back)</b> / <b>X-Ray</b> for full depth visualization.
      </div>
    </div>
  );
}

