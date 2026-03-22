import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useTheme } from "../contexts/ThemeContext";
import { FaSun, FaMoon, FaUserShield, FaChalkboardTeacher, FaUserGraduate } from "react-icons/fa";

const ROLE_CARDS = [
  { key: "admin", label: "Admin", icon: FaUserShield, user: "admin", pass: "admin123", color: "#6366f1" },
  { key: "teacher", label: "Teacher", icon: FaChalkboardTeacher, user: "teacher", pass: "teacher123", color: "#14b8a6" },
  { key: "student", label: "Student", icon: FaUserGraduate, user: "student", pass: "student123", color: "#f59e0b" },
];

function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    setTimeout(() => {
      const result = login(username, password);
      if (result.success) {
        navigate("/");
      } else {
        setError(result.error);
      }
      setLoading(false);
    }, 400);
  };

  const fillCredentials = (user, pass) => {
    setUsername(user);
    setPassword(pass);
    setError("");
  };

  return (
    <div className="login-page">
      <button className="theme-toggle-float" onClick={toggleTheme} title="Toggle theme">
        {theme === "light" ? <FaMoon /> : <FaSun />}
      </button>

      <div className="login-card">
        <div className="login-header">
          <div className="login-logo-icon">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <rect width="48" height="48" rx="12" fill="url(#lg)" />
              <path d="M14 16h20v2H14zM14 22h20v2H14zM14 28h14v2H14zM32 26l6 6-6 6" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
              <defs><linearGradient id="lg" x1="0" y1="0" x2="48" y2="48"><stop stopColor="#6366f1"/><stop offset="1" stopColor="#14b8a6"/></linearGradient></defs>
            </svg>
          </div>
          <h1>TIMETRIX</h1>
          <p>Smart Timetable Management System</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="login-error">{error}</div>}

          <div className="login-field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
              autoComplete="username"
            />
          </div>

          <div className="login-field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" className="login-btn" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="demo-section">
          <p className="demo-title">Quick Login</p>
          <div className="demo-grid">
            {ROLE_CARDS.map((r) => (
              <button
                key={r.key}
                type="button"
                className="demo-card"
                onClick={() => fillCredentials(r.user, r.pass)}
                style={{ "--accent": r.color }}
              >
                <r.icon className="demo-card-icon" />
                <span className="demo-card-label">{r.label}</span>
                <span className="demo-card-creds">{r.user} / {r.pass}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default LoginPage;
