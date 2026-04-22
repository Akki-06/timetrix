import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import NeuralNetwork3D from "../components/NeuralNetwork3D";
import {
  FaArrowRight,
  FaBrain,
  FaShieldAlt,
  FaUsers,
  FaCogs,
  FaChartLine,
  FaFileExport,
  FaGithub,
  FaLinkedinIn,
  FaCheck,
  FaBolt,
  FaRobot,
  FaClock,
  FaBars,
} from "react-icons/fa";
import "../styles/landing.css";

/* ── stat marquee items ── */
const STATS = [
  { icon: <FaCheck />, text: "100% Conflict-Free", bg: "rgba(16,185,129,0.12)", color: "#34d399" },
  { icon: <FaUsers />, text: "3 Role Access", bg: "rgba(99,102,241,0.12)", color: "#818cf8" },
  { icon: <FaBolt />, text: "Auto-Assign", bg: "rgba(245,158,11,0.12)", color: "#fbbf24" },
  { icon: <FaRobot />, text: "ML-Powered", bg: "rgba(139,92,246,0.12)", color: "#a78bfa" },
  { icon: <FaClock />, text: "Seconds, Not Hours", bg: "rgba(20,184,166,0.12)", color: "#2dd4bf" },
  { icon: <FaShieldAlt />, text: "Constraint-Aware", bg: "rgba(244,63,94,0.12)", color: "#fb7185" },
  { icon: <FaBrain />, text: "GraphSAGE GNN", bg: "rgba(99,102,241,0.12)", color: "#818cf8" },
  { icon: <FaChartLine />, text: "Random Forest AI", bg: "rgba(20,184,166,0.12)", color: "#2dd4bf" },
];

/* ── steps ── */
const STEPS = [
  {
    num: "01",
    icon: <FaCogs />,
    title: "Configure",
    desc: "Set up your faculty, courses, rooms, and constraints. Bulk upload from Excel or add manually through our intuitive UI.",
  },
  {
    num: "02",
    icon: <FaBrain />,
    title: "Generate",
    desc: "Our Graph Neural Network analyzes relationships, while the constraint engine ensures zero conflicts across all dimensions.",
  },
  {
    num: "03",
    icon: <FaChartLine />,
    title: "Deploy",
    desc: "View optimized timetables by section, faculty, or room. Export, share, and publish — all roles get instant access.",
  },
];

/* ── features ── */
const FEATURES = [
  {
    icon: <FaBrain />,
    title: "Smart AI Scheduling",
    desc: "GraphSAGE GNN + Random Forest ensemble predicts optimal slot assignments with 111-dimensional feature vectors.",
    bg: "rgba(99,102,241,0.12)",
    color: "#818cf8",
  },
  {
    icon: <FaShieldAlt />,
    title: "Conflict Detection",
    desc: "Hard constraints guarantee zero double-booking for faculty, rooms, and student groups. Lab slots always paired.",
    bg: "rgba(16,185,129,0.12)",
    color: "#34d399",
  },
  {
    icon: <FaUsers />,
    title: "Faculty Management",
    desc: "3-level exclusion system — program, semester, course. Role-based workload limits from Dean to Visiting faculty.",
    bg: "rgba(245,158,11,0.12)",
    color: "#fbbf24",
  },
  {
    icon: <FaCogs />,
    title: "Multi-Role Access",
    desc: "Admin controls everything. Teachers see their schedule. Students view their timetable. Each role, tailored access.",
    bg: "rgba(139,92,246,0.12)",
    color: "#a78bfa",
  },
  {
    icon: <FaChartLine />,
    title: "ML Optimization",
    desc: "Heterogeneous graph with 5 node types, 7 edge types. 32-dim embeddings via link prediction training.",
    bg: "rgba(20,184,166,0.12)",
    color: "#2dd4bf",
  },
  {
    icon: <FaFileExport />,
    title: "Real-Time Export",
    desc: "Dynamic color-coded timetable grids with legend. Version history, PDF export, and notifications built-in.",
    bg: "rgba(244,63,94,0.12)",
    color: "#fb7185",
  },
];

/* ── tech stack ── */
const TECH = [
  { icon: "⚛️", name: "React 19", detail: "Frontend + Vite 7" },
  { icon: "🐍", name: "Django 6", detail: "REST API Backend" },
  { icon: "🧠", name: "PyTorch", detail: "GraphSAGE GNN" },
  { icon: "🌲", name: "scikit-learn", detail: "Random Forest" },
];

/* ── mock timetable data ── */
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const TIMES = ["9:00", "10:00", "11:00", "12:00", "2:00", "3:00"];
const MOCK_FILLS = {
  "0-0": { cls: "brand-fill", label: "CS301" },
  "0-2": { cls: "accent-fill", label: "Lab" },
  "0-3": { cls: "accent-fill", label: "Lab" },
  "1-1": { cls: "purple-fill", label: "MA201" },
  "1-4": { cls: "brand-fill", label: "CS302" },
  "2-0": { cls: "warning-fill", label: "EC101" },
  "2-2": { cls: "brand-fill", label: "CS301" },
  "3-1": { cls: "accent-fill", label: "Lab" },
  "3-2": { cls: "accent-fill", label: "Lab" },
  "3-4": { cls: "purple-fill", label: "MA201" },
  "4-0": { cls: "warning-fill", label: "EC101" },
  "4-3": { cls: "brand-fill", label: "CS302" },
  "5-1": { cls: "brand-fill", label: "CS301" },
};

export default function LandingPage() {
  const [scrolled, setScrolled] = useState(false);
  const revealRefs = useRef([]);

  /* scroll → navbar shrink */
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  /* IntersectionObserver → section reveals */
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.12 }
    );

    revealRefs.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
  }, []);

  const addRevealRef = (el) => {
    if (el && !revealRefs.current.includes(el)) revealRefs.current.push(el);
  };

  return (
    <div className="landing-root">
      {/* subtle grid bg */}
      <div className="lp-grid-bg" />

      {/* ────── NAVBAR ────── */}
      <nav className={`lp-navbar${scrolled ? " scrolled" : ""}`}>
        <a href="#" className="lp-nav-logo">
          <div className="lp-nav-logo-icon">
            <svg width="20" height="20" viewBox="0 0 48 48" fill="none">
              <path
                d="M14 16h20v2H14zM14 22h20v2H14zM14 28h14v2H14zM32 26l6 6-6 6"
                stroke="#fff"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <span className="lp-nav-logo-text">TIMETRIX</span>
        </a>

        <ul className="lp-nav-links">
          <li><a href="#about">About</a></li>
          <li><a href="#features">Features</a></li>
          <li><a href="#tech">Tech Stack</a></li>
          <li><a href="#developer">Developer</a></li>
        </ul>

        <Link to="/login" className="lp-nav-cta">
          Get Started <FaArrowRight />
        </Link>

        <button className="lp-nav-toggle" aria-label="Menu">
          <FaBars />
        </button>
      </nav>

      {/* ────── HERO ────── */}
      <section className="lp-hero" id="about">
        <div className="lp-hero-inner">
          <div className="lp-hero-content">
            <div className="lp-hero-badge">
              <span className="lp-hero-badge-dot" />
              Powered by GNN + Random Forest AI
            </div>

            <h1 className="lp-hero-title">
              Schedule<br />
              <span className="gradient-text">Smarter.</span><br />
              Not Harder.
            </h1>

            <p className="lp-hero-subtitle">
              AI-powered timetable generation for educational institutions. 
              Zero conflicts. Total control. Built with Graph Neural Networks 
              and constraint-based optimization.
            </p>

            <div className="lp-hero-actions">
              <Link to="/login" className="lp-btn-primary">
                Get Started <FaArrowRight />
              </Link>
              <a href="#showcase" className="lp-btn-ghost">
                See It In Action
              </a>
            </div>
          </div>

          <div className="lp-hero-visual">
            <NeuralNetwork3D />
          </div>
        </div>
      </section>

      {/* ────── STATS MARQUEE ────── */}
      <div className="lp-stats-strip">
        <div className="lp-stats-track">
          {[...STATS, ...STATS].map((s, i) => (
            <div key={i} className="lp-stat-pill">
              <div
                className="lp-stat-pill-icon"
                style={{ background: s.bg, color: s.color }}
              >
                {s.icon}
              </div>
              <span className="lp-stat-pill-text">{s.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ────── HOW IT WORKS ────── */}
      <section className="lp-section" id="how-it-works">
        <div className="lp-section-header lp-reveal" ref={addRevealRef}>
          <div className="lp-section-label">⚡ How It Works</div>
          <h2 className="lp-section-title">
            From Chaos to Order<br />in Three Steps
          </h2>
          <p className="lp-section-desc">
            No more spreadsheet nightmares. Define your constraints, let the AI do the heavy lifting, 
            and deploy conflict-free timetables in seconds.
          </p>
        </div>

        <div className="lp-steps-grid">
          {STEPS.map((step, i) => (
            <div
              key={i}
              className="lp-step-card lp-reveal"
              ref={addRevealRef}
              style={{ transitionDelay: `${i * 0.15}s` }}
            >
              <div className="lp-step-number">{step.num}</div>
              <div
                className="lp-step-icon"
                style={{
                  color: i === 0 ? "#818cf8" : i === 1 ? "#2dd4bf" : "#fbbf24",
                }}
              >
                {step.icon}
              </div>
              <h3 className="lp-step-title">{step.title}</h3>
              <p className="lp-step-desc">{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ────── SHOWCASE (floating UI) ────── */}
      <section className="lp-showcase" id="showcase">
        <div className="lp-showcase-inner">
          <div className="lp-section-header lp-reveal" ref={addRevealRef}>
            <div className="lp-section-label">🖥️ See It In Action</div>
            <h2 className="lp-section-title">
              Intelligent Timetables,<br />Beautifully Rendered
            </h2>
            <p className="lp-section-desc">
              Color-coded grids, multi-view layouts, and real-time conflict detection — 
              all powered by our constraint-aware scheduling engine.
            </p>
          </div>

          <div className="lp-showcase-frame lp-reveal" ref={addRevealRef} style={{ position: "relative" }}>
            {/* floating badges */}
            <div className="lp-float-badge">
              <div className="lp-float-badge-icon" style={{ background: "rgba(16,185,129,0.15)", color: "#34d399" }}>
                <FaCheck />
              </div>
              AI Generated ✓
            </div>
            <div className="lp-float-badge">
              <div className="lp-float-badge-icon" style={{ background: "rgba(99,102,241,0.15)", color: "#818cf8" }}>
                <FaShieldAlt />
              </div>
              No Conflicts ✓
            </div>
            <div className="lp-float-badge">
              <div className="lp-float-badge-icon" style={{ background: "rgba(245,158,11,0.15)", color: "#fbbf24" }}>
                <FaBolt />
              </div>
              Optimized ✓
            </div>

            {/* browser chrome */}
            <div className="lp-browser-chrome">
              <div className="lp-browser-dots">
                <span /><span /><span />
              </div>
              <div className="lp-browser-url">localhost:5173 — TIMETRIX Dashboard</div>
            </div>

            {/* mockup body */}
            <div className="lp-mockup-body">
              <div className="lp-mockup-header">
                <span className="lp-mockup-logo">TIMETRIX</span>
                <div className="lp-mockup-badges">
                  <span className="lp-mockup-badge-mini">✓ Published</span>
                  <span className="lp-mockup-badge-mini">v2.1</span>
                </div>
              </div>

              <div className="lp-mockup-grid">
                {/* header row */}
                <div className="lp-mockup-cell header">Time</div>
                {DAYS.map((d) => (
                  <div key={d} className="lp-mockup-cell header">{d}</div>
                ))}

                {/* time rows */}
                {TIMES.map((t, ti) => (
                  <>
                    <div key={`t-${ti}`} className="lp-mockup-cell time-col">{t}</div>
                    {DAYS.map((_, di) => {
                      const key = `${di}-${ti}`;
                      const fill = MOCK_FILLS[key];
                      return (
                        <div
                          key={key}
                          className={`lp-mockup-cell${fill ? ` filled ${fill.cls}` : ""}`}
                        >
                          {fill ? fill.label : "—"}
                        </div>
                      );
                    })}
                  </>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ────── FEATURES ────── */}
      <section className="lp-section" id="features">
        <div className="lp-section-header lp-reveal" ref={addRevealRef}>
          <div className="lp-section-label">✨ Features</div>
          <h2 className="lp-section-title">Everything You Need</h2>
          <p className="lp-section-desc">
            A comprehensive platform that handles every aspect of academic timetable management — 
            from data entry to intelligent scheduling to deployment.
          </p>
        </div>

        <div className="lp-features-grid">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="lp-feature-card lp-reveal"
              ref={addRevealRef}
              style={{ transitionDelay: `${i * 0.1}s` }}
            >
              <div className="lp-feature-icon" style={{ background: f.bg, color: f.color }}>
                {f.icon}
              </div>
              <h3 className="lp-feature-title">{f.title}</h3>
              <p className="lp-feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ────── TECH STACK ────── */}
      <section className="lp-section" id="tech">
        <div className="lp-section-header lp-reveal" ref={addRevealRef}>
          <div className="lp-section-label">🧱 Tech Stack</div>
          <h2 className="lp-section-title">Built with Modern Tech</h2>
          <p className="lp-section-desc">
            Enterprise-grade technologies powering every layer — from the reactive frontend 
            to the ML pipeline.
          </p>
        </div>

        <div className="lp-tech-grid">
          {TECH.map((t, i) => (
            <div
              key={i}
              className="lp-tech-card lp-reveal"
              ref={addRevealRef}
              style={{ transitionDelay: `${i * 0.1}s` }}
            >
              <span className="lp-tech-icon">{t.icon}</span>
              <h3 className="lp-tech-name">{t.name}</h3>
              <p className="lp-tech-detail">{t.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ────── MEET THE DEVELOPER ────── */}
      <section className="lp-dev-section" id="developer">
        <div className="lp-section-header lp-reveal" ref={addRevealRef}>
          <div className="lp-section-label">👨‍💻 Meet the Developer</div>
          <h2 className="lp-section-title">Built with Passion</h2>
        </div>

        <div className="lp-dev-card lp-reveal" ref={addRevealRef}>
          <div className="lp-dev-avatar">AK</div>
          <h3 className="lp-dev-name">Akhil</h3>
          <p className="lp-dev-role">
            BCA Student &nbsp;·&nbsp; Full-Stack Developer &nbsp;·&nbsp; AI Systems Enthusiast
          </p>
          <div className="lp-dev-links">
            <a
              href="https://github.com/Akki-06"
              target="_blank"
              rel="noopener noreferrer"
              className="lp-dev-link"
            >
              <FaGithub /> GitHub
            </a>
            <a
              href="https://www.linkedin.com/in/akhil-puri/"
              target="_blank"
              rel="noopener noreferrer"
              className="lp-dev-link"
            >
              <FaLinkedinIn /> LinkedIn
            </a>
          </div>
        </div>
      </section>

      {/* ────── FOOTER ────── */}
      <footer className="lp-footer">
        <span className="lp-footer-logo">TIMETRIX</span>
        <span className="lp-footer-copy">
          © {new Date().getFullYear()} Timetrix · Built for academic excellence.
        </span>
        <div className="lp-footer-links">
          <a href="#about">About</a>
          <a href="#features">Features</a>
          <a href="https://github.com/Akki-06/timetrix" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </footer>
    </div>
  );
}
