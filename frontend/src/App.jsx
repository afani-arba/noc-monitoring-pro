import { createContext, useContext, useState, useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, NavLink } from "react-router-dom";
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
    <div className="flex min-h-screen bg-secondary/10 text-foreground">
      {/* Sidebar */}
      <aside className="w-64 border-r border-border/40 bg-card shadow-[4px_0_24px_-12px_rgba(0,0,0,0.1)] flex flex-col shrink-0 relative z-20">
        <div className="h-16 flex items-center gap-3 px-5 border-b border-border/40">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-primary to-primary/80 flex items-center justify-center shadow-sm">
            <span className="text-primary-foreground text-[16px]">📡</span>
          </div>
          <div>
            <span className="font-bold text-[15px] tracking-tight block leading-tight">NOC Monitoring</span>
            <span className="text-[10px] text-muted-foreground tracking-widest uppercase font-medium">Pro Edition</span>
          </div>
        </div>
        <nav className="flex-1 py-5 px-3 space-y-1.5 overflow-y-auto custom-scrollbar">
          {[
            { to: "/admin", label: "Dashboard",     icon: "🖥️" },
            { to: "/wall",  label: "Wall Display",  icon: "📺" },
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
            <NavLink
              key={to}
              to={to}
              end={to === "/admin" || to === "/wall"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 group relative ${
                  isActive
                    ? "bg-primary/10 text-primary shadow-[inset_0_0_0_1px_rgba(var(--primary),0.2)]"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span className={`text-[16px] transition-transform duration-200 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>{icon}</span>
                  <span>{label}</span>
                  {isActive && (
                    <div className="absolute right-3 flex h-2 w-2">
                       <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-50"></span>
                       <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                    </div>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-border/40 bg-card/50">
          <div className="flex items-center gap-3 p-2 rounded-xl bg-secondary/30 border border-border/40 hover:bg-secondary/50 transition-colors">
            <div className="w-9 h-9 rounded-full bg-primary/20 flex items-center justify-center text-primary font-bold shadow-sm">
               {user?.username?.charAt(0)?.toUpperCase() || "A"}
            </div>
            <div className="flex-1 min-w-0">
               <p className="text-[13px] font-semibold text-foreground truncate">{user?.username || "Admin"}</p>
               <button
                 onClick={logout}
                 className="text-[11px] text-destructive hover:text-red-400 font-medium transition-colors"
               >
                 Sign Out
               </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <div className="absolute top-0 left-0 right-0 h-[250px] bg-gradient-to-b from-primary/5 to-transparent pointer-events-none z-0"></div>
        <header className="h-16 flex items-center justify-between px-6 border-b border-border/50 bg-card/70 backdrop-blur-xl sticky top-0 z-30 shadow-[0_2px_20px_-6px_rgba(0,0,0,0.05)]">
           <div className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
             <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse block"></span>
             System Running
           </div>
           <div className="text-xs text-muted-foreground font-mono">
             {new Date().toLocaleDateString('id-ID', {day: 'numeric', month: 'long', year: 'numeric'})}
           </div>
        </header>
        <div className="flex-1 overflow-auto p-6 relative z-10 custom-scrollbar">
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
