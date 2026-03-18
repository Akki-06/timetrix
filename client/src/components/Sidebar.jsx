import { NavLink } from "react-router-dom";
import {
  FaBuilding,
  FaChalkboardTeacher,
  FaChartPie,
  FaCog,
  FaFileAlt,
  FaGraduationCap,
  FaMagic,
} from "react-icons/fa";

const menuItems = [
  { label: "Dashboard", to: "/", icon: FaChartPie },
  { label: "Faculty", to: "/faculty", icon: FaChalkboardTeacher },
  { label: "Courses", to: "/courses", icon: FaGraduationCap },
  { label: "Infrastructure", to: "/infrastructure", icon: FaBuilding },
  { label: "Timetable Generator", to: "/generator", icon: FaMagic },
  { label: "Generated", to: "/generated", icon: FaFileAlt },
  { label: "Settings", to: "/settings", icon: FaCog },
];

function Sidebar({ collapsed }) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <div className="sidebar-brand">
        <h3 className="sidebar-title">Academic Timetable</h3>
        {!collapsed && <p>Management System</p>}
      </div>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <div key={item.label} className="sidebar-group">
            <NavLink
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `sidebar-item ${isActive ? "active" : ""}`
              }
              title={item.label}
            >
              <span className="sidebar-item-icon"><item.icon /></span>
              {!collapsed && <span className="sidebar-item-text">{item.label}</span>}
            </NavLink>
          </div>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
