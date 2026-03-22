import { useEffect, useRef, useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { FaBars, FaSun, FaMoon, FaSignOutAlt, FaBell } from "react-icons/fa";
import api from "../api/axios";
import { asList } from "../utils/helpers";

const ROLE_LABELS = {
  admin: "Administrator",
  teacher: "Faculty",
  student: "Student",
};

const TYPE_COLORS = {
  success: "var(--brand)",
  warning: "#f59e0b",
  error:   "#ef4444",
  info:    "var(--muted)",
};

function NotificationBell() {
  const [open, setOpen]         = useState(false);
  const [notes, setNotes]       = useState([]);
  const [unread, setUnread]     = useState(0);
  const dropRef                 = useRef(null);

  const load = async () => {
    try {
      const resp = await api.get("scheduler/notifications/");
      const all  = asList(resp.data);
      setNotes(all.slice(0, 20));
      setUnread(all.filter((n) => !n.is_read).length);
    } catch {
      // backend not running — silently ignore
    }
  };

  // Poll every 30 seconds for new notifications (pause when tab is hidden)
  useEffect(() => {
    load();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") load();
    }, 30000);
    return () => clearInterval(id);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (dropRef.current && !dropRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const markAllRead = async () => {
    try {
      await api.patch("scheduler/notifications/mark-all-read/");
      setUnread(0);
      setNotes((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch { /* ignore */ }
  };

  const markOne = async (id) => {
    try {
      await api.patch(`scheduler/notifications/${id}/`, { is_read: true });
      setNotes((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
      setUnread((c) => Math.max(0, c - 1));
    } catch { /* ignore */ }
  };

  return (
    <div ref={dropRef} style={{ position: "relative" }}>
      <button
        type="button"
        className="theme-btn"
        onClick={() => { setOpen((o) => !o); if (!open) load(); }}
        title="Notifications"
        style={{ position: "relative" }}
      >
        <FaBell />
        {unread > 0 && (
          <span style={{
            position: "absolute", top: 2, right: 2,
            background: "#ef4444", color: "#fff",
            borderRadius: "50%", fontSize: 9, fontWeight: 700,
            minWidth: 14, height: 14, lineHeight: "14px",
            textAlign: "center", padding: "0 2px",
          }}>
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 8px)", right: 0,
          width: 340, maxHeight: 420, overflowY: "auto",
          background: "var(--card-bg)", border: "1px solid var(--border)",
          borderRadius: 10, boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
          zIndex: 999,
        }}>
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "12px 16px", borderBottom: "1px solid var(--border)",
          }}>
            <strong style={{ fontSize: "0.9rem" }}>Notifications</strong>
            {unread > 0 && (
              <button
                type="button"
                onClick={markAllRead}
                style={{
                  fontSize: "0.75rem", color: "var(--brand)",
                  background: "none", border: "none", cursor: "pointer",
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {notes.length === 0 ? (
            <p style={{ padding: 16, textAlign: "center", color: "var(--muted)", fontSize: "0.85rem" }}>
              No notifications yet
            </p>
          ) : (
            notes.map((n) => (
              <div
                key={n.id}
                onClick={() => markOne(n.id)}
                style={{
                  padding: "10px 16px",
                  borderBottom: "1px solid var(--border)",
                  cursor: "pointer",
                  background: n.is_read ? "transparent" : "var(--brand-alpha, rgba(99,102,241,0.06))",
                  display: "flex", gap: 10, alignItems: "flex-start",
                }}
              >
                <span style={{
                  width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
                  background: TYPE_COLORS[n.type] || "var(--muted)",
                  marginTop: 5,
                }} />
                <div>
                  <p style={{ fontSize: "0.82rem", margin: 0, color: "var(--text)" }}>
                    {n.message}
                  </p>
                  <p style={{ fontSize: "0.72rem", margin: "2px 0 0", color: "var(--muted)" }}>
                    {new Date(n.created_at).toLocaleString("en-IN", {
                      day: "2-digit", month: "short",
                      hour: "2-digit", minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function TopNavbar({ onToggleSidebar }) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="top-navbar">
      <div className="top-navbar-left">
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          <FaBars />
        </button>

        <div>
          <h2 className="top-navbar-title">TIMETRIX</h2>
          <p className="top-navbar-subtitle">Smart Timetable Management</p>
        </div>
      </div>

      <div className="top-navbar-controls">
        <button
          type="button"
          className="theme-btn"
          onClick={toggleTheme}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
        >
          {theme === "light" ? <FaMoon /> : <FaSun />}
        </button>

        {/* Notification bell — only visible to admins */}
        {user?.role === "admin" && <NotificationBell />}

        <div className="top-user">
          <div className="top-user-meta">
            <div className="top-user-name">{user?.name || "User"}</div>
            <div className="top-user-role">
              <span className={`role-badge role-${user?.role || "student"}`}>
                {ROLE_LABELS[user?.role] || "User"}
              </span>
            </div>
          </div>
          <div className={`top-user-avatar avatar-${user?.role || "student"}`}>
            {user?.name?.[0] || "U"}
          </div>
        </div>

        <button type="button" className="logout-btn" onClick={logout} title="Logout">
          <FaSignOutAlt />
        </button>
      </div>
    </header>
  );
}

export default TopNavbar;
