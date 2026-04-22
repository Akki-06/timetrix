import { useRef, useEffect, useCallback } from "react";

/**
 * TimetableGrid3D
 * A canvas-based 3D week × slot grid where lecture blocks
 * animate into cells — matching Timetrix brand colours.
 * Mouse-reactive rotation, depth-sorted rendering.
 */

const lerp = (a, b, t) => a + (b - a) * t;
const rand = (min, max) => Math.random() * (max - min) + min;

const DAYS   = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const SLOTS  = ["9:00", "10:00", "11:00", "12:00", "2:00", "3:00", "4:00"];
const COLS   = DAYS.length;
const ROWS   = SLOTS.length;

const PALETTE = [
  { r: 99,  g: 102, b: 241 },  // indigo
  { r: 20,  g: 184, b: 166 },  // teal
  { r: 139, g: 92,  b: 246 },  // purple
  { r: 245, g: 158, b: 11  },  // amber
  { r: 244, g: 63,  b: 94  },  // rose
  { r: 16,  g: 185, b: 129 },  // emerald
];

const COURSES = ["CS301", "MA201", "EC101", "CS302", "Lab", "Lab", "PE101", "DS201"];

function rgba(c, a) {
  return `rgba(${c.r},${c.g},${c.b},${a.toFixed(3)})`;
}

// Pre-assign colours & labels to cells
function buildGrid() {
  const cells = [];
  const filled = new Set();
  // seed ~60% cells
  for (let attempt = 0; attempt < 80; attempt++) {
    const col = Math.floor(rand(0, COLS));
    const row = Math.floor(rand(0, ROWS));
    const key = `${col}-${row}`;
    if (filled.has(key)) continue;
    filled.add(key);
    cells.push({
      col, row,
      color: PALETTE[Math.floor(rand(0, PALETTE.length))],
      label: COURSES[Math.floor(rand(0, COURSES.length))],
      // animation: each cell drops in at a random delay
      dropDelay: rand(0, 3.5),
      dropDuration: rand(0.5, 0.9),
      opacity: 0,
      targetOpacity: rand(0.55, 0.85),
      scaleY: 0,   // 0 → 1 drop-in
    });
  }
  return cells;
}

export default function TimetableGrid3D({ style, className }) {
  const canvasRef   = useRef(null);
  const mouseRef    = useRef({ x: 0, y: 0, active: false });
  const smoothMouse = useRef({ x: 0, y: 0 });
  const animRef     = useRef(null);
  const timeRef     = useRef(0);
  const cellsRef    = useRef(null);

  if (!cellsRef.current) cellsRef.current = buildGrid();

  // 3D projection
  const project = useCallback((x3, y3, z3, cx, cy, rotY, rotX) => {
    // rotate Y
    let x1 = x3 * Math.cos(rotY) - z3 * Math.sin(rotY);
    let z1 = x3 * Math.sin(rotY) + z3 * Math.cos(rotY);
    let y1 = y3;
    // rotate X
    let y2 = y1 * Math.cos(rotX) - z1 * Math.sin(rotX);
    let z2 = y1 * Math.sin(rotX) + z1 * Math.cos(rotX);
    const fov = 550;
    const scale = fov / (fov + z2);
    return { sx: cx + x1 * scale, sy: cy + y2 * scale, scale, z: z2 };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const cells = cellsRef.current;

    const resize = () => {
      const dpr  = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width  = rect.width  * dpr;
      canvas.height = rect.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    const onMove = (e) => {
      mouseRef.current.x = (e.clientX / window.innerWidth  - 0.5) * 2;
      mouseRef.current.y = (e.clientY / window.innerHeight - 0.5) * 2;
      mouseRef.current.active = true;
    };
    const onLeave = () => { mouseRef.current.active = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseleave", onLeave);

    const render = () => {
      const w  = canvas.getBoundingClientRect().width;
      const h  = canvas.getBoundingClientRect().height;
      const cx = w * 0.5;
      const cy = h * 0.5;
      const t  = timeRef.current;
      timeRef.current += 0.008;

      // smooth mouse / auto-rotate
      const tx = mouseRef.current.active
        ? mouseRef.current.x * 0.3
        : Math.sin(t * 0.6) * 0.18;
      const ty = mouseRef.current.active
        ? mouseRef.current.y * 0.18
        : Math.cos(t * 0.4) * 0.1;
      smoothMouse.current.x = lerp(smoothMouse.current.x, tx, 0.06);
      smoothMouse.current.y = lerp(smoothMouse.current.y, ty, 0.06);

      const rotY = -0.30 + smoothMouse.current.x;
      const rotX =  0.28 + smoothMouse.current.y;

      ctx.clearRect(0, 0, w, h);

      // ── Cell dimensions in 3D space ──
      const CW = 70;   // cell width  (3D)
      const CH = 46;   // cell height (3D)
      const GAP = 6;
      const stepX = CW + GAP;
      const stepY = CH + GAP;
      const gridW = COLS * stepX - GAP;
      const gridH = ROWS * stepY - GAP;
      const ox = -gridW / 2;  // centre the grid
      const oy = -gridH / 2;

      // Project all 4 corners of every cell for depth sort
      const quads = [];

      // ── Ghost grid lines (empty cells) ──
      for (let c = 0; c < COLS; c++) {
        for (let r = 0; r < ROWS; r++) {
          const x3 = ox + c * stepX;
          const y3 = oy + r * stepY;
          const corners = [
            project(x3,      y3,      0, cx, cy, rotY, rotX),
            project(x3 + CW, y3,      0, cx, cy, rotY, rotX),
            project(x3 + CW, y3 + CH, 0, cx, cy, rotY, rotX),
            project(x3,      y3 + CH, 0, cx, cy, rotY, rotX),
          ];
          const avgZ = corners.reduce((s, p) => s + p.z, 0) / 4;
          quads.push({ type: "empty", corners, avgZ, c, r });
        }
      }

      // ── Filled cells with drop-in animation ──
      cells.forEach(cell => {
        const elapsed = t - cell.dropDelay;
        if (elapsed < 0) {
          // not started yet — still render ghost
          cell.scaleY  = 0;
          cell.opacity = 0;
          return;
        }
        const progress = Math.min(1, elapsed / cell.dropDuration);
        // ease-out bounce
        const eased = 1 - Math.pow(1 - progress, 3);
        cell.scaleY  = eased;
        cell.opacity = eased * cell.targetOpacity;

        const x3 = ox + cell.col * stepX;
        // drop from above: starts CH above, lands at y3
        const y3base  = oy + cell.row * stepY;
        const y3start = y3base - CH * 1.2;
        const y3top   = lerp(y3start, y3base, eased);
        const y3bot   = y3top + CH * cell.scaleY;

        const corners = [
          project(x3,      y3top, 0, cx, cy, rotY, rotX),
          project(x3 + CW, y3top, 0, cx, cy, rotY, rotX),
          project(x3 + CW, y3bot, 0, cx, cy, rotY, rotX),
          project(x3,      y3bot, 0, cx, cy, rotY, rotX),
        ];
        const avgZ = corners.reduce((s, p) => s + p.z, 0) / 4;
        quads.push({ type: "filled", corners, avgZ, cell });
      });

      // depth sort — farthest first
      quads.sort((a, b) => a.avgZ - b.avgZ);

      quads.forEach(q => {
        const [tl, tr, br, bl] = q.corners;
        ctx.beginPath();
        ctx.moveTo(tl.sx, tl.sy);
        ctx.lineTo(tr.sx, tr.sy);
        ctx.lineTo(br.sx, br.sy);
        ctx.lineTo(bl.sx, bl.sy);
        ctx.closePath();

        if (q.type === "empty") {
          ctx.fillStyle   = "rgba(99,102,241,0.04)";
          ctx.strokeStyle = "rgba(99,102,241,0.12)";
          ctx.lineWidth   = 0.8;
          ctx.fill();
          ctx.stroke();
        } else {
          const { cell } = q;
          const avgScale = tl.scale;
          // filled rect gradient
          const grd = ctx.createLinearGradient(tl.sx, tl.sy, br.sx, br.sy);
          grd.addColorStop(0, rgba(cell.color, cell.opacity * 0.9));
          grd.addColorStop(1, rgba(cell.color, cell.opacity * 0.55));
          ctx.fillStyle   = grd;
          ctx.strokeStyle = rgba(cell.color, cell.opacity * 0.5);
          ctx.lineWidth   = 1 * avgScale;
          ctx.fill();
          ctx.stroke();

          // label — only if tall enough
          const cellH = Math.abs(br.sy - tl.sy);
          if (cellH > 10 && cell.scaleY > 0.5) {
            const midX = (tl.sx + br.sx) / 2;
            const midY = (tl.sy + br.sy) / 2;
            ctx.fillStyle  = `rgba(255,255,255,${Math.min(0.9, cell.opacity * 1.3)})`;
            ctx.font       = `600 ${Math.round(9 * avgScale)}px Inter,system-ui,sans-serif`;
            ctx.textAlign  = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(cell.label, midX, midY);
          }
        }
      });

      // ── Day header labels ──
      DAYS.forEach((day, c) => {
        const x3  = ox + c * stepX + CW / 2;
        const y3  = oy - 20;
        const pp  = project(x3, y3, 0, cx, cy, rotY, rotX);
        ctx.fillStyle   = "rgba(148,163,184,0.5)";
        ctx.font        = `600 ${Math.round(9 * pp.scale)}px Inter,system-ui,sans-serif`;
        ctx.textAlign   = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(day, pp.sx, pp.sy);
      });

      // ── Slot time labels ──
      SLOTS.forEach((slot, r) => {
        const x3  = ox - 18;
        const y3  = oy + r * stepY + CH / 2;
        const pp  = project(x3, y3, 0, cx, cy, rotY, rotX);
        ctx.fillStyle   = "rgba(148,163,184,0.4)";
        ctx.font        = `500 ${Math.round(8 * pp.scale)}px Inter,system-ui,sans-serif`;
        ctx.textAlign   = "right";
        ctx.textBaseline = "middle";
        ctx.fillText(slot, pp.sx, pp.sy);
      });

      // ── Ambient glow orbs on canvas ──
      const g1 = ctx.createRadialGradient(cx * 0.4, cy * 0.4, 0, cx * 0.4, cy * 0.4, 300);
      g1.addColorStop(0, "rgba(99,102,241,0.05)");
      g1.addColorStop(1, "transparent");
      ctx.fillStyle = g1;
      ctx.fillRect(0, 0, w, h);

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
      style={{ width: "100%", height: "100%", display: "block", ...style }}
    />
  );
}
