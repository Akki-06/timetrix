import logo from "../assets/logo/timetrix-logo.png";

function TopNavbar({ selectedTerm, selectedVersion, onToggleSidebar }) {
  return (
    <header className="top-navbar">
      <div className="top-navbar-left">
        <button
          type="button"
          className="sidebar-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
        >
          Menu
        </button>
        <img src={logo} alt="TIMETRIX Logo" className="top-navbar-logo" />
      </div>

      <div className="top-navbar-controls">
        <select className="top-select" defaultValue={selectedTerm}>
          <option>Spring 2024</option>
          <option>Spring 2025</option>
        </select>

        <select className="top-select" defaultValue={selectedVersion}>
          <option>Version 1</option>
          <option>Version 2</option>
        </select>

        <span className="top-icon" title="Theme">
          {"\u263D"}
        </span>
        <span className="top-icon" title="Notifications">
          {"\u23F0"}
        </span>
        <span className="top-icon" title="Profile">
          {"\u263A"}
        </span>
      </div>
    </header>
  );
}

export default TopNavbar;
