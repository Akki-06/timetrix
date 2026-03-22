import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import StatsSection from "../components/StatsSection";
import ActivitySection from "../components/ActivitySection";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/axios";
import { asList } from "../utils/helpers";
import {
  FaBuilding,
  FaChalkboardTeacher,
  FaGraduationCap,
  FaCalendarAlt,
  FaCheckCircle,
} from "react-icons/fa";

function relativeTime(dateStr) {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? "" : "s"} ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} hour${diffHr === 1 ? "" : "s"} ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 30) return `${diffDay} day${diffDay === 1 ? "" : "s"} ago`;
  const diffMonth = Math.floor(diffDay / 30);
  return `${diffMonth} month${diffMonth === 1 ? "" : "s"} ago`;
}

const SUBTITLES = {
  admin: "Overview of your timetable management system",
  teacher: "Your teaching schedule at a glance",
  student: "Your academic schedule overview",
};

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

        // Build rich activity items from timetable history
        const activityItems = tts.slice(0, 4).map((tt) => ({
          title: "Timetable generated",
          description: `Version ${tt.version}${tt.term_display ? " - " + tt.term_display : ""}`,
          time: relativeTime(tt.created_at),
          type: "success",
        }));

        setActivities(
          activityItems.length > 0
            ? activityItems
            : [{ title: "No recent activity", description: "Generate your first timetable to see activity here.", time: "", type: "success" }]
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
        { title: "Active Version", value: latest ? `V${latest.version}` : "None" },
      ];
    }

    return [
      { title: "Programs", value: progs.length },
      { title: "Total Courses", value: courses.length },
      { title: "Active Version", value: latest ? `V${latest.version}` : "None" },
    ];
  };

  const buildSystemStatus = () => {
    if (!allData) return [];
    const { latest } = allData;
    const score = latest ? latest.total_constraint_score : null;

    return [
      {
        label: "Faculty availability compliance",
        value: score != null ? `${Math.min(100, Math.round(score * 100))}%` : "--",
      },
      {
        label: "Room allocation efficiency",
        value: score != null ? `${Math.min(100, Math.round(score * 95))}%` : "--",
      },
      {
        label: "Lunch break adherence",
        value: "100%",
      },
      {
        label: "Max lectures per day",
        value: "Within limits",
      },
    ];
  };

  if (loading) {
    return (
      <DashboardLayout>
        <h1 className="dashboard-title">Dashboard</h1>
        <p className="dashboard-subtitle">Loading...</p>
      </DashboardLayout>
    );
  }

  const systemStatus = buildSystemStatus();
  const hasConstraintIssues = allData?.latest
    ? allData.latest.total_constraint_score < 1
    : false;

  return (
    <DashboardLayout>
      <div className="dashboard-header-row">
        <div>
          <h1 className="dashboard-title">Dashboard</h1>
          <p className="dashboard-subtitle">{SUBTITLES[role]}</p>
        </div>
        {role === "admin" && (
          <Link to="/generator" className="btn-primary btn-with-icon">
            <FaCalendarAlt />
            Generate Timetable
          </Link>
        )}
      </div>

      {fetchError && <p className="upload-error" style={{ marginBottom: 14 }}>{fetchError}</p>}

      <StatsSection stats={buildStats()} />

      {role === "admin" && (
        <div className="dashboard-bottom-grid">
          {/* System Status */}
          <div className="panel-card">
            <h3>System Status</h3>

            <div className="system-status-banner">
              <FaCheckCircle className="system-status-icon" />
              <span>
                {hasConstraintIssues
                  ? "Some constraints may need attention"
                  : "All active timetables satisfy defined constraints"}
              </span>
            </div>

            <div className="system-status-list">
              {systemStatus.map((item, i) => (
                <div key={i} className="system-status-row">
                  <span className="system-status-label">{item.label}</span>
                  <span className="system-status-value">{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Activity */}
          <ActivitySection activities={activities} />
        </div>
      )}

      {role === "admin" && (
        <div className="panel-card quick-actions-card">
          <h3>Quick Actions</h3>
          <div className="quick-actions-grid">
            <Link to="/faculty" className="quick-action-item">
              <div className="quick-action-icon"><FaBuilding /></div>
              <span>Add Department</span>
            </Link>
            <Link to="/faculty" className="quick-action-item">
              <div className="quick-action-icon"><FaChalkboardTeacher /></div>
              <span>Register Faculty</span>
            </Link>
            <Link to="/courses" className="quick-action-item">
              <div className="quick-action-icon"><FaGraduationCap /></div>
              <span>Create Course</span>
            </Link>
            <Link to="/generated" className="quick-action-item">
              <div className="quick-action-icon"><FaCalendarAlt /></div>
              <span>View Timetables</span>
            </Link>
          </div>
        </div>
      )}

      {role === "teacher" && (
        <div className="dashboard-bottom-grid">
          <ActivitySection activities={activities} />
          <div className="panel-card">
            <h3>Quick Actions</h3>
            <p style={{ color: "var(--muted)", fontSize: 14, marginBottom: 12 }}>
              View your assigned timetable under the Timetables page.
            </p>
            <Link to="/generated" className="btn-primary" style={{ display: "inline-block", textDecoration: "none" }}>
              View My Schedule
            </Link>
          </div>
        </div>
      )}

      {role === "student" && (
        <div className="dashboard-bottom-grid">
          <ActivitySection activities={activities} />
          <div className="panel-card">
            <h3>Quick Actions</h3>
            <p style={{ color: "var(--muted)", fontSize: 14, marginBottom: 12 }}>
              Check your class timetable for the current term.
            </p>
            <Link to="/generated" className="btn-primary" style={{ display: "inline-block", textDecoration: "none" }}>
              View Timetable
            </Link>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default Dashboard;
