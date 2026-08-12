// Provider beam diagram — ported from the vanilla micro-frontend
// (admin_static/beam/src/main.tsx + beam.css) into the React admin-ui, now
// rendering the re-homed magicui AnimatedBeam (components/ui/magic/animated-beam).
//
// The canvas is pan/zoom (drag the background, wheel/buttons to zoom) and every
// provider node is individually draggable. Zoom scales the layout via the --bs
// custom property, so beam paths are re-measured by the component's ResizeObserver;
// node drags bump a measureKey that forces the same re-measure so beams stay
// attached while a node is being moved.
import {
  createRef,
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type RefObject,
} from "react";

import { AnimatedBeam } from "@/components/ui/magic/animated-beam";

import "./beam.css";

export interface BeamProvider {
  id: string;
  name: string;
  logo: string;
}

export interface ProviderBeamProps {
  providers: BeamProvider[];
  gateway?: { name: string };
  client?: { name: string };
}

const FALLBACK_LOGO = "/admin/assets/logos/_fallback.svg";
const MIN_SCALE = 0.2;
const MAX_SCALE = 3;
const FIT_PADDING = 32;
const GATEWAY_MARK_PATH =
  "M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-7.258 0h3.767L16.906 20h-3.674l-1.343-3.461H5.017l-1.344 3.46H0L6.57 3.522zm4.132 9.959L8.453 7.687 6.205 13.48H10.7z";
const USER_ICON_PATH = "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2";

// Natural (scale-1) node geometry in px.
const PROVIDER_NODE = 48;
const GATEWAY_NODE = 64;
const CLIENT_NODE = 48;

interface View {
  x: number;
  y: number;
  s: number;
}

interface ProviderPos {
  x: number;
  y: number;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function ProviderBeam({ providers, gateway, client }: ProviderBeamProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const diagramRef = useRef<HTMLDivElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);
  const clientRef = useRef<HTMLDivElement>(null);
  const providerRefs = useRef(new Map<string, RefObject<HTMLDivElement | null>>());
  const viewRef = useRef<View>({ x: 0, y: 0, s: 1 });
  // One drag state for both node-drags and canvas pans. Node drags stop
  // propagation so they never also start a pan.
  const dragState = useRef<{
    node: { providerId: string; px: number; py: number; start: ProviderPos } | null;
    pan: { px: number; py: number } | null;
  }>({ node: null, pan: null });
  const fitRef = useRef<() => void>(() => {});
  const measureScheduled = useRef(false);
  const windowMove = useRef<(event: PointerEvent) => void>(() => {});
  const windowUp = useRef<() => void>(() => {});
  const [view, setView] = useState<View>({ x: 0, y: 0, s: 1 });
  viewRef.current = view;
  const [isPanning, setIsPanning] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [measureKey, setMeasureKey] = useState(0);

  const count = providers.length;

  // Layout: the gateway sits at the centre, providers start on a circle around
  // it (the user can drag any of them anywhere), the client hangs below.
  const R = Math.max(120, 80 + count * 11);
  const canvasW = R * 2 + 200;
  const canvasH = R * 2 + 284;
  const cx = canvasW / 2;
  const cy = canvasH / 2 - 40;
  const clientPos = { x: cx, y: cy + R + 90 };

  // Seed provider positions synchronously so the first paint is already laid
  // out (no centre-flash), and never re-scatter nodes the user has moved.
  const [positions, setPositions] = useState<Record<string, ProviderPos>>(() => {
    const seed: Record<string, ProviderPos> = {};
    providers.forEach((provider, index) => {
      const angle = (index / Math.max(providers.length, 1)) * Math.PI * 2 - Math.PI / 2;
      seed[provider.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
    });
    return seed;
  });

  // Collapse per-drag-frame measureKey bumps into one rAF so beams recompute
  // once per frame instead of once per pointermove.
  const requestMeasure = () => {
    if (measureScheduled.current) return;
    measureScheduled.current = true;
    requestAnimationFrame(() => {
      measureScheduled.current = false;
      setMeasureKey((key) => key + 1);
    });
  };

  // Stable ref per provider id (survives re-orders / adds).
  const refFor = useCallback((providerId: string): RefObject<HTMLDivElement | null> => {
    let ref = providerRefs.current.get(providerId);
    if (!ref) {
      ref = createRef<HTMLDivElement>();
      providerRefs.current.set(providerId, ref);
    }
    return ref;
  }, []);

  // Reduced-motion: freeze the pulse (duration ~0, no repeat).
  const reducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const beamMotion = {
    duration: reducedMotion ? 0.01 : 2,
    repeat: reducedMotion ? 0 : Infinity,
  };
  const beamDelay = (index: number) => (reducedMotion ? 0 : (index % 5) * 0.25);

  const fit = useCallback(() => {
    const panel = viewportRef.current;
    const diagram = diagramRef.current;
    if (!panel || !diagram) return;
    const panelW = panel.clientWidth;
    const panelH = panel.clientHeight;
    if (!panelW || !panelH) return;
    // offsetWidth already reflects the current --bs scale, so divide by it to
    // get the natural (scale 1) size and fit without a feedback loop.
    const scale = Number.parseFloat(diagram.style.getPropertyValue("--bs")) || 1;
    const natW = diagram.offsetWidth / scale;
    const natH = diagram.offsetHeight / scale;
    if (!natW || !natH) return;
    const s = clamp(
      Math.min((panelW - FIT_PADDING) / natW, (panelH - FIT_PADDING) / natH),
      MIN_SCALE,
      MAX_SCALE,
    );
    setView({ x: (panelW - natW * s) / 2, y: (panelH - natH * s) / 2, s });
  }, []);
  fitRef.current = fit;

  // Add circle positions for providers that appear after mount; existing
  // (possibly user-moved) nodes are left untouched.
  useEffect(() => {
    setPositions((prev) => {
      let next = prev;
      providers.forEach((provider, index) => {
        if (next[provider.id] === undefined) {
          if (next === prev) next = { ...prev };
          const angle = (index / Math.max(providers.length, 1)) * Math.PI * 2 - Math.PI / 2;
          next[provider.id] = { x: cx + R * Math.cos(angle), y: cy + R * Math.sin(angle) };
        }
      });
      return next;
    });
    requestMeasure();
  }, [count]);

  useEffect(() => {
    fitRef.current();
  }, [providers.length]);

  // Non-passive wheel listener so we can preventDefault the page scroll.
  useEffect(() => {
    const panel = viewportRef.current;
    if (!panel) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = panel.getBoundingClientRect();
      const px = event.clientX - rect.left;
      const py = event.clientY - rect.top;
      setView((current) => {
        const s = clamp(current.s * Math.exp(-event.deltaY * 0.0022), MIN_SCALE, MAX_SCALE);
        const k = s / current.s;
        return {
          x: px - (px - current.x) * k,
          y: py - (py - current.y) * k,
          s,
        };
      });
    };
    panel.addEventListener("wheel", onWheel, { passive: false });
    return () => panel.removeEventListener("wheel", onWheel);
  }, []);

  // Drag handling lives on window listeners (installed per pointerdown,
  // removed on pointerup) rather than pointer capture, which Chromium can
  // release mid-drag. A single handler serves both node-drags and canvas pans
  // by reading dragState; it reads viewRef so deltas scale correctly if the
  // zoom changes mid-drag.
  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const node = dragState.current.node;
      if (node) {
        // Deltas arrive in viewport pixels; convert to natural units so
        // positions stay resolution-independent across zoom levels.
        const dx = (event.clientX - node.px) / viewRef.current.s;
        const dy = (event.clientY - node.py) / viewRef.current.s;
        dragState.current.node = { ...node, px: event.clientX, py: event.clientY };
        setPositions((prev) => {
          const current = prev[node.providerId] ?? node.start;
          return { ...prev, [node.providerId]: { x: current.x + dx, y: current.y + dy } };
        });
        requestMeasure();
      } else if (dragState.current.pan) {
        const dx = event.clientX - dragState.current.pan.px;
        const dy = event.clientY - dragState.current.pan.py;
        dragState.current.pan = { px: event.clientX, py: event.clientY };
        setView((current) => ({ ...current, x: current.x + dx, y: current.y + dy }));
      }
    };
    const onUp = () => {
      if (!dragState.current.node && !dragState.current.pan) return;
      dragState.current.node = null;
      dragState.current.pan = null;
      setDraggingId(null);
      setIsPanning(false);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
    windowMove.current = onMove;
    windowUp.current = onUp;
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, []);

  // Pan the canvas by dragging the empty background.
  const onViewportPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    dragState.current.pan = { px: event.clientX, py: event.clientY };
    setIsPanning(true);
    window.addEventListener("pointermove", windowMove.current);
    window.addEventListener("pointerup", windowUp.current);
    window.addEventListener("pointercancel", windowUp.current);
  };

  // Drag an individual provider node anywhere in the canvas. stopPropagation
  // keeps it from also starting a pan on the viewport.
  const onProviderPointerDown = (
    event: React.PointerEvent<HTMLDivElement>,
    providerId: string,
    pos: ProviderPos,
  ) => {
    event.stopPropagation();
    dragState.current.node = { providerId, px: event.clientX, py: event.clientY, start: pos };
    setDraggingId(providerId);
    window.addEventListener("pointermove", windowMove.current);
    window.addEventListener("pointerup", windowUp.current);
    window.addEventListener("pointercancel", windowUp.current);
  };

  const zoomButtons = (factor: number) => {
    const panel = viewportRef.current;
    if (!panel) return;
    const pcx = panel.clientWidth / 2;
    const pcy = panel.clientHeight / 2;
    setView((current) => {
      const s = clamp(current.s * factor, MIN_SCALE, MAX_SCALE);
      const k = s / current.s;
      return { x: pcx - (pcx - current.x) * k, y: pcy - (pcy - current.y) * k, s };
    });
  };

  const diagramStyle: CSSProperties & { "--bs": number } = {
    "--bs": view.s,
    width: `${canvasW * view.s}px`,
    height: `${canvasH * view.s}px`,
    transform: `translate(${view.x}px, ${view.y}px)`,
  };

  return (
    <div className="beam-panel">
      <div
        className={`beam-viewport${isPanning ? " is-panning" : ""}`}
        ref={viewportRef}
        onPointerDown={onViewportPointerDown}
        onDoubleClick={fit}
      >
        <div className="beam-diagram" ref={diagramRef} style={diagramStyle}>
          {providers.map((provider) => {
            const pos = positions[provider.id] ?? { x: cx, y: cy };
            return (
              <div
                key={provider.id}
                className={`beam-node-row${draggingId === provider.id ? " is-dragging" : ""}`}
                style={{
                  left: `${(pos.x - PROVIDER_NODE / 2) * view.s}px`,
                  top: `${(pos.y - PROVIDER_NODE / 2) * view.s}px`,
                }}
                onPointerDown={(event) => onProviderPointerDown(event, provider.id, pos)}
              >
                <div className="beam-node beam-node-provider" ref={refFor(provider.id)}>
                  <img
                    className="beam-logo"
                    src={provider.logo}
                    alt=""
                    loading="lazy"
                    onError={(event) => {
                      const image = event.currentTarget;
                      image.onerror = null;
                      image.src = FALLBACK_LOGO;
                    }}
                  />
                </div>
                <span className="beam-label">{provider.name}</span>
              </div>
            );
          })}
          <div
            className="beam-center"
            style={{
              left: `${(cx - GATEWAY_NODE / 2) * view.s}px`,
              top: `${(cy - GATEWAY_NODE / 2) * view.s}px`,
            }}
          >
            <div className="beam-node beam-node-gateway" ref={centerRef}>
              <svg
                className="beam-gateway-mark"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d={GATEWAY_MARK_PATH} />
              </svg>
            </div>
            <span className="beam-label">{gateway?.name ?? "claudey"}</span>
          </div>
          <div
            className="beam-client"
            style={{
              left: `${(clientPos.x - CLIENT_NODE / 2) * view.s}px`,
              top: `${(clientPos.y - CLIENT_NODE / 2) * view.s}px`,
            }}
          >
            <div className="beam-node beam-node-client" ref={clientRef}>
              <svg
                className="beam-client-icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d={USER_ICON_PATH} />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <span className="beam-label">{client?.name ?? "Your agent"}</span>
          </div>
          {providers.map((provider, index) => (
            <AnimatedBeam
              key={`beam-${provider.id}`}
              containerRef={diagramRef}
              fromRef={refFor(provider.id)}
              toRef={centerRef}
              pathColor="#ff4d00"
              pathWidth={2 * view.s}
              pathOpacity={0.18}
              gradientStartColor="#ff4d00"
              gradientStopColor="#ffaa40"
              delay={beamDelay(index)}
              measureKey={measureKey}
              {...beamMotion}
            />
          ))}
          <AnimatedBeam
            containerRef={diagramRef}
            fromRef={centerRef}
            toRef={clientRef}
            reverse
            pathColor="#ff4d00"
            pathWidth={2 * view.s}
            pathOpacity={0.18}
            gradientStartColor="#ff4d00"
            gradientStopColor="#ffaa40"
            delay={reducedMotion ? 0 : 0.4}
            measureKey={measureKey}
            {...beamMotion}
          />
        </div>
      </div>
      <div className="beam-toolbar">
        <button
          type="button"
          className="beam-tool-btn"
          aria-label="Zoom in"
          onClick={() => zoomButtons(1.3)}
        >
          +
        </button>
        <button
          type="button"
          className="beam-tool-btn"
          aria-label="Zoom out"
          onClick={() => zoomButtons(1 / 1.3)}
        >
          −
        </button>
        <button type="button" className="beam-tool-btn" aria-label="Reset view" onClick={fit}>
          ⤢
        </button>
        <span className="beam-zoom-hint">drag models · drag background to pan · scroll to zoom</span>
      </div>
    </div>
  );
}