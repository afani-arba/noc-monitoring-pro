import { useEffect, useRef, useState, useCallback } from "react";
import api from "@/lib/api";

// ── Status helpers ────────────────────────────────────────────────────────────
const STATUS_COLOR = {
  online:  "#22c55e",
  offline: "#ef4444",
  warning: "#eab308",
  unknown: "#6b7280",
};

const STATUS_LABEL = {
  online:  "Online",
  offline: "Offline",
  warning: "Warning",
  unknown: "Unknown",
};

function getStatus(device) {
  if (!device) return "unknown";
  if (device.status === "online"  || device.is_up === true)  return "online";
  if (device.status === "offline" || device.is_up === false) return "offline";
  if (device.status === "warning") return "warning";
  return "unknown";
}

// ── Leaflet lazy loader ───────────────────────────────────────────────────────
let leafletLoaded = false;
let L = null;

async function loadLeaflet() {
  if (leafletLoaded) return L;
  // Load CSS
  if (!document.getElementById("leaflet-css")) {
    const link = document.createElement("link");
    link.id   = "leaflet-css";
    link.rel  = "stylesheet";
    link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.appendChild(link);
  }
  // Load JS
  await new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
    script.onload  = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
  L = window.L;
  leafletLoaded = true;
  return L;
}

// ── SVG Marker factory ────────────────────────────────────────────────────────
function makeIcon(color, size = 14) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size * 2}" height="${size * 2}" viewBox="0 0 ${size * 2} ${size * 2}">
    <circle cx="${size}" cy="${size}" r="${size - 2}" fill="${color}" stroke="#fff" stroke-width="2" opacity="0.95"/>
  </svg>`;
  return `data:image/svg+xml;base64,${btoa(svg)}`;
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function GeoMap() {
  const mapRef      = useRef(null);
  const mapInstance = useRef(null);
  const markersRef  = useRef({});

  const [devices, setDevices]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [filter, setFilter]     = useState("all");
  const [saving, setSaving]     = useState(false);
  const [leafletReady, setLeafletReady] = useState(false);

  // ── Fetch devices ───────────────────────────────────────────────────────────
  const fetchDevices = useCallback(async () => {
    try {
      const res = await api.get("/devices/all");
      setDevices(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      setError("Gagal memuat data perangkat: " + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDevices(); }, [fetchDevices]);

  // ── Load Leaflet ────────────────────────────────────────────────────────────
  useEffect(() => {
    loadLeaflet().then(() => setLeafletReady(true)).catch(() => {
      setError("Gagal memuat library peta. Pastikan server memiliki akses internet.");
    });
  }, []);

  // ── Init Map ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!leafletReady || !mapRef.current || mapInstance.current) return;

    mapInstance.current = L.map(mapRef.current, {
      center: [-2.5, 117.5],
      zoom: 5,
      zoomControl: true,
    });

    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(mapInstance.current);

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [leafletReady]);

  // ── Render Markers ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!leafletReady || !mapInstance.current || devices.length === 0) return;

    const map = mapInstance.current;
    // Remove old markers
    Object.values(markersRef.current).forEach(m => m.remove());
    markersRef.current = {};

    const visible = devices.filter(d => {
      if (filter === "online")  return getStatus(d) === "online";
      if (filter === "offline") return getStatus(d) === "offline";
      return true;
    });

    const bounds = [];

    visible.forEach((device, idx) => {
      const status = getStatus(device);
      const color  = STATUS_COLOR[status];
      const lat    = device.latitude  ?? (-6 + (idx * 0.15) % 10);
      const lng    = device.longitude ?? (106 + (idx * 0.2) % 10);

      bounds.push([lat, lng]);

      const icon = L.icon({
        iconUrl: makeIcon(color),
        iconSize:   [20, 20],
        iconAnchor: [10, 10],
        popupAnchor:[0, -12],
      });

      const marker = L.marker([lat, lng], { icon, draggable: editMode })
        .addTo(map)
        .bindPopup(`
          <div style="font-family:sans-serif;min-width:180px">
            <b style="color:${color}">${STATUS_LABEL[status]}</b>
            <div style="font-size:13px;font-weight:bold;margin:4px 0">${device.name || device.ip_address}</div>
            <div style="font-size:11px;color:#aaa">${device.ip_address || ""}</div>
            ${device.location ? `<div style="font-size:11px;color:#888;margin-top:2px">📍 ${device.location}</div>` : ""}
            ${device.cpu_load != null ? `<div style="font-size:11px;margin-top:4px">CPU: ${device.cpu_load}% | RAM: ${device.memory_usage ?? "-"}%</div>` : ""}
            ${device.ping_latency != null ? `<div style="font-size:11px">Ping: ${device.ping_latency} ms</div>` : ""}
          </div>
        `);

      // Save position on drag
      marker.on("dragend", async (e) => {
        const { lat: newLat, lng: newLng } = e.target.getLatLng();
        setSaving(true);
        try {
          await api.patch(`/devices/${device.id}/location`, { latitude: newLat, longitude: newLng });
        } catch { /* silent */ } finally {
          setSaving(false);
        }
      });

      markersRef.current[device.id] = marker;
    });

    if (bounds.length > 0) {
      try { map.fitBounds(bounds, { padding: [40, 40] }); } catch { /* ignore */ }
    }
  }, [leafletReady, devices, filter, editMode]);

  // Toggle draggable on edit mode change
  useEffect(() => {
    Object.values(markersRef.current).forEach(m => {
      if (editMode) m.dragging?.enable();
      else m.dragging?.disable();
    });
  }, [editMode]);

  // ── Filtered counts ─────────────────────────────────────────────────────────
  const onlineCount  = devices.filter(d => getStatus(d) === "online").length;
  const offlineCount = devices.filter(d => getStatus(d) === "offline").length;
  const warnCount    = devices.filter(d => getStatus(d) === "warning").length;

  // ── Fit all markers ─────────────────────────────────────────────────────────
  const fitAll = () => {
    const pts = Object.values(markersRef.current).map(m => m.getLatLng());
    if (pts.length > 0 && mapInstance.current) {
      mapInstance.current.fitBounds(pts.map(p => [p.lat, p.lng]), { padding: [40, 40] });
    }
  };

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 p-3 bg-card border border-border rounded-lg">
        <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block" />
            Online: <b className="text-green-400">{onlineCount}</b>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block" />
            Offline: <b className="text-red-400">{offlineCount}</b>
          </span>
          {warnCount > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full bg-yellow-500 inline-block" />
              Warning: <b className="text-yellow-400">{warnCount}</b>
            </span>
          )}
          {saving && <span className="text-yellow-400 animate-pulse">Menyimpan posisi...</span>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Filter */}
          {["all", "online", "offline"].map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1 text-xs rounded border transition-colors ${
                filter === f
                  ? "bg-primary text-primary-foreground border-primary"
                  : "border-border text-muted-foreground hover:bg-accent"
              }`}>
              {f === "all" ? "Semua" : f === "online" ? "Online" : "Offline"}
            </button>
          ))}
          <button onClick={fitAll}
            className="px-3 py-1 text-xs rounded border border-border text-muted-foreground hover:bg-accent transition-colors">
            Fit All
          </button>
          <button onClick={() => setEditMode(v => !v)}
            className={`px-3 py-1 text-xs rounded border transition-colors ${
              editMode
                ? "bg-green-600 text-white border-green-600"
                : "border-border text-muted-foreground hover:bg-accent"
            }`}>
            {editMode ? "🔓 Edit Mode" : "🔒 Terkunci"}
          </button>
          <button onClick={fetchDevices}
            className="px-3 py-1 text-xs rounded border border-border text-muted-foreground hover:bg-accent transition-colors">
            ↻ Refresh
          </button>
        </div>
      </div>

      {/* Map Area */}
      <div className="relative rounded-lg overflow-hidden border border-border" style={{ height: "520px" }}>
        {(loading || !leafletReady) && (
          <div className="absolute inset-0 bg-card flex items-center justify-center z-10 text-muted-foreground text-sm">
            {loading ? "Memuat data perangkat..." : "Memuat peta..."}
          </div>
        )}
        {error && (
          <div className="absolute inset-0 bg-card flex items-center justify-center z-10">
            <div className="text-center text-sm text-red-400 p-6 max-w-sm">
              <p className="font-semibold mb-1">⚠️ Error</p>
              <p>{error}</p>
              <button onClick={() => { setError(null); fetchDevices(); }}
                className="mt-3 px-4 py-1.5 bg-primary text-primary-foreground rounded text-xs">
                Coba Lagi
              </button>
            </div>
          </div>
        )}
        <div ref={mapRef} style={{ width: "100%", height: "100%" }} />
      </div>

      {/* Device Table */}
      {devices.length > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-4 py-2 border-b border-border text-xs font-semibold text-muted-foreground">
            Daftar Perangkat ({devices.length})
          </div>
          <div className="overflow-x-auto max-h-56 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-muted/80">
                <tr className="text-left text-muted-foreground">
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Nama</th>
                  <th className="px-4 py-2">IP</th>
                  <th className="px-4 py-2">CPU</th>
                  <th className="px-4 py-2">RAM</th>
                  <th className="px-4 py-2">Ping</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {devices.map(d => {
                  const status = getStatus(d);
                  return (
                    <tr key={d.id}
                      className="hover:bg-accent/50 cursor-pointer transition-colors"
                      onClick={() => {
                        const m = markersRef.current[d.id];
                        if (m && mapInstance.current) {
                          mapInstance.current.setView(m.getLatLng(), 12);
                          m.openPopup();
                        }
                      }}>
                      <td className="px-4 py-1.5">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          status === "online"  ? "bg-green-500/10 text-green-400" :
                          status === "offline" ? "bg-red-500/10 text-red-400" :
                          status === "warning" ? "bg-yellow-500/10 text-yellow-400" :
                          "bg-gray-500/10 text-gray-400"
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            status === "online"  ? "bg-green-400" :
                            status === "offline" ? "bg-red-400" :
                            status === "warning" ? "bg-yellow-400" : "bg-gray-400"
                          }`} />
                          {STATUS_LABEL[status]}
                        </span>
                      </td>
                      <td className="px-4 py-1.5 font-medium">{d.name || "-"}</td>
                      <td className="px-4 py-1.5 font-mono text-muted-foreground">{d.ip_address}</td>
                      <td className="px-4 py-1.5">{d.cpu_load != null ? `${d.cpu_load}%` : "-"}</td>
                      <td className="px-4 py-1.5">{d.memory_usage != null ? `${d.memory_usage}%` : "-"}</td>
                      <td className="px-4 py-1.5">{d.ping_latency != null ? `${d.ping_latency}ms` : "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
