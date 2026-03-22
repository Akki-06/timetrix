import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import TopNavbar from "../components/TopNavbar";

function DashboardLayout({ children }) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleToggleSidebar = () => {
    // On mobile (≤768px) toggle the overlay drawer; on desktop toggle collapse
    if (window.innerWidth <= 768) {
      setMobileOpen((prev) => !prev);
    } else {
      setIsSidebarCollapsed((prev) => !prev);
    }
  };

  // Close mobile sidebar on route change (content click) and on resize to desktop
  useEffect(() => {
    const onResize = () => { if (window.innerWidth > 768) setMobileOpen(false); };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  return (
    <div className="dashboard-layout">
      <TopNavbar onToggleSidebar={handleToggleSidebar} />

      {/* Mobile backdrop */}
      {mobileOpen && (
        <div className="sidebar-backdrop" onClick={() => setMobileOpen(false)} />
      )}

      <div className="dashboard-body">
        <Sidebar
          collapsed={isSidebarCollapsed}
          mobileOpen={mobileOpen}
          onMobileClose={() => setMobileOpen(false)}
        />
        <div className="dashboard-content" onClick={() => mobileOpen && setMobileOpen(false)}>
          {children}
        </div>
      </div>
    </div>
  );
}

export default DashboardLayout;
