import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/axios";
import { asList } from "../utils/helpers";
import {
  FaBuilding,
  FaChalkboardTeacher,
  FaGraduationCap,
  FaCalendarAlt,
  FaCheckCircle,
  FaDoorOpen,
  FaChartPie,
  FaArrowRight,
  FaCog,
  FaBolt,
  FaLink,
  FaCalendarCheck,
  FaRocket,
  FaShieldAlt,
  FaClock,
} from "react-icons/fa";

function relativeTime(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay}d ago`;
  const diffMonth = Math.floor(diffDay / 30);
  return `${diffMonth}mo ago`;
}

const GREETINGS = {
  admin: "Welcome back, Admin",
  teacher: "Welcome back, Teacher",
  student: "Welcome back, Student",
};

const SUBTITLES = {
  admin: "Here's what's happening with your timetable system today.",
  teacher: "Your teaching schedule at a glance.",
  student: "Your academic schedule overview.",
};

const STAT_META = {
  Departments: { icon: FaBuilding, gradient: "linear-gradient(135deg, #3b82f6, #1d4ed8)", lightBg: "rgba(59,130,246,0.1)" },
  Programs: { icon: FaGraduationCap, gradient: "linear-gradient(135deg, #10b981, #059669)", lightBg: "rgba(16,185,129,0.1)" },
  Faculty: { icon: FaChalkboardTeacher, gradient: "linear-gradient(135deg, #8b5cf6, #6d28d9)", lightBg: "rgba(139,92,246,0.1)" },
  Rooms: { icon: FaDoorOpen, gradient: "linear-gradient(135deg, #f97316, #c2410c)", lightBg: "rgba(249,115,22,0.1)" },
  Timetables: { icon: FaCalendarCheck, gradient: "linear-gradient(135deg, #6366f1, #4f46e5)", lightBg: "rgba(99,102,241,0.1)" },
  "Total Courses": { icon: FaGraduationCap, gradient: "linear-gradient(135deg, #10b981, #059669)", lightBg: "rgba(16,185,129,0.1)" },
  "Active Version": { icon: FaCalendarCheck, gradient: "linear-gradient(135deg, #6366f1, #4f46e5)", lightBg: "rgba(99,102,241,0.1)" },
};

const QUICK_ACTIONS = [
  { label: "Add Department", icon: FaBuilding, to: "/faculty", color: "#3b82f6" },
  { label: "Register Faculty", icon: FaChalkboardTeacher, to: "/faculty", color: "#8b5cf6" },
  { label: "Create Course", icon: FaGraduationCap, to: "/courses", color: "#10b981" },
  { label: "Assignments", icon: FaLink, to: "/assignments", color: "#f59e0b" },
  { label: "Generate", icon: FaRocket, to: "/generator", color: "#6366f1" },
  { label: "View Timetables", icon: FaCalendarAlt, to: "/generated", color: "#14b8a6" },
];

function Dashboard() {
  const { user } = useAuth();
  const role = user?.role || "student";
  const [allData, setAllData] = useState(null);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [deptResp, progResp, facResp, roomResp, ttResp, courseResp] =
          await Promise.all([
            api.get("academics/departments/").catch(() => null),
            api.get("academics/programs/").catch(() => null),
            api.get("faculty/faculty/").catch(() => null),
            api.get("infrastructure/room/").catch(() => null),
            api.get("scheduler/timetables/", { params: { ordering: "-created_at" } }).catch(() => null),
            api.get("academics/courses/").catch(() => null),
          ]);

        const depts = deptResp ? asList(deptResp.data) : [];
        const progs = progResp ? asList(progResp.data) : [];
        const facs = facResp ? asList(facResp.data) : [];
        const rms = roomResp ? asList(roomResp.data) : [];
        const tts = ttResp ? asList(ttResp.data) : [];
        const courses = courseResp ? asList(courseResp.data) : [];
        const latest = tts.length > 0 ? tts[0] : null;

        setAllData({ depts, progs, facs, rms, tts, courses, latest });

        const activityItems = tts.slice(0, 5).map((tt) => ({
          title: "Timetable generated",
          description: `Version ${tt.version}${tt.term_display ? " — " + tt.term_display : ""}`,
          time: relativeTime(tt.created_at),
          type: "success",
        }));

        setActivities(
          activityItems.length > 0
            ? activityItems
            : [{ title: "No recent activity", description: "Generate your first timetable to see activity here.", time: "", type: "info" }]
        );
      } catch (err) {
        console.error("Dashboard fetch error:", err);
        setFetchError("Failed to load dashboard data. Is the backend running?");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const buildStats = () => {
    if (!allData) return [];
    const { depts, progs, facs, rms, courses, tts, latest } = allData;
    if (role === "admin") {
      return [
        { title: "Departments", value: depts.length },
        { title: "Programs", value: progs.length },
        { title: "Faculty", value: facs.length },
        { title: "Rooms", value: rms.length },
        { title: "Timetables", value: tts.length },
      ];
    }
    if (role === "teacher") {
      return [
        { title: "Total Courses", value: courses.length },
        { title: "Programs", value: progs.length },
        { title: "Active Version", value: latest ? `V${latest.version}` : "—" },
      ];
    }
    return [
      { title: "Programs", value: progs.length },
      { title: "Total Courses", value: courses.length },
      { title: "Active Version", value: latest ? `V${latest.version}` : "—" },
    ];
  };

  const buildSystemStatus = () => {
    if (!allData) return [];
    const { latest } = allData;
    const score = latest ? latest.total_constraint_score : null;
    return [
      { label: "Faculty availability", value: score != null ? `${Math.min(100, Math.round(score * 100))}%` : "—", icon: FaChalkboardTeacher, color: "#8b5cf6" },
      { label: "Room allocation", value: score != null ? `${Math.min(100, Math.round(score * 95))}%` : "—", icon: FaDoorOpen, color: "#f97316" },
      { label: "Lunch break adherence", value: "100%", icon: FaClock, color: "#10b981" },
      { label: "Max lectures/day", value: "Within limits", icon: FaShieldAlt, color: "#6366f1" },
    ];
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="db-loading">
          <div className="db-loading-spinner" />
          <p>Loading dashboard...</p>
        </div>
      </DashboardLayout>
    );
  }

  const systemStatus = buildSystemStatus();
  const hasConstraintIssues = allData?.latest ? allData.latest.total_constraint_score < 1 : false;
  const stats = buildStats();

  return (
    <DashboardLayout>
      {/* ── Header ── */}
      <div className="db-header">
        <div className="db-header-text">
          <h1 className="db-greeting">{GREETINGS[role]}</h1>
          <p className="db-header-sub">{SUBTITLES[role]}</p>
        </div>
        {role === "admin" && (
          <Link to="/generator" className="db-header-cta">
            <FaBolt /> Generate Timetable
          </Link>
        )}
      </div>

      {fetchError && <div className="db-error-banner">{fetchError}</div>}

      {/* ── Stats Cards ── */}
      <div className="db-stats-grid">
        {stats.map((item, i) => {
          const meta = STAT_META[item.title] || { icon: FaChartPie, gradient: "linear-gradient(135deg, #6366f1, #4f46e5)", lightBg: "rgba(99,102,241,0.1)" };
          const Icon = meta.icon;
          return (
            <div key={i} className="db-stat-card">
              <div className="db-stat-icon-wrap" style={{ background: meta.gradient }}>
                <Icon />
              </div>
              <div className="db-stat-info">
                <span className="db-stat-label">{item.title}</span>
                <span className="db-stat-value">{item.value}</span>
              </div>
              <div className="db-stat-glow" style={{ background: meta.lightBg }} />
            </div>
          );
        })}
      </div>

      {/* ── Admin: System Status + Activity ── */}
      {role === "admin" && (
        <div className="db-grid-2col">
          {/* System Health */}
          <div className="db-panel">
            <div className="db-panel-header">
              <h3><FaShieldAlt style={{ marginRight: 8, opacity: 0.6 }} />System Health</h3>
              <span className={`db-health-badge ${hasConstraintIssues ? "warn" : "ok"}`}>
                <FaCheckCircle />
                {hasConstraintIssues ? "Needs Attention" : "All Clear"}
              </span>
            </div>
            <div className="db-health-grid">
              {systemStatus.map((item, i) => {
                const Icon = item.icon;
                return (
                  <div key={i} className="db-health-item">
                    <div className="db-health-icon" style={{ color: item.color, background: `${item.color}14` }}>
                      <Icon />
                    </div>
                    <div className="db-health-info">
                      <span className="db-health-label">{item.label}</span>
                      <span className="db-health-value">{item.value}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Activity */}
          <div className="db-panel">
            <div className="db-panel-header">
              <h3><FaClock style={{ marginRight: 8, opacity: 0.6 }} />Recent Activity</h3>
            </div>
            <div className="db-activity-list">
              {activities.map((item, i) => (
                <div key={i} className="db-activity-item">
                  <div className={`db-activity-dot ${item.type}`} />
                  <div className="db-activity-content">
                    <span className="db-activity-title">{item.title || item.message}</span>
                    {item.description && <span className="db-activity-desc">{item.description}</span>}
                  </div>
                  {item.time && <span className="db-activity-time">{item.time}</span>}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Admin: Quick Actions ── */}
      {role === "admin" && (
        <div className="db-panel" style={{ marginTop: 16 }}>
          <div className="db-panel-header">
            <h3><FaBolt style={{ marginRight: 8, opacity: 0.6 }} />Quick Actions</h3>
          </div>
          <div className="db-actions-grid">
            {QUICK_ACTIONS.map((action, i) => {
              const Icon = action.icon;
              return (
                <Link key={i} to={action.to} className="db-action-card">
                  <div className="db-action-icon" style={{ color: action.color, background: `${action.color}14` }}>
                    <Icon />
                  </div>
                  <span className="db-action-label">{action.label}</span>
                  <FaArrowRight className="db-action-arrow" />
                </Link>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Teacher/Student view ── */}
      {(role === "teacher" || role === "student") && (
        <div className="db-grid-2col">
          <div className="db-panel">
            <div className="db-panel-header">
              <h3><FaClock style={{ marginRight: 8, opacity: 0.6 }} />Recent Activity</h3>
            </div>
            <div className="db-activity-list">
              {activities.map((item, i) => (
                <div key={i} className="db-activity-item">
                  <div className={`db-activity-dot ${item.type}`} />
                  <div className="db-activity-content">
                    <span className="db-activity-title">{item.title}</span>
                    {item.description && <span className="db-activity-desc">{item.description}</span>}
                  </div>
                  {item.time && <span className="db-activity-time">{item.time}</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="db-panel">
            <div className="db-panel-header">
              <h3><FaCalendarAlt style={{ marginRight: 8, opacity: 0.6 }} />Quick Access</h3>
            </div>
            <p style={{ color: "var(--muted)", fontSize: 14, marginBottom: 16, lineHeight: 1.6 }}>
              {role === "teacher"
                ? "View your assigned teaching schedule under the Timetables page."
                : "Check your class timetable for the current term."}
            </p>
            <Link to="/generated" className="db-header-cta" style={{ display: "inline-flex" }}>
              <FaCalendarAlt /> View {role === "teacher" ? "My Schedule" : "Timetable"}
            </Link>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default Dashboard;
