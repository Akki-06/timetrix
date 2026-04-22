import { useRef, useEffect, useCallback } from "react";

/**
 * Interactive 3D Neural Network — horizontal layout
 * Input(5) → Hidden1(8) → Hidden2(8) → Output(3)
 * Left-to-right flow, strong 3D perspective, mouse-reactive
 */

const lerp = (a, b, t) => a + (b - a) * t;
const rand = (min, max) => Math.random() * (max - min) + min;

const COLORS = {
  indigo: { r: 99, g: 102, b: 241 },
  teal: { r: 20, g: 184, b: 166 },
  white: { r: 220, g: 225, b: 245 },
};

function rgbaStr(c, a) {
  return `rgba(${c.r},${c.g},${c.b},${a})`;
}

function lerpColor(c1, c2, t) {
  return {
    r: Math.round(lerp(c1.r, c2.r, t)),
    g: Math.round(lerp(c1.g, c2.g, t)),
    b: Math.round(lerp(c1.b, c2.b, t)),
  };
}

/* ── horizontal 4-layer NN: Input(left) → Output(right) ── */
function createNetwork() {
  const layers = [5, 8, 8, 3];
  const layerLabels = ["Input", "Hidden 1", "Hidden 2", "Output"];
  const nodes = [];
  const edges = [];

  const layerGap = 180; // horizontal spacing between layers
  const totalWidth = (layers.length - 1) * layerGap;

  layers.forEach((count, li) => {
    const x = li * layerGap - totalWidth / 2; // left to right
    const nodeSpacing = 55;
    const totalHeight = (count - 1) * nodeSpacing;
    const colorT = li / (layers.length - 1);
    const color = lerpColor(COLORS.indigo, COLORS.teal, colorT);

    for (let ni = 0; ni < count; ni++) {
      const y = ni * nodeSpacing - totalHeight / 2;
      // z variation per layer for depth — inner layers pushed back
      const layerZ = li === 1 || li === 2 ? rand(-80, -30) : rand(20, 60);
      const nodeIdx = nodes.length;

      nodes.push({
        x, y, z: layerZ,
        baseX: x,
        baseY: y,
        baseZ: layerZ,
        radius: li === 0 || li === layers.length - 1 ? 5.5 : 6.5,
        color,
        layer: li,
        layerLabel: layerLabels[li],
        pulsePhase: rand(0, Math.PI * 2),
        idx: nodeIdx,
      });

      // fully connected to previous layer
      if (li > 0) {
        const prevStart = nodes.length - count - layers[li - 1];
        for (let pi = 0; pi < layers[li - 1]; pi++) {
          edges.push({
            from: prevStart + pi,
            to: nodeIdx,
            pulseOffset: rand(0, 25),
            pulseSpeed: rand(0.06, 0.14),
            opacity: rand(0.05, 0.16),
          });
        }
      }
    }
  });

  return { nodes, edges, layers, layerLabels };
}

function createParticles(count) {
  const particles = [];
  for (let i = 0; i < count; i++) {
    particles.push({
      x: rand(-700, 700),
      y: rand(-500, 500),
      z: rand(-250, 250),
      vx: rand(-0.08, 0.08),
      vy: rand(-0.06, 0.06),
      radius: rand(0.6, 1.8),
      alpha: rand(0.06, 0.25),
      color: Math.random() > 0.5 ? COLORS.indigo : COLORS.teal,
    });
  }
  return particles;
}

export default function NeuralNetwork3D({ style, className }) {
  const canvasRef = useRef(null);
  const mouseRef = useRef({ x: 0, y: 0, active: false });
  const smoothMouse = useRef({ x: 0, y: 0 });
  const networkRef = useRef(null);
  const particlesRef = useRef(null);
  const animRef = useRef(null);
  const timeRef = useRef(0);

  /* 3D projection with strong perspective */
  const project = useCallback((node, cx, cy, rotY, rotX) => {
    // rotate around Y (horizontal mouse)
    let x1 = node.x * Math.cos(rotY) - node.z * Math.sin(rotY);
    let z1 = node.x * Math.sin(rotY) + node.z * Math.cos(rotY);
    let y1 = node.y;

    // rotate around X (vertical mouse)
    let y2 = y1 * Math.cos(rotX) - z1 * Math.sin(rotX);
    let z2 = y1 * Math.sin(rotX) + z1 * Math.cos(rotX);

    const perspective = 600; // lower = stronger 3D effect
    const scale = perspective / (perspective + z2);
    return { x: cx + x1 * scale, y: cy + y2 * scale, scale, z: z2 };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    if (!networkRef.current) networkRef.current = createNetwork();
    if (!particlesRef.current) particlesRef.current = createParticles(50);

    const network = networkRef.current;
    const particles = particlesRef.current;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    /* global mouse tracking */
    const onMove = (e) => {
      mouseRef.current.x = (e.clientX / window.innerWidth - 0.5) * 2;
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
      mouseRef.current.active = true;
    };
    const onLeave = () => { mouseRef.current.active = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseleave", onLeave);

    const render = () => {
      const w = canvas.getBoundingClientRect().width;
      const h = canvas.getBoundingClientRect().height;
      const cx = w / 2;
      const cy = h / 2;
      const t = timeRef.current;
      timeRef.current += 0.008;

      // smooth mouse — MORE SENSITIVE (higher lerp factor + larger rotation)
      const targetX = mouseRef.current.active ? mouseRef.current.x : Math.sin(t * 1.2) * 0.15;
      const targetY = mouseRef.current.active ? mouseRef.current.y : Math.cos(t * 0.8) * 0.1;
      smoothMouse.current.x = lerp(smoothMouse.current.x, targetX, 0.08);
      smoothMouse.current.y = lerp(smoothMouse.current.y, targetY, 0.08);

      const BASE_ROT_Y = -0.35; // base tilt to the left
      const BASE_ROT_X = 0.1;   // slight downward tilt for natural perspective
      const rotY = BASE_ROT_Y + smoothMouse.current.x * 0.4;
      const rotX = BASE_ROT_X + smoothMouse.current.y * 0.25;

      ctx.clearRect(0, 0, w, h);

      // ambient glows
      const g1 = ctx.createRadialGradient(cx * 0.6, cy * 0.5, 0, cx * 0.6, cy * 0.5, 400);
      g1.addColorStop(0, "rgba(99,102,241,0.04)");
      g1.addColorStop(1, "transparent");
      ctx.fillStyle = g1;
      ctx.fillRect(0, 0, w, h);

      const g2 = ctx.createRadialGradient(cx * 1.4, cy * 1.4, 0, cx * 1.4, cy * 1.4, 350);
      g2.addColorStop(0, "rgba(20,184,166,0.03)");
      g2.addColorStop(1, "transparent");
      ctx.fillStyle = g2;
      ctx.fillRect(0, 0, w, h);

      // gentle breathing
      network.nodes.forEach((node) => {
        node.x = node.baseX + Math.sin(t * 2 + node.pulsePhase) * 1.5;
        node.y = node.baseY + Math.cos(t * 1.5 + node.pulsePhase * 1.3) * 1.5;
        node.z = node.baseZ + Math.sin(t * 1.2 + node.pulsePhase * 0.7) * 4;
      });

      const projected = network.nodes.map((n) => ({
        ...project(n, cx, cy, rotY, rotX),
        node: n,
      }));

      // ── edges with training pulses ──
      network.edges.forEach((edge) => {
        const a = projected[edge.from];
        const b = projected[edge.to];
        if (!a || !b) return;

        const edgeColor = lerpColor(a.node.color, b.node.color, 0.5);
        const avgScale = (a.scale + b.scale) / 2;

        // base line
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = rgbaStr(edgeColor, edge.opacity * avgScale);
        ctx.lineWidth = 0.7 * avgScale;
        ctx.stroke();

        // training pulse traveling A→B
        const pulseT = ((t * edge.pulseSpeed + edge.pulseOffset) % 1);
        const px = lerp(a.x, b.x, pulseT);
        const py = lerp(a.y, b.y, pulseT);
        const ps = lerp(a.scale, b.scale, pulseT);
        const pulseAlpha = Math.sin(pulseT * Math.PI) * 0.55;

        if (pulseAlpha > 0.04) {
          const pc = lerpColor(COLORS.indigo, COLORS.teal, pulseT);
          const grd = ctx.createRadialGradient(px, py, 0, px, py, 12 * ps);
          grd.addColorStop(0, rgbaStr(pc, pulseAlpha * 0.4));
          grd.addColorStop(1, rgbaStr(pc, 0));
          ctx.fillStyle = grd;
          ctx.beginPath();
          ctx.arc(px, py, 12 * ps, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = rgbaStr(pc, pulseAlpha * 0.8);
          ctx.beginPath();
          ctx.arc(px, py, 2.2 * ps, 0, Math.PI * 2);
          ctx.fill();
        }
      });

      // ── nodes (depth sorted — farther drawn first) ──
      const sorted = [...projected].sort((a, b) => a.z - b.z);
      sorted.forEach((p) => {
        const n = p.node;
        const pulse = 1 + Math.sin(t * 3 + n.pulsePhase) * 0.12;
        const r = n.radius * p.scale * pulse;
        const alpha = Math.min(1, 0.5 + p.scale * 0.5);
        // size difference by depth already handled by scale

        // big outer glow
        const grd = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r * 6);
        grd.addColorStop(0, rgbaStr(n.color, alpha * 0.15));
        grd.addColorStop(1, rgbaStr(n.color, 0));
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 6, 0, Math.PI * 2);
        ctx.fill();

        // ring (3D feel)
        ctx.strokeStyle = rgbaStr(n.color, alpha * 0.3);
        ctx.lineWidth = 1.5 * p.scale;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 1.8, 0, Math.PI * 2);
        ctx.stroke();

        // filled node
        const nodeFill = ctx.createRadialGradient(
          p.x - r * 0.3, p.y - r * 0.3, 0,
          p.x, p.y, r
        );
        nodeFill.addColorStop(0, rgbaStr(COLORS.white, alpha * 0.7));
        nodeFill.addColorStop(0.5, rgbaStr(n.color, alpha * 0.9));
        nodeFill.addColorStop(1, rgbaStr(n.color, alpha * 0.5));
        ctx.fillStyle = nodeFill;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fill();
      });

      // ── layer labels (below each column) ──
      ctx.font = "600 11px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      const layerInfo = {};
      projected.forEach((p) => {
        const li = p.node.layer;
        if (!(li in layerInfo)) {
          layerInfo[li] = { sumX: 0, maxY: -Infinity, count: 0, label: p.node.layerLabel };
        }
        layerInfo[li].sumX += p.x;
        layerInfo[li].count++;
        if (p.y > layerInfo[li].maxY) layerInfo[li].maxY = p.y;
      });

      Object.values(layerInfo).forEach((li) => {
        const avgX = li.sumX / li.count;
        ctx.fillStyle = "rgba(148,163,184,0.4)";
        ctx.fillText(li.label, avgX, li.maxY + 28);
      });

      // ── ambient particles ──
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x > 700) p.x = -700;
        if (p.x < -700) p.x = 700;
        if (p.y > 500) p.y = -500;
        if (p.y < -500) p.y = 500;

        const pp = project(p, cx, cy, rotY * 0.15, rotX * 0.15);
        ctx.fillStyle = rgbaStr(p.color, p.alpha * pp.scale);
        ctx.beginPath();
        ctx.arc(pp.x, pp.y, p.radius * pp.scale, 0, Math.PI * 2);
        ctx.fill();
      });

      // ── epoch bar — pushed to very bottom ──
      const barW = 90;
      const barX = cx - barW / 2;
      const barY = h - 14; // near absolute bottom
      const progress = (Math.sin(t * 3) + 1) / 2;

      ctx.fillStyle = "rgba(99,102,241,0.05)";
      ctx.beginPath();
      ctx.roundRect(barX, barY, barW, 2.5, 2);
      ctx.fill();

      const gb = ctx.createLinearGradient(barX, 0, barX + barW * progress, 0);
      gb.addColorStop(0, "rgba(99,102,241,0.35)");
      gb.addColorStop(1, "rgba(20,184,166,0.35)");
      ctx.fillStyle = gb;
      ctx.beginPath();
      ctx.roundRect(barX, barY, barW * progress, 2.5, 2);
      ctx.fill();

      ctx.fillStyle = "rgba(148,163,184,0.3)";
      ctx.font = "500 8px Inter, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`Epoch ${Math.round(progress * 100)}`, cx, barY - 5);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);

    return () => {
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseleave", onLeave);
      cancelAnimationFrame(animRef.current);
    };
  }, [project]);

  return (
    <canvas
      ref={canvasRef}
      className={className}
      style={{
        width: "100%",
        height: "100%",
        display: "block",
        ...style,
      }}
    />
  );
}
