import { useState, useEffect, useRef, useCallback } from "react";
import api from "@/lib/api";
import {
  Activity, Server, Wifi, WifiOff, RefreshCw, Play, Square, Trash2,
  ChevronDown, ChevronUp, Globe, AlertCircle, CheckCircle, Clock,
  BarChart2, Layers, ArrowUpDown, Terminal, Zap
} from "lucide-react";
import { toast } from "sonner";

// ── Config ───────────────────────────────────────────────────────────────────
const MAX_LOG_LINES = 500;

// ── Helper ───────────────────────────────────────────────────────────────────
function fmtRtt(v) {
  if (v == null) return "—";
  return `${Number(v).toFixed(1)} ms`;
}
function classByRtt(rtt) {
  if (rtt == null) return "text-muted-foreground";
  if (rtt < 30)  return "text-emerald-400";
  if (rtt < 80)  return "text-yellow-400";
  if (rtt < 200) return "text-orange-400";
  return "text-red-400";
}
function classByLoss(pct) {
  if (pct === 0)   return "text-emerald-400";
  if (pct < 10)    return "text-yellow-400";
  if (pct < 50)    return "text-orange-400";
  return "text-red-400";
}
function StatusDot({ status }) {
  const color =
    status === "up"      ? "bg-emerald-500 shadow-[0_0_6px_#10b981]" :
    status === "down"    ? "bg-red-500 shadow-[0_0_6px_#ef4444]" :
    status === "timeout" ? "bg-orange-500" : "bg-zinc-500";
  return <span className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${color}`} />;
}

// ── Mini RTT Sparkline ────────────────────────────────────────────────────────
function RttSparkline({ values }) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values);
  const W = 80, H = 28;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * W;
    const y = H - ((v - min) / (max - min + 0.001)) * (H - 4) - 2;
    return `${x},${y}`;
  }).join(" ");
  const lastRtt = values[values.length - 1];
  const color = lastRtt < 30 ? "#10b981" : lastRtt < 80 ? "#facc15" : lastRtt < 200 ? "#f97316" : "#ef4444";
  return (
    <svg width={W} height={H} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" />
      <circle cx={pts.split(" ").pop().split(",")[0]} cy={pts.split(" ").pop().split(",")[1]} r="2" fill={color} />
    </svg>
  );
}

// ── Terminal Output Line ──────────────────────────────────────────────────────
function LogLine({ entry }) {
  const { type, rtt, from: fromIp, seq, loss_pct, transmitted, received, min, avg, max: mdev, raw } = entry;
  if (type === "start")
    return <p className="text-cyan-400 font-mono text-[11px]">▶ PING {entry.host} — {entry.count} paket, size {entry.size}B</p>;
  if (type === "reply")
    return (
      <p className="font-mono text-[11px]">
        <span className="text-emerald-400">✔</span>{" "}
        <span className="text-zinc-300">dari {fromIp} seq={seq} ttl={entry.ttl} rtt=</span>
        <span className={classByRtt(rtt)}>{fmtRtt(rtt)}</span>
      </p>
    );
  if (type === "timeout")
    return <p className="font-mono text-[11px] text-orange-400">⏱ Request Timeout (seq={seq})</p>;
  if (type === "summary")
    return (
      <p className="font-mono text-[11px]">
        <span className="text-zinc-400">📊 {transmitted} dikirim, {received} diterima — </span>
        <span className={classByLoss(loss_pct)}>{loss_pct}% packet loss</span>
      </p>
    );
  if (type === "rtt_stats")
    return (
      <p className="font-mono text-[11px] text-zinc-400">
        ⚡ min={fmtRtt(entry.min)} avg={fmtRtt(entry.avg)} max={fmtRtt(entry.max)} mdev={fmtRtt(entry.mdev)}
      </p>
    );
  if (type === "done")
    return <p className={`font-mono text-[11px] font-bold ${entry.success ? "text-emerald-400" : "text-red-400"}`}>
      {entry.success ? "✔ Ping selesai" : "✘ Host tidak merespons"}
    </p>;
  if (type === "error")
    return <p className="font-mono text-[11px] text-red-400">✘ Error: {entry.message || raw}</p>;
  if (type === "info" || type === "raw")
    return <p className="font-mono text-[11px] text-zinc-500">{raw}</p>;
  return null;
}

// ══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ══════════════════════════════════════════════════════════════════════════════
export default function PingToolPage() {
  // ── Ping state ──
  const [host, setHost]       = useState("");
  const [count, setCount]     = useState(20);
  const [interval, setInterv] = useState(0.5);
  const [size, setSize]       = useState(56);
  const [running, setRunning] = useState(false);
  const [logs, setLogs]       = useState([]);
  const [rttHistory, setRttHistory] = useState([]);
  const [done, setDone]       = useState(null); // {success, stats}
  const esRef  = useRef(null);
  const logRef = useRef(null);
  const token  = localStorage.getItem("noc_token");

  // ── Bulk sweep state ──
  const [sweeping, setSweeping]   = useState(false);
  const [sweepResults, setSweepResults] = useState(null);
  const [searchQ, setSearchQ]     = useState("");
  const [sortBy, setSortBy]       = useState("status"); // status|rtt|name
  const [activeTab, setActiveTab] = useState("single"); // single|bulk

  // ── Auto-scroll terminal ──
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  // ── Start streaming ping ──
  const startPing = useCallback(() => {
    if (!host.trim()) { toast.error("Masukkan host atau IP address"); return; }
    if (esRef.current) { esRef.current.close(); }

    setRunning(true);
    setLogs([]);
    setRttHistory([]);
    setDone(null);

    const BASE_URL = process.env.REACT_APP_API_URL || window.location.origin.replace(":3000", ":8000");
    const params = new URLSearchParams({
      host: host.trim(), count, interval, size,
    });
    if (token) params.append("token", token);
    const url = `${BASE_URL}/api/network-tools/ping/stream?${params}`;

    const es = new EventSource(url, {
      // EVentSource tidak support custom headers — gunakan query param token jika perlu
    });

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        setLogs(prev => [...prev.slice(-MAX_LOG_LINES), data]);
        if (data.type === "reply" && data.rtt != null) {
          setRttHistory(prev => [...prev.slice(-60), data.rtt]);
        }
        if (data.type === "done") {
          setDone(data);
          setRunning(false);
          es.close();
        }
        if (data.type === "error" || data.type === "cancelled") {
          setRunning(false);
          es.close();
        }
      } catch (_) {}
    };

    es.onerror = () => {
      setRunning(false);
      es.close();
    };

    esRef.current = es;
  }, [host, count, interval, size]);

  const stopPing = () => {
    if (esRef.current) { esRef.current.close(); esRef.current = null; }
    setRunning(false);
    setLogs(prev => [...prev, { type: "info", raw: "⏹ Ping dihentikan oleh user" }]);
  };

  // ── Handle Enter key ──
  const handleKey = (e) => { if (e.key === "Enter" && !running) startPing(); };

  // ── Bulk sweep ──
  const runSweep = async () => {
    setSweeping(true);
    setSweepResults(null);
    try {
      const res = await api.get("/network-tools/ping/bulk");
      setSweepResults(res.data);
      toast.success(`Sweep selesai: ${res.data.summary.up}↑ up, ${res.data.summary.down}↓ down`);
    } catch (e) {
      toast.error("Sweep gagal: " + (e.response?.data?.detail || e.message));
    } finally {
      setSweeping(false);
    }
  };

  // ── Sort & filter sweep results ──
  const filteredResults = (sweepResults?.results || [])
    .filter(r => {
      if (!searchQ) return true;
      const q = searchQ.toLowerCase();
      return (r.name || "").toLowerCase().includes(q) || (r.ip || "").includes(q);
    })
    .sort((a, b) => {
      if (sortBy === "rtt")    return (a.rtt_avg || 9999) - (b.rtt_avg || 9999);
      if (sortBy === "name")   return (a.name || "").localeCompare(b.name || "");
      // Default: down first, then by rtt
      if (a.status !== b.status) return a.status === "down" ? -1 : 1;
      return (a.rtt_avg || 9999) - (b.rtt_avg || 9999);
    });

  // ── Stats dari rttHistory ──
  const liveStats = rttHistory.length > 0 ? {
    min: Math.min(...rttHistory),
    max: Math.max(...rttHistory),
    avg: rttHistory.reduce((s, v) => s + v, 0) / rttHistory.length,
    count: rttHistory.length,
  } : null;

  return (
    <div className="space-y-4 pb-16">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            Network Ping Tool
          </h1>
          <p className="text-xs text-muted-foreground">Uji koneksi real-time ke host atau semua device terdaftar</p>
        </div>
      </div>

      {/* ── Tab ── */}
      <div className="flex border-b border-border/50">
        <button
          onClick={() => setActiveTab("single")}
          className={`px-5 py-2.5 text-sm font-semibold transition-colors ${activeTab === "single" ? "border-b-2 border-cyan-400 text-cyan-400" : "text-muted-foreground hover:text-foreground"}`}
        >
          <span className="flex items-center gap-2"><Terminal className="w-3.5 h-3.5" /> Ping Host</span>
        </button>
        <button
          onClick={() => setActiveTab("bulk")}
          className={`px-5 py-2.5 text-sm font-semibold transition-colors ${activeTab === "bulk" ? "border-b-2 border-purple-400 text-purple-400" : "text-muted-foreground hover:text-foreground"}`}
        >
          <span className="flex items-center gap-2"><Layers className="w-3.5 h-3.5" /> Device Sweep</span>
        </button>
      </div>

      {/* ═══════════════════════════════ TAB: PING SINGLE ════════════════════ */}
      {activeTab === "single" && (
        <div className="space-y-4">
          {/* Control Bar */}
          <div className="bg-card border border-border rounded-xl p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3">
              {/* Host input */}
              <div className="flex-1 flex items-center gap-2 bg-background border border-border rounded-lg px-3 py-2 focus-within:border-cyan-500/60 transition-colors">
                <Globe className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <input
                  id="ping-host-input"
                  type="text"
                  value={host}
                  onChange={e => setHost(e.target.value)}
                  onKeyDown={handleKey}
                  placeholder="IP / Hostname  (contoh: 8.8.8.8  atau  google.com)"
                  disabled={running}
                  className="flex-1 bg-transparent text-sm font-mono text-foreground placeholder:text-muted-foreground/50 outline-none"
                />
              </div>
              {/* Action buttons */}
              <div className="flex gap-2">
                {!running ? (
                  <button
                    id="btn-start-ping"
                    onClick={startPing}
                    disabled={!host.trim()}
                    className="flex items-center gap-2 px-5 py-2 bg-cyan-500 hover:bg-cyan-400 text-black font-bold rounded-lg text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(6,182,212,0.3)]"
                  >
                    <Play className="w-4 h-4" /> Ping
                  </button>
                ) : (
                  <button
                    id="btn-stop-ping"
                    onClick={stopPing}
                    className="flex items-center gap-2 px-5 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/40 text-red-400 font-bold rounded-lg text-sm transition-all"
                  >
                    <Square className="w-4 h-4" /> Stop
                  </button>
                )}
                <button
                  onClick={() => { setLogs([]); setRttHistory([]); setDone(null); }}
                  disabled={running}
                  className="flex items-center gap-1.5 px-3 py-2 bg-secondary/40 hover:bg-secondary/60 text-muted-foreground rounded-lg text-sm transition-colors disabled:opacity-40"
                  title="Bersihkan output"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Options */}
            <div className="flex flex-wrap gap-4 pt-1">
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="text-zinc-500">Jumlah Paket</span>
                <select
                  value={count}
                  onChange={e => setCount(Number(e.target.value))}
                  disabled={running}
                  className="bg-secondary/40 border border-border rounded px-2 py-1 text-xs text-foreground"
                >
                  {[5, 10, 20, 50, 100].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="text-zinc-500">Interval</span>
                <select
                  value={interval}
                  onChange={e => setInterv(Number(e.target.value))}
                  disabled={running}
                  className="bg-secondary/40 border border-border rounded px-2 py-1 text-xs text-foreground"
                >
                  {[0.2, 0.5, 1, 2].map(n => <option key={n} value={n}>{n}s</option>)}
                </select>
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="text-zinc-500">Ukuran Paket</span>
                <select
                  value={size}
                  onChange={e => setSize(Number(e.target.value))}
                  disabled={running}
                  className="bg-secondary/40 border border-border rounded px-2 py-1 text-xs text-foreground"
                >
                  {[32, 56, 128, 512, 1400].map(n => <option key={n} value={n}>{n}B</option>)}
                </select>
              </label>
            </div>
          </div>

          {/* Stats Row */}
          {liveStats && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Min RTT",  value: fmtRtt(liveStats.min), color: "text-emerald-400" },
                { label: "Avg RTT",  value: fmtRtt(liveStats.avg), color: classByRtt(liveStats.avg) },
                { label: "Max RTT",  value: fmtRtt(liveStats.max), color: classByRtt(liveStats.max) },
                { label: "Diterima", value: `${liveStats.count}/${count}`, color: liveStats.count === count ? "text-emerald-400" : "text-yellow-400" },
              ].map(s => (
                <div key={s.label} className="bg-card border border-border rounded-lg px-4 py-3">
                  <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{s.label}</p>
                  <p className={`text-xl font-bold font-mono ${s.color}`}>{s.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Layout: Terminal (kiri) + Sparkline (kanan) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Terminal Output */}
            <div className="lg:col-span-2 bg-[#09090b] border border-[#27272a] rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-2 border-b border-[#27272a] bg-[#111113]">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <span className="w-3 h-3 rounded-full bg-red-500/80" />
                    <span className="w-3 h-3 rounded-full bg-yellow-500/80" />
                    <span className="w-3 h-3 rounded-full bg-green-500/80" />
                  </div>
                  <span className="text-xs text-zinc-500 font-mono ml-2">ping terminal</span>
                </div>
                {running && (
                  <span className="flex items-center gap-1.5 text-[10px] text-cyan-400 font-mono">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
                    LIVE
                  </span>
                )}
              </div>
              <div
                ref={logRef}
                className="h-80 overflow-y-auto p-4 space-y-0.5 font-mono text-[11px] leading-relaxed"
              >
                {logs.length === 0 ? (
                  <p className="text-zinc-600 text-xs text-center mt-16">
                    Masukkan host dan klik Ping untuk memulai
                  </p>
                ) : (
                  logs.map((entry, i) => <LogLine key={i} entry={entry} />)
                )}
              </div>
            </div>

            {/* RTT Realtime Chart */}
            <div className="bg-card border border-border rounded-xl p-4 flex flex-col">
              <p className="text-xs font-semibold mb-1 flex items-center gap-1.5">
                <BarChart2 className="w-3.5 h-3.5 text-cyan-400" />
                Grafik RTT Real-time
              </p>
              <p className="text-[10px] text-muted-foreground mb-4">Riwayat {rttHistory.length} reply terakhir</p>

              {rttHistory.length < 2 ? (
                <div className="flex-1 flex items-center justify-center text-muted-foreground">
                  <div className="text-center">
                    <Activity className="w-8 h-8 mx-auto mb-2 opacity-20" />
                    <p className="text-xs">Data akan muncul saat ping berjalan</p>
                  </div>
                </div>
              ) : (
                <div className="flex-1">
                  {/* SVG Chart */}
                  <RttBarChart values={rttHistory} />
                </div>
              )}

              {/* Result Summary */}
              {done && (
                <div className={`mt-4 p-3 rounded-lg border text-xs ${done.success ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-300" : "bg-red-500/10 border-red-500/20 text-red-300"}`}>
                  {done.success ? (
                    <>
                      <p className="font-bold mb-1">✔ Ping Berhasil</p>
                      <p>Min: {fmtRtt(done.stats?.min)} · Avg: {fmtRtt(done.stats?.avg)} · Max: {fmtRtt(done.stats?.max)}</p>
                    </>
                  ) : (
                    <p className="font-bold">✘ Host tidak merespons (100% loss)</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════ TAB: BULK SWEEP ═════════════════════ */}
      {activeTab === "bulk" && (
        <div className="space-y-4">
          {/* Controls */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <div>
                <p className="text-sm font-semibold">Device Ping Sweep</p>
                <p className="text-xs text-muted-foreground">Ping semua {sweepResults?.summary?.total || "device"} yang terdaftar secara paralel untuk deteksi outage masif</p>
              </div>
              <button
                id="btn-run-sweep"
                onClick={runSweep}
                disabled={sweeping}
                className="sm:ml-auto flex items-center gap-2 px-5 py-2.5 bg-purple-500 hover:bg-purple-400 text-white font-bold rounded-lg text-sm transition-all disabled:opacity-50 shadow-[0_0_15px_rgba(168,85,247,0.25)]"
              >
                {sweeping ? (
                  <><RefreshCw className="w-4 h-4 animate-spin" /> Sweeping...</>
                ) : (
                  <><Zap className="w-4 h-4" /> Jalankan Sweep</>
                )}
              </button>
            </div>

            {/* Summary Cards */}
            {sweepResults?.summary && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
                {[
                  { label: "Total Device", value: sweepResults.summary.total, color: "text-zinc-300" },
                  { label: "Online ↑",     value: sweepResults.summary.up,    color: "text-emerald-400" },
                  { label: "Offline ↓",   value: sweepResults.summary.down,   color: "text-red-400" },
                  { label: "Packet Loss", value: `${sweepResults.summary.loss_pct}%`, color: sweepResults.summary.loss_pct > 10 ? "text-orange-400" : "text-emerald-400" },
                ].map(c => (
                  <div key={c.label} className="bg-background border border-border rounded-lg px-4 py-3">
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wide mb-1">{c.label}</p>
                    <p className={`text-2xl font-bold font-mono ${c.color}`}>{c.value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Results Table */}
          {sweepResults && (
            <div className="bg-card border border-border rounded-xl overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3 border-b border-border/50">
                <p className="text-xs font-semibold flex-1">Hasil Sweep — {filteredResults.length} device</p>
                <input
                  type="text"
                  placeholder="Cari nama / IP..."
                  value={searchQ}
                  onChange={e => setSearchQ(e.target.value)}
                  className="bg-background border border-border rounded px-2.5 py-1 text-xs w-40 font-mono"
                />
                <select
                  value={sortBy}
                  onChange={e => setSortBy(e.target.value)}
                  className="bg-background border border-border rounded px-2 py-1 text-xs"
                >
                  <option value="status">Sort: Status</option>
                  <option value="rtt">Sort: RTT</option>
                  <option value="name">Sort: Nama</option>
                </select>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-border bg-secondary/10">
                      {["Status", "Nama Device", "IP Address", "Avg RTT", "Packet Loss", "Grafik RTT"].map(h => (
                        <th key={h} className="px-4 py-2.5 text-[10px] text-muted-foreground uppercase tracking-wider font-medium whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredResults.length === 0 ? (
                      <tr><td colSpan={6} className="px-4 py-12 text-center text-muted-foreground text-xs">Tidak ada device yang cocok</td></tr>
                    ) : filteredResults.map((r, i) => (
                      <tr key={r.id || i} className="border-b border-border/20 hover:bg-secondary/10 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <StatusDot status={r.status} />
                            <span className={`text-xs font-bold uppercase ${r.status === "up" ? "text-emerald-400" : r.status === "down" ? "text-red-400" : "text-orange-400"}`}>
                              {r.status === "up" ? "UP" : r.status === "down" ? "DOWN" : "TIMEOUT"}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-xs font-semibold text-foreground">{r.name || "—"}</td>
                        <td className="px-4 py-3 text-xs font-mono text-muted-foreground">{r.ip || r.ip_address}</td>
                        <td className={`px-4 py-3 text-xs font-mono font-bold ${classByRtt(r.rtt_avg)}`}>{fmtRtt(r.rtt_avg)}</td>
                        <td className={`px-4 py-3 text-xs font-mono ${classByLoss(r.loss_pct)}`}>{r.loss_pct != null ? `${r.loss_pct}%` : "—"}</td>
                        <td className="px-4 py-3">
                          {r.status === "up" && r.rtt_avg ? (
                            <div className="flex items-center gap-1">
                              <div
                                className="h-3 rounded-sm"
                                style={{
                                  width: `${Math.min(90, (r.rtt_avg / 200) * 90)}px`,
                                  background: r.rtt_avg < 30 ? "#10b981" : r.rtt_avg < 80 ? "#facc15" : r.rtt_avg < 200 ? "#f97316" : "#ef4444",
                                  opacity: 0.85,
                                }}
                              />
                            </div>
                          ) : (
                            <span className="text-muted-foreground text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {!sweepResults && !sweeping && (
            <div className="bg-card border border-border/50 border-dashed rounded-xl py-16 text-center text-muted-foreground">
              <Server className="w-10 h-10 mx-auto mb-3 opacity-20" />
              <p className="text-sm">Klik "Jalankan Sweep" untuk ping semua device</p>
              <p className="text-xs mt-1 opacity-60">Setiap device akan diping 3 paket secara paralel</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── RTT Bar Chart SVG ─────────────────────────────────────────────────────────
function RttBarChart({ values }) {
  const W = 300, H = 140;
  const maxV = Math.max(...values, 1);
  const barW = Math.max(3, Math.floor((W - 8) / values.length) - 1);

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full h-36">
      {/* Grid lines */}
      {[0.25, 0.5, 0.75, 1].map(f => (
        <line key={f} x1={4} y1={H * f} x2={W - 4} y2={H * f}
          stroke="#27272a" strokeWidth="0.5" strokeDasharray="3 3" />
      ))}
      {/* Bars */}
      {values.map((v, i) => {
        const bh = Math.max(2, (v / maxV) * (H - 16));
        const x = 4 + i * (barW + 1);
        const y = H - bh - 2;
        const color = v < 30 ? "#10b981" : v < 80 ? "#facc15" : v < 200 ? "#f97316" : "#ef4444";
        return (
          <g key={i}>
            <rect x={x} y={y} width={barW} height={bh} fill={color} opacity={0.8} rx={1} />
          </g>
        );
      })}
      {/* Last value label */}
      <text
        x={W - 6}
        y={14}
        textAnchor="end"
        fontSize={10}
        fill={values[values.length - 1] < 30 ? "#10b981" : values[values.length - 1] < 80 ? "#facc15" : "#f97316"}
        fontFamily="monospace"
      >
        {fmtRtt(values[values.length - 1])}
      </text>
    </svg>
  );
}
