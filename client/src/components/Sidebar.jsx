const menuItems = [
  { label: "Dashboard", shortLabel: "D", active: true },
  { label: "Timetables", shortLabel: "T" },
  { label: "Faculty", shortLabel: "F" },
  { label: "Rooms", shortLabel: "R" },
];

function Sidebar({ collapsed }) {
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <h3 className="sidebar-title">{collapsed ? "M" : "Menu"}</h3>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <a
            key={item.label}
            href="/"
            className={`sidebar-item ${item.active ? "active" : ""}`}
            title={collapsed ? item.label : ""}
          >
            <span className="sidebar-item-icon">{item.shortLabel}</span>
            {!collapsed && (
              <span className="sidebar-item-text">{item.label}</span>
            )}
          </a>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
