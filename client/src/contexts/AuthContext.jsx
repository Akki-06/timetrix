import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

const DEMO_USERS = {
  admin: { password: "admin123", role: "admin", name: "Admin User" },
  teacher: { password: "teacher123", role: "teacher", name: "Dr. Smith" },
  student: { password: "student123", role: "student", name: "John Doe" },
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem("timetrix_user");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const login = (username, password) => {
    const demoUser = DEMO_USERS[username.toLowerCase().trim()];
    if (!demoUser || demoUser.password !== password) {
      return { success: false, error: "Invalid username or password" };
    }
    const userData = {
      username: username.toLowerCase().trim(),
      role: demoUser.role,
      name: demoUser.name,
    };
    setUser(userData);
    localStorage.setItem("timetrix_user", JSON.stringify(userData));
    return { success: true };
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem("timetrix_user");
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
