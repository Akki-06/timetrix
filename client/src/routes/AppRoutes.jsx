import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import ProtectedRoute from "../components/ProtectedRoute";
import LoginPage from "../pages/LoginPage";
import Dashboard from "../pages/Dashboard";
import FacultyPage from "../pages/FacultyPage";
import ProgramsPage from "../pages/ProgramsPage";
import SectionsPage from "../pages/SectionsPage";
import CoursesPage from "../pages/CoursesPage";
import InfrastructurePage from "../pages/InfrastructurePage";
import TimetableGeneratorPage from "../pages/TimetableGeneratorPage";
import GeneratedTimetablesPage from "../pages/GeneratedTimetablesPage";
import SettingsPage from "../pages/SettingsPage";

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
        />

        <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />

        <Route path="/faculty" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <FacultyPage />
          </ProtectedRoute>
        } />

        <Route path="/programs" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <ProgramsPage />
          </ProtectedRoute>
        } />

        <Route path="/sections" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <SectionsPage />
          </ProtectedRoute>
        } />

        <Route path="/courses" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <CoursesPage />
          </ProtectedRoute>
        } />

        <Route path="/infrastructure" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <InfrastructurePage />
          </ProtectedRoute>
        } />

        <Route path="/generator" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <TimetableGeneratorPage />
          </ProtectedRoute>
        } />

        <Route path="/generated" element={
          <ProtectedRoute allowedRoles={["admin", "teacher", "student"]}>
            <GeneratedTimetablesPage />
          </ProtectedRoute>
        } />

        <Route path="/settings" element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <SettingsPage />
          </ProtectedRoute>
        } />

        <Route path="*" element={<Navigate to={isAuthenticated ? "/" : "/login"} replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default AppRoutes;
