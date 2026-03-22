import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { FaBars, FaSun, FaMoon, FaSignOutAlt } from "react-icons/fa";

const ROLE_LABELS = {
  admin: "Administrator",
  teacher: "Faculty",
  student: "Student",
};

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
