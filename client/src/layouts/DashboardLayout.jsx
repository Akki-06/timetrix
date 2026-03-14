import { useState } from "react";
import Sidebar from "../components/Sidebar";
import TopNavbar from "../components/TopNavbar";

function DashboardLayout({ children }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed((prev) => !prev);
  };

  return (
    <div className="dashboard-layout">
      <TopNavbar
        selectedTerm="Spring 2024"
        selectedVersion="Version 1"
        onToggleSidebar={handleToggleSidebar}
      />

      <div className="dashboard-body">
        <Sidebar collapsed={isSidebarCollapsed} />
        <div className="dashboard-content">
          {children}
        </div>
      </div>
    </div>
  );
}

export default DashboardLayout;
