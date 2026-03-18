import { BrowserRouter, Routes, Route } from "react-router-dom";
import Dashboard from "../pages/Dashboard";
import FacultyPage from "../pages/FacultyPage";
import CoursesPage from "../pages/CoursesPage";
import InfrastructurePage from "../pages/InfrastructurePage";
import TimetableGeneratorPage from "../pages/TimetableGeneratorPage";
import GeneratedTimetablesPage from "../pages/GeneratedTimetablesPage";
import SettingsPage from "../pages/SettingsPage";

function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/faculty" element={<FacultyPage />} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/infrastructure" element={<InfrastructurePage />} />
        <Route path="/generator" element={<TimetableGeneratorPage />} />
        <Route path="/generated" element={<GeneratedTimetablesPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;