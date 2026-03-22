import {
  FaBuilding,
  FaGraduationCap,
  FaChalkboardTeacher,
  FaDoorOpen,
  FaCalendarCheck,
  FaChartPie,
} from "react-icons/fa";

const ICON_MAP = {
  Departments: { icon: FaBuilding, color: "#3b82f6" },
  Programs: { icon: FaGraduationCap, color: "#10b981" },
  Faculty: { icon: FaChalkboardTeacher, color: "#8b5cf6" },
  Rooms: { icon: FaDoorOpen, color: "#f97316" },
  "Active Version": { icon: FaCalendarCheck, color: "#6366f1" },
  "Constraint Score": { icon: FaChartPie, color: "#14b8a6" },
  "Total Courses": { icon: FaGraduationCap, color: "#10b981" },
  "Timetables": { icon: FaCalendarCheck, color: "#6366f1" },
};

function StatsSection({ stats }) {
  return (
    <div className="stats-grid">
      {stats.map((item, index) => {
        const mapped = ICON_MAP[item.title] || { icon: FaChartPie, color: "#6366f1" };
        const Icon = mapped.icon;
        return (
          <div key={index} className="stats-card">
            <div className="stats-card-content">
              <p>{item.title}</p>
              <h2>{item.value}</h2>
              {item.subtitle && <small>{item.subtitle}</small>}
            </div>
            <div
              className="stats-card-icon"
              style={{ color: mapped.color, background: `${mapped.color}14` }}
            >
              <Icon />
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default StatsSection;
