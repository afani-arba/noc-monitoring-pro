import { createContext, useContext, useState, useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Toaster } from "sonner";
import api from "@/lib/api";
import { ThemeProvider } from "@/context/ThemeContext";

// ── Auth Context ──────────────────────────────────────────────────────────────
const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

// ── Edition Context ───────────────────────────────────────────────────────────
const EditionContext = createContext({
  edition: "monitoring_pro",
  edition_name: "NOC-Monitoring-Pro",
  features: {
    monitoring: true,
    genieacs: false,
    billing: false,
    customers: false,
    finance_report: false,
    auto_isolir: false,
    n8n: false,
  },
});
export const useEdition = () => useContext(EditionContext);

// ── Lazy Page Imports ─────────────────────────────────────────────────────────
const LoginPage         = lazy(() => import("@/pages/LoginPage"));
const DashboardPage     = lazy(() => import("@/pages/DashboardPage"));
const DevicesPage       = lazy(() => import("@/pages/DevicesPage"));
const SLAPage           = lazy(() => import("@/pages/SLAPage"));
const IncidentsPage     = lazy(() => import("@/pages/IncidentsPage"));
const ReportsPage       = lazy(() => import("@/pages/ReportsPage"));
const BackupsPage       = lazy(() => import("@/pages/BackupsPage"));
const SchedulerPage     = lazy(() => import("@/pages/SchedulerPage"));
const NotificationsPage = lazy(() => import("@/pages/NotificationsPage"));
const SettingsPage      = lazy(() => import("@/pages/SettingsPage"));
const AdminPage         = lazy(() => import("@/pages/AdminPage"));
const LicensePage       = lazy(() => import("@/pages/LicensePage"));
const UpdatePage        = lazy(() => import("@/pages/UpdatePage"));
const WallDisplayPage   = lazy(() => import("@/pages/WallDisplayPage"));
const TopologyPage      = lazy(() => import("@/pages/TopologyPage"));
const PingToolPage      = lazy(() => import("@/pages/PingToolPage"));
const SyslogPage        = lazy(() => import("@/pages/SyslogPage"));
const AuditLogPage      = lazy(() => import("@/pages/AuditLogPage"));

// ── Loading Fallback ──────────────────────────────────────────────────────────
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background text-muted-foreground text-sm">
      Memuat...
    </div>
  );
}

// ── Protected Route ───────────────────────────────────────────────────────────
function ProtectedRoute() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <Outlet />;
}

// ── Layout with Sidebar ───────────────────────────────────────────────────────
function AdminLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-56 border-r border-border bg-card flex flex-col shrink-0">
        <div className="h-14 flex items-center px-4 border-b border-border">
          <span className="font-bold text-sm text-primary">📡 NOC Monitoring</span>
        </div>
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto text-xs">
          {[
            { to: "/admin", label: "Dashboard", icon: "🖥️" },
            { to: "/admin/devices", label: "Perangkat", icon: "🔌" },
            { to: "/admin/sla", label: "SLA Monitor", icon: "📊" },
            { to: "/admin/incidents", label: "Insiden", icon: "🚨" },
            { to: "/admin/reports", label: "Laporan", icon: "📈" },
            { to: "/admin/topology", label: "Topologi", icon: "🗺️" },
            { to: "/admin/ping", label: "Ping Tool", icon: "📡" },
            { to: "/admin/syslog", label: "Syslog", icon: "📋" },
            { to: "/admin/backups", label: "Backup", icon: "💾" },
            { to: "/admin/scheduler", label: "Scheduler", icon: "⏰" },
            { to: "/admin/notifications", label: "Notifikasi", icon: "🔔" },
            { to: "/admin/audit", label: "Audit Log", icon: "🔍" },
            { to: "/admin/settings", label: "Pengaturan", icon: "⚙️" },
            { to: "/admin/users", label: "User Management", icon: "👥" },
            { to: "/admin/license", label: "Lisensi", icon: "🔑" },
            { to: "/admin/update", label: "Update Aplikasi", icon: "🔄" },
          ].map(({ to, label, icon }) => (
            <a
              key={to}
              href={to}
              className="flex items-center gap-2 px-3 py-2 rounded-sm hover:bg-accent transition-colors"
            >
              <span>{icon}</span>
              <span>{label}</span>
            </a>
          ))}
        </nav>
        <div className="p-3 border-t border-border">
          <p className="text-[10px] text-muted-foreground mb-1 truncate">{user?.username}</p>
          <button
            onClick={logout}
            className="w-full text-xs text-red-400 hover:text-red-300 text-left py-1 px-2 rounded-sm hover:bg-red-500/10 transition-colors"
          >
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          <Suspense fallback={<PageLoader />}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
  );
}

// ── Auth Provider ─────────────────────────────────────────────────────────────
function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem("noc_user");
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });

  const [editionData, setEditionData] = useState({
    edition: "monitoring_pro",
    edition_name: "NOC-Monitoring-Pro",
    features: {
      monitoring: true, genieacs: false, billing: false,
      customers: false, finance_report: false, auto_isolir: false, n8n: false,
    },
  });

  // Fetch edition info from backend on mount
  useEffect(() => {
    if (!user) return;
    api.get("/system/edition").then(res => {
      setEditionData({
        edition: res.data.edition || "monitoring_pro",
        edition_name: res.data.edition_name || "NOC-Monitoring-Pro",
        features: res.data.features || editionData.features,
      });
    }).catch(() => {});
  }, [user]);

  const login = async (username, password) => {
    const res = await api.post("/auth/login", { username, password });
    const { access_token, user: userData } = res.data;
    localStorage.setItem("noc_token", access_token);
    localStorage.setItem("noc_user", JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem("noc_token");
    localStorage.removeItem("noc_user");
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      <EditionContext.Provider value={editionData}>
        {children}
      </EditionContext.Provider>
    </AuthContext.Provider>
  );
}

// ── Root App ──────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="bottom-right" richColors />
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Public */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/wall" element={<WallDisplayPage />} />

              {/* Protected */}
              <Route element={<ProtectedRoute />}>
                <Route element={<AdminLayout />}>
                  <Route path="/admin" element={<DashboardPage />} />
                  <Route path="/admin/devices" element={<DevicesPage />} />
                  <Route path="/admin/sla" element={<SLAPage />} />
                  <Route path="/admin/incidents" element={<IncidentsPage />} />
                  <Route path="/admin/reports" element={<ReportsPage />} />
                  <Route path="/admin/topology" element={<TopologyPage />} />
                  <Route path="/admin/ping" element={<PingToolPage />} />
                  <Route path="/admin/syslog" element={<SyslogPage />} />
                  <Route path="/admin/backups" element={<BackupsPage />} />
                  <Route path="/admin/scheduler" element={<SchedulerPage />} />
                  <Route path="/admin/notifications" element={<NotificationsPage />} />
                  <Route path="/admin/audit" element={<AuditLogPage />} />
                  <Route path="/admin/settings" element={<SettingsPage />} />
                  <Route path="/admin/users" element={<AdminPage />} />
                  <Route path="/admin/license" element={<LicensePage />} />
                  <Route path="/admin/update" element={<UpdatePage />} />
                </Route>
              </Route>

              {/* Fallback */}
              <Route path="/" element={<Navigate to="/admin" replace />} />
              <Route path="*" element={<Navigate to="/admin" replace />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
