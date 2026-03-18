import DashboardLayout from "../layouts/DashboardLayout";
import StatsSection from "../components/StatsSection";
import ActivitySection from "../components/ActivitySection";
import TermStatusSection from "../components/TermStatucSection";

function Dashboard() {

  // 🔥 Temporary Mock Data (Later replace with API)
  const stats = [
    { title: "Total Departments", value: 12 },
    { title: "Total Programs", value: 45 },
    { title: "Total Faculty", value: 186 },
    { title: "Total Rooms", value: 92 },
    { title: "Active Version", value: "V3", subtitle: "Spring 2025" },
    { title: "Constraint Score", value: "87%" },
  ];

  const activities = [
    { message: "Timetable Version 3 generated", time: "2 hours ago" },
    { message: "Faculty availability updated", time: "4 hours ago" },
    { message: "Room conflict detected", time: "1 day ago" },
    { message: "New course added", time: "2 days ago" },
  ];

  const term = {
    name: "Spring 2025",
    status: "Active",
    courses: 124,
    groups: 38,
    offerings: 215,
    progress: 73,
  };

  return (
    <DashboardLayout>
      <h1 className="dashboard-title">Dashboard</h1>
      <p className="dashboard-subtitle">
        Overview of your timetable management system
      </p>

      <StatsSection stats={stats} />

      <div className="dashboard-bottom-grid">
        <div>
          <ActivitySection activities={activities} />
        </div>
        <div>
          <TermStatusSection term={term} />
        </div>
      </div>
    </DashboardLayout>
  );
}

export default Dashboard;
