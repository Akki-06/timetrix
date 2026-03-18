function TopNavbar({ onToggleSidebar }) {
  return (
    <header className="top-navbar">
      <div className="top-navbar-left">
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          ☰
        </button>

        <div>
          <h2 className="top-navbar-title">TIMETRIX</h2>
          <p className="top-navbar-subtitle">Smart Timetable Management</p>
        </div>
      </div>

      <div className="top-navbar-controls">
        <select className="top-select" defaultValue="Spring 2025">
          <option>Spring 2025</option>
          <option>Spring 2026</option>
        </select>

        <select className="top-select" defaultValue="Version 1">
          <option>Version 1</option>
          <option>Version 2</option>
        </select>

        <button type="button" className="top-icon" title="Notifications">
          🔔
        </button>

        <div className="top-user">
          <div className="top-user-meta">
            <div className="top-user-name">Admin User</div>
            <div className="top-user-role">System Administrator</div>
          </div>
          <div className="top-user-avatar">A</div>
        </div>
      </div>
    </header>
  );
}

export default TopNavbar;
