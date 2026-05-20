import { useEffect, useMemo, useRef, useState } from "react";
import {
  FaCheckCircle, FaCog, FaRocket, FaTimes, FaSpinner,
} from "react-icons/fa";

/**
 * Full-screen overlay rendered while the scheduler is running.
 *
 * Props:
 *   open         — boolean, controls visibility
 *   events       — array of SSE events appended in order
 *   estimate     — { estimated_seconds, total_offerings, total_sections } | null
 *   status       — "running" | "success" | "partial" | "failed" | "error"
 *   onClose      — called when the close button is clicked
 *   onViewResult — called when the user wants to navigate to the timetable
 *
 * The countdown logic intentionally allows the displayed remaining-time to
 * go to zero and then keep counting elapsed-only, so the UI never shows a
 * misleading "0 seconds left" when generation takes longer than estimated.
 */
function pad2(n) {
  return n < 10 ? `0${n}` : `${n}`;
}

function formatDuration(secs) {
  if (secs < 0) secs = 0;
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${pad2(m)}:${pad2(s)}`;
}

function phaseEmoji(phase) {
  switch (phase) {
    case "load":        return "📦";
    case "auto_assign": return "👤";
    case "cpsat":       return "🧠";
    case "labs":        return "🔬";
    case "theory":      return "📚";
    case "repair":      return "🔧";
    case "idle_pack":   return "🗂️";
    case "slot_pack":   return "🧩";
    case "verify":      return "🔍";
    case "save":        return "💾";
    default:            return "⚙️";
  }
}

function lineColor(ev) {
  if (ev.success) return "var(--success, #10b981)";
  if (ev.type === "error")   return "var(--danger, #ef4444)";
  if (ev.type === "phase")   return "var(--brand, #6366f1)";
  if (ev.type === "assign") {
    switch (ev.kind) {
      case "LAB":      return "#f59e0b";
      case "PE":       return "#a855f7";
      case "COMBINED": return "#06b6d4";
      case "THEORY":   return "#22d3ee";
      case "FACULTY":  return "#84cc16";
      default:         return "#94a3b8";
    }
  }
  return "var(--muted, #94a3b8)";
}

export default function GenerationProgressOverlay({
  open,
  events,
  estimate,
  status,
  onClose,
  onViewResult,
}) {
  // Animated elapsed seconds (drives the countdown). We tick locally so the UI
  // stays smooth even when no new SSE events arrive for a few seconds.
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    if (status !== "running") return;
    startRef.current = Date.now();
    const id = setInterval(() => {
      setElapsed((Date.now() - (startRef.current ?? Date.now())) / 1000);
    }, 200);
    return () => clearInterval(id);
  }, [open, status]);

  const totalEst = estimate?.estimated_seconds ?? 30;
  // Progress percent: cap at 95% until status becomes terminal so the bar
  // never "completes early" if the engine finishes faster than the estimate.
  const rawPct = Math.min(95, (elapsed / totalEst) * 100);
  const isDone = status !== "running";
  const pct = isDone ? 100 : rawPct;

  // Remaining: never negative; show "wrapping up..." if we overshot
  const remaining = Math.max(0, totalEst - elapsed);
  const overshot = !isDone && elapsed > totalEst;

  // Auto-scroll terminal to bottom on new events
  const terminalRef = useRef(null);
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [events]);

  // Derive a compact "current phase" for the headline
  const currentPhase = useMemo(() => {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].type === "phase") return events[i];
    }
    return null;
  }, [events]);

  // Count successful allocations for the live stat strip
  const assignCount = useMemo(
    () => events.filter((e) => e.type === "assign").length,
    [events],
  );
  const phaseCount = useMemo(
    () => events.filter((e) => e.type === "phase").length,
    [events],
  );

  if (!open) return null;

  return (
    <div className="gpo-overlay" role="dialog" aria-modal="true">
      <div className="gpo-modal">

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="gpo-header">
          <div className="gpo-title-block">
            <div className="gpo-icon">
              {status === "running" ? (
                <FaCog className="gpo-icon-spin" />
              ) : status === "success" ? (
                <FaCheckCircle />
              ) : status === "partial" ? (
                <FaCheckCircle style={{ color: "#f59e0b" }} />
              ) : (
                <FaTimes />
              )}
            </div>
            <div>
              <h2 className="gpo-title">
                {status === "running"
                  ? "Generating timetable…"
                  : status === "success"
                  ? "Generation complete"
                  : status === "partial"
                  ? "Partially generated"
                  : "Generation failed"}
              </h2>
              <p className="gpo-subtitle">
                {currentPhase
                  ? `${phaseEmoji(currentPhase.phase)} ${currentPhase.msg}`
                  : "Initializing…"}
              </p>
            </div>
          </div>

          {/* Close — only after terminal status */}
          {isDone && (
            <button className="gpo-close" onClick={onClose} aria-label="Close">
              <FaTimes />
            </button>
          )}
        </div>

        {/* ── Countdown + progress bar ──────────────────────────────────── */}
        <div className="gpo-progress-block">
          <div className="gpo-timer">
            <div className="gpo-timer-cell">
              <span className="gpo-timer-val">{formatDuration(elapsed)}</span>
              <span className="gpo-timer-lbl">Elapsed</span>
            </div>
            <div className="gpo-timer-sep">·</div>
            <div className="gpo-timer-cell">
              <span className="gpo-timer-val">
                {isDone ? "—" : overshot ? "wrapping up" : formatDuration(remaining)}
              </span>
              <span className="gpo-timer-lbl">
                {isDone ? "Final" : "Estimated remaining"}
              </span>
            </div>
            <div className="gpo-timer-sep">·</div>
            <div className="gpo-timer-cell">
              <span className="gpo-timer-val">{formatDuration(totalEst)}</span>
              <span className="gpo-timer-lbl">Initial estimate</span>
            </div>
          </div>

          <div className="gpo-bar-wrap">
            <div
              className={`gpo-bar ${isDone ? "gpo-bar-done" : ""}`}
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="gpo-meta-row">
            <span>
              {estimate?.total_offerings ?? "?"} offerings · {estimate?.total_sections ?? "?"} sections
            </span>
            <span>
              <strong style={{ color: "var(--brand)" }}>{assignCount}</strong> assignments ·{" "}
              <strong style={{ color: "var(--accent)" }}>{phaseCount}</strong> phases
            </span>
          </div>
        </div>

        {/* ── Terminal-style log ────────────────────────────────────────── */}
        <div className="gpo-terminal" ref={terminalRef}>
          {events.length === 0 ? (
            <div className="gpo-terminal-empty">
              <FaSpinner className="gpo-icon-spin" />
              <span>Connecting to scheduler…</span>
            </div>
          ) : (
            events.map((ev, i) => (
              <div key={i} className="gpo-line" style={{ color: lineColor(ev) }}>
                <span className="gpo-line-time">[{ev.elapsed?.toFixed(1) ?? "0.0"}s]</span>
                {ev.type === "assign" ? (
                  <>
                    <span className="gpo-line-kind">{ev.kind} ✓</span>
                    <span className="gpo-line-msg">
                      {ev.course} <span className="gpo-line-dim">({ev.section})</span>
                      {ev.faculty && (
                        <>
                          {" → "}
                          <span style={{ color: "#84cc16" }}>{ev.faculty}</span>
                        </>
                      )}
                      {ev.room && (
                        <>
                          {" · "}
                          <span style={{ color: "#06b6d4" }}>R{ev.room}</span>
                        </>
                      )}
                      {ev.day && (
                        <>
                          {" · "}
                          <span style={{ color: "var(--muted)" }}>
                            {ev.day} S{ev.slot}
                          </span>
                        </>
                      )}
                    </span>
                  </>
                ) : ev.type === "phase" ? (
                  <>
                    <span className="gpo-line-kind">▶ {phaseEmoji(ev.phase)}</span>
                    <span className="gpo-line-msg">{ev.msg}</span>
                  </>
                ) : ev.type === "error" ? (
                  <>
                    <span className="gpo-line-kind">✕ ERROR</span>
                    <span className="gpo-line-msg">{ev.msg}</span>
                  </>
                ) : (
                  <span className="gpo-line-msg">{ev.msg}</span>
                )}
              </div>
            ))
          )}
        </div>

        {/* ── Footer actions ─────────────────────────────────────────────── */}
        {isDone && (
          <div className="gpo-footer">
            {status !== "error" && status !== "failed" ? (
              <button className="gpo-view-btn" onClick={onViewResult}>
                <FaRocket /> View Timetable
              </button>
            ) : (
              <button className="gpo-close-btn" onClick={onClose}>
                Close
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
