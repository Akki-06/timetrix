import { NavLink } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import {
  FaBuilding,
  FaChalkboardTeacher,
  FaChartPie,
  FaCog,
  FaCalendarAlt,
  FaGraduationCap,
  FaLink,
  FaMagic,
  FaUniversity,
  FaUsers,
} from "react-icons/fa";

const MENU_ITEMS = [
  { label: "Dashboard", to: "/dashboard", icon: FaChartPie, roles: ["admin", "teacher", "student"] },
  { label: "Faculty", to: "/faculty", icon: FaChalkboardTeacher, roles: ["admin"] },
  { label: "Programs", to: "/programs", icon: FaUniversity, roles: ["admin"] },
  { label: "Sections", to: "/sections", icon: FaUsers, roles: ["admin"] },
  { label: "Courses", to: "/courses", icon: FaGraduationCap, roles: ["admin"] },
  { label: "Assignments", to: "/assignments", icon: FaLink, roles: ["admin"] },
  { label: "Infrastructure", to: "/infrastructure", icon: FaBuilding, roles: ["admin"] },
  { label: "Generator", to: "/generator", icon: FaMagic, roles: ["admin"] },
  { label: "Timetables", to: "/generated", icon: FaCalendarAlt, roles: ["admin", "teacher", "student"] },
  { label: "Settings", to: "/settings", icon: FaCog, roles: ["admin"] },
];

function Sidebar({ collapsed, mobileOpen, onMobileClose }) {
  const { user } = useAuth();
  const role = user?.role || "student";
  const visibleItems = MENU_ITEMS.filter((item) => item.roles.includes(role));

  const cls = [
    "sidebar",
    collapsed ? "collapsed" : "",
    mobileOpen ? "mobile-open" : "",
  ].filter(Boolean).join(" ");

  return (
    <aside className={cls}>
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <svg width="32" height="32" viewBox="0 0 48 48" fill="none">
            <rect width="48" height="48" rx="12" fill="url(#slg)" />
            <path d="M14 16h20v2H14zM14 22h20v2H14zM14 28h14v2H14zM32 26l6 6-6 6" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            <defs><linearGradient id="slg" x1="0" y1="0" x2="48" y2="48"><stop stopColor="#6366f1" /><stop offset="1" stopColor="#14b8a6" /></linearGradient></defs>
          </svg>
        </div>
        {!collapsed && (
          <div className="sidebar-brand-text">
            <h3 className="sidebar-title">Timetrix</h3>
            <p>Management System</p>
          </div>
        )}
      </div>

      <nav className="sidebar-nav">
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/dashboard"}
            className={({ isActive }) =>
              `sidebar-item ${isActive ? "active" : ""}`
            }
            title={item.label}
            onClick={onMobileClose}
          >
            <span className="sidebar-item-icon"><item.icon /></span>
            {!collapsed && <span className="sidebar-item-text">{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
