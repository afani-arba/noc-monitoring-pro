import { createContext, useContext, useState, useEffect, lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate, Outlet, NavLink } from "react-router-dom";
import { Toaster } from "sonner";
import api from "@/lib/api";
import { ThemeProvider } from "@/context/ThemeContext";
import {
  LayoutDashboard, Monitor, Server, BarChart2, AlertTriangle, FileText, 
  GitBranch, Activity, Terminal, HardDrive, CalendarClock, Bell, Search, 
  Settings, Users, Key, RefreshCw, Radio
} from "lucide-react";
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
    <div className="flex min-h-screen bg-[#0A0D14] text-slate-200">
      {/* Sidebar */}
      <aside className="w-[260px] border-r border-slate-800/60 bg-[#0B0F19] shadow-[4px_0_24px_-12px_rgba(0,0,0,0.5)] flex flex-col shrink-0 relative z-20">
        <div className="h-16 flex items-center gap-3.5 px-6 border-b border-slate-800/60 mt-1">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-[0_0_15px_rgba(59,130,246,0.3)]">
            <Radio className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-bold text-[14px] tracking-tight block leading-tight text-slate-100">NOC Monitoring</span>
            <span className="text-[9px] text-blue-400 tracking-widest uppercase font-bold">Pro Edition</span>
          </div>
        </div>
        
        {/* Subtle decorative glow */}
        <div className="absolute top-0 left-0 w-full h-32 bg-blue-500/5 blur-2xl pointer-events-none"></div>

        <nav className="flex-1 py-5 px-3.5 space-y-1 overflow-y-auto custom-scrollbar relative z-10">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 px-2">Main Menu</div>
          {[
            { to: "/admin", label: "Dashboard",     icon: LayoutDashboard },
            { to: "/wall",  label: "Wall Display",  icon: Monitor },
            { to: "/admin/devices", label: "Perangkat", icon: Server },
            { to: "/admin/sla", label: "SLA Monitor", icon: BarChart2 },
            { to: "/admin/incidents", label: "Insiden", icon: AlertTriangle },
            { to: "/admin/reports", label: "Laporan", icon: FileText },
            { to: "/admin/topology", label: "Topologi", icon: GitBranch },
            { to: "/admin/ping", label: "Ping Tool", icon: Activity },
            { to: "/admin/syslog", label: "Syslog", icon: Terminal },
            { to: "/admin/backups", label: "Backup", icon: HardDrive },
            { to: "/admin/scheduler", label: "Scheduler", icon: CalendarClock },
            { to: "/admin/notifications", label: "Notifikasi", icon: Bell },
            { to: "/admin/audit", label: "Audit Log", icon: Search },
            { separator: true },
            { to: "/admin/settings", label: "Pengaturan", icon: Settings },
            { to: "/admin/users", label: "User Management", icon: Users },
            { to: "/admin/license", label: "Lisensi", icon: Key },
            { to: "/admin/update", label: "Update Aplikasi", icon: RefreshCw },
          ].map((item, idx) => {
            if (item.separator) {
               return <div key={`sep-${idx}`} className="h-px bg-slate-800/60 my-3 mx-2" />;
            }
            const { to, label, icon: Icon } = item;
            return (
              <NavLink
                key={to}
                to={to}
                end={to === "/admin" || to === "/wall"}
                className={({ isActive }) =>
                  `flex items-center gap-3.5 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-300 group relative overflow-hidden ${
                    isActive
                      ? "text-blue-400 bg-blue-500/10 shadow-[inset_2px_0_0_0_rgba(59,130,246,1)]"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <div className={`relative flex items-center justify-center transition-transform duration-300 ${isActive ? 'scale-110' : 'group-hover:scale-110'}`}>
                       <Icon className={`w-[18px] h-[18px] ${isActive ? 'text-blue-400 drop-shadow-[0_0_8px_rgba(59,130,246,0.4)]' : 'text-slate-400 group-hover:text-slate-300'}`} strokeWidth={isActive ? 2.5 : 2} />
                    </div>
                    <span className="relative z-10 tracking-wide">{label}</span>
                    {isActive && (
                      <div className="absolute right-3 flex h-1.5 w-1.5">
                         <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-60"></span>
                         <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500"></span>
                      </div>
                    )}
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-800/60 bg-[#0B0F19]/90">
          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-slate-800/30 border border-slate-700/50 hover:bg-slate-800/50 transition-colors">
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-slate-700 to-slate-600 flex items-center justify-center text-slate-200 font-bold shadow-inner border border-slate-600/50">
               {user?.username?.charAt(0)?.toUpperCase() || "A"}
            </div>
            <div className="flex-1 min-w-0">
               <p className="text-[13px] font-semibold text-slate-200 truncate tracking-wide">{user?.username || "Admin"}</p>
               <button
                 onClick={logout}
                 className="text-[11px] text-red-400 hover:text-red-300 font-medium transition-colors"
               >
                 Sign Out
               </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative">
        <div className="absolute top-0 left-0 right-0 h-[250px] bg-gradient-to-b from-blue-500/5 to-transparent pointer-events-none z-0"></div>
        <header className="h-16 flex items-center justify-between px-8 border-b border-slate-800/60 bg-[#0B0F19]/80 backdrop-blur-xl sticky top-0 z-30 shadow-[0_2px_20px_-6px_rgba(0,0,0,0.2)]">
           <div className="text-[13px] font-semibold text-slate-300 flex items-center gap-2.5 bg-slate-800/40 px-3 py-1.5 rounded-lg border border-slate-700/50">
             <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse block"></span>
             System Running
           </div>
           <div className="text-[12px] text-slate-400 font-mono font-medium tracking-wide">
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
    api.get("/edition").then(res => {
      setEditionData({
        edition: res.data.edition || "monitoring_pro",
        edition_name: res.data.edition_name || "NOC-Monitoring-Pro",
        features: res.data.features || editionData.features,
      });
    }).catch(() => {});
  }, [user]);

  const login = async (username, password) => {
    const res = await api.post("/auth/login", { username, password });
    const { access_token, token, user: userData } = res.data;
    localStorage.setItem("noc_token", access_token || token);
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
