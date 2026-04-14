#!/usr/bin/env python3
"""
NOC Monitoring Pro L2TP Agent v2 — ip l2tp (Kernel Native)
===========================================================
Menggunakan 'ip l2tp' dan PPP session via kernel L2TPv2/L2TPv3
TANPA memerlukan xl2tpd, pppd, atau /dev/ppp device node.
Kompatibel dengan LXC container di Proxmox.

Endpoints:
  GET  /status      - Status link L2TP (IP, bytes, uptime)
  GET  /health      - Cek kesehatan agent
  POST /connect     - Setup & dial L2TP tunnel
  POST /disconnect  - Putus link L2TP
"""

import os
import socket
import subprocess
import time
import json
import logging
import struct
import threading
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8002
VPN_IFACE   = "l2tp0"        # interface yang kita buat via ip l2tp
PPP_IFACE   = "ppp0"         # ppp interface jika pakai xl2tpd fallback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [l2tp-agent] %(levelname)s %(message)s"
)
logger = logging.getLogger(__name__)


def _run(cmd: list, timeout: int = 20) -> tuple:
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout)
        out = (r.stdout + r.stderr).strip()
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "Command timeout"
    except Exception as e:
        return False, str(e)


def _get_ppp_iface():
    """Cari interface ppp atau l2tp yang aktif."""
    for iface_prefix in ["l2tp", "ppp"]:
        ok, out = _run(["ip", "-4", "-o", "addr", "show"])
        if ok and out:
            for line in out.splitlines():
                if iface_prefix in line and "inet" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        return parts[1]
    return None


def get_status() -> dict:
    """Baca status interface L2TP/PPP aktif."""
    state = {"status": "offline", "endpoint": "", "rx_bytes": 0, "tx_bytes": 0, "uptime": 0}

    # Cek semua kandidat interface
    ok, out = _run(["ip", "-4", "-o", "addr", "show"])
    if ok and out:
        for line in out.splitlines():
            for pfx in ["ppp", "l2tp"]:
                if pfx in line and "inet" in line:
                    parts = line.split()
                    iface = parts[1].rstrip(":")
                    if "inet" in parts:
                        idx = parts.index("inet")
                        state["endpoint"] = parts[idx + 1].split("/")[0]
                        state["status"]   = "online"
                        state["interface"] = iface
                        # Statistik
                        base = f"/sys/class/net/{iface}/statistics"
                        for key, fname in [("rx_bytes", "rx_bytes"), ("tx_bytes", "tx_bytes")]:
                            try:
                                with open(f"{base}/{fname}") as f:
                                    state[key] = int(f.read().strip())
                            except Exception:
                                pass
                        return state
    return state


def _kill_existing():
    """Bersihkan semua koneksi L2TP lama."""
    _run(["pkill", "-f", "xl2tpd"], timeout=5)
    _run(["pkill", "-f", "pppd"], timeout=5)
    _run(["pkill", "-f", "l2tpns"], timeout=5)
    # Hapus tunnel ip l2tp lama jika ada
    ok, out = _run(["ip", "l2tp", "show", "tunnel"])
    if ok and out:
        for line in out.splitlines():
            if "Tunnel" in line:
                try:
                    tid = line.split()[1].rstrip(",")
                    _run(["ip", "l2tp", "delete", "tunnel", "tunnel_id", tid], timeout=5)
                except Exception:
                    pass
    # Hapus interface l2tp0/ppp0
    for iface in ["l2tp0", "ppp0", "ppp1"]:
        _run(["ip", "link", "delete", iface], timeout=5)
    time.sleep(1)


def l2tp_connect_xl2tpd(server: str, username: str, password: str, auto_routes: str = "") -> dict:
    """
    Mode 1: xl2tpd + PPP (untuk host dengan /dev/ppp).
    Digunakan sebagai fallback jika mode ip l2tp gagal.
    """
    xl2tpd_conf = f"""
[lac myvpn]
lns = {server}
ppp debug = yes
pppoptfile = /etc/ppp/options.l2tp.client
length bit = yes
"""
    ppp_options = f"""noauth
proxyarp
name "{username}"
password "{password}"
noipdefault
nodefaultroute
usepeerdns
require-mschap-v2
refuse-eap
refuse-pap
refuse-chap
refuse-mschap
"""
    try:
        os.makedirs("/etc/xl2tpd", exist_ok=True)
        os.makedirs("/etc/ppp",    exist_ok=True)
        with open("/etc/xl2tpd/xl2tpd.conf", "w") as f:
            f.write(xl2tpd_conf)
        with open("/etc/ppp/options.l2tp.client", "w") as f:
            f.write(ppp_options)
    except Exception as e:
        return {"ok": False, "error": f"Gagal tulis config: {e}"}

    _run(["systemctl", "restart", "xl2tpd"])
    time.sleep(1)

    # Dial
    control_path = "/var/run/xl2tpd/l2tp-control"
    for _ in range(5):
        if os.path.exists(control_path):
            break
        time.sleep(0.5)

    try:
        with open(control_path, "w") as f:
            f.write("c myvpn")
    except Exception as e:
        return {"ok": False, "error": f"Gagal dial xl2tpd: {e}"}

    for _ in range(20):
        time.sleep(1)
        st = get_status()
        if st["status"] == "online":
            iface = st.get("interface", "ppp0")
            # Auto routes
            _add_routes(iface, auto_routes)
            return {"ok": True, "message": f"L2TP Connected! IP: {st['endpoint']}", "status": st}

    return {"ok": False, "error": "Timeout: PPP interface tidak muncul. Cek /dev/ppp dan pppd log."}


def _add_routes(iface: str, auto_routes: str):
    """Tambahkan route static via interface VPN."""
    if auto_routes:
        routes = [r.strip() for r in auto_routes.split(",") if r.strip()]
        for r in routes:
            logger.info(f"[l2tp-agent] Adding route: {r} via {iface}")
            _run(["ip", "route", "replace", r, "dev", iface])


def l2tp_connect_nmcli(server: str, username: str, password: str, auto_routes: str = "") -> dict:
    """
    Mode 2: NetworkManager (nmcli) — bekerja di LXC yang punya NetworkManager.
    Membuat koneksi L2TP tanpa /dev/ppp.
    """
    # Hapus koneksi lama jika ada
    _run(["nmcli", "connection", "delete", "noc-l2tp"], timeout=10)
    time.sleep(0.5)

    # Buat koneksi L2TP baru via nmcli
    cmd = [
        "nmcli", "connection", "add",
        "type", "vpn",
        "vpn-type", "l2tp",
        "con-name", "noc-l2tp",
        "ifname", "--",
        "connection.id", "noc-l2tp",
        "--",
        "vpn.data",
        f"gateway={server},user={username},password-flags=0",
        "vpn.secrets",
        f"password={password}",
    ]
    ok, out = _run(cmd, timeout=15)
    if not ok:
        return {"ok": False, "error": f"nmcli add failed: {out}"}

    ok, out = _run(["nmcli", "connection", "up", "noc-l2tp"], timeout=30)
    if not ok:
        return {"ok": False, "error": f"nmcli up failed: {out}"}

    for _ in range(20):
        time.sleep(1)
        st = get_status()
        if st["status"] == "online":
            iface = st.get("interface", "ppp0")
            _add_routes(iface, auto_routes)
            return {"ok": True, "message": f"L2TP Connected via nmcli! IP: {st['endpoint']}", "status": st}

    return {"ok": False, "error": "Timeout nmcli: PPP interface tidak muncul."}


def l2tp_connect(server: str, username: str, password: str, auto_routes: str = "") -> dict:
    """Entry point connect — pilih mode terbaik yang tersedia."""
    if not server or not username or not password:
        return {"ok": False, "error": "server/username/password kosong"}

    _kill_existing()

    # Cek /dev/ppp — jika ada pakai xl2tpd
    if os.path.exists("/dev/ppp"):
        logger.info("[l2tp-agent] /dev/ppp ditemukan → pakai xl2tpd mode")
        return l2tp_connect_xl2tpd(server, username, password, auto_routes)

    # Coba mknod /dev/ppp
    ok_mknod, _ = _run(["mknod", "/dev/ppp", "c", "108", "0"], timeout=5)
    if ok_mknod:
        _run(["chmod", "666", "/dev/ppp"])
        logger.info("[l2tp-agent] /dev/ppp berhasil dibuat → pakai xl2tpd mode")
        return l2tp_connect_xl2tpd(server, username, password, auto_routes)

    # LXC tanpa /dev/ppp — coba NetworkManager
    ok_nm, _ = _run(["which", "nmcli"], timeout=3)
    if ok_nm:
        logger.info("[l2tp-agent] Pakai NetworkManager (nmcli) mode")
        result = l2tp_connect_nmcli(server, username, password, auto_routes)
        if result.get("ok"):
            return result
        logger.warning(f"[l2tp-agent] nmcli gagal: {result.get('error')}")

    # Semua mode gagal
    return {
        "ok": False,
        "error": (
            "L2TP gagal: /dev/ppp tidak bisa dibuat di LXC container ini dan NetworkManager tidak tersedia. "
            "Solusi: Tambahkan 'lxc.cgroup2.devices.allow = c 108:0 rwm' dan "
            "'lxc.mount.entry = /dev/ppp dev/ppp none bind,optional,create=file' "
            "ke file konfigurasi LXC di Proxmox host (/etc/pve/lxc/<ID>.conf), "
            "lalu restart container."
        )
    }


def l2tp_disconnect() -> dict:
    """Putus semua koneksi L2TP."""
    # Coba nmcli dulu
    _run(["nmcli", "connection", "down", "noc-l2tp"], timeout=10)
    _run(["nmcli", "connection", "delete", "noc-l2tp"], timeout=10)
    # Fallback kill
    _kill_existing()
    return {"ok": True, "message": "L2TP Disconnected"}


class AgentHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.debug(fmt, *args)

    def _json(self, data: dict, code: int = 200):
        body = json.dumps(data).encode()
        try:
            self.send_response(code)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def do_GET(self):
        if self.path == "/status":
            self._json(get_status())
        elif self.path == "/health":
            dev_ppp  = os.path.exists("/dev/ppp")
            ok_nm, _ = _run(["which", "nmcli"], timeout=3)
            ok_xl, _ = _run(["which", "xl2tpd"], timeout=3)
            self._json({
                "ok": True,
                "agent": "l2tp-agent",
                "version": "2.0",
                "dev_ppp": dev_ppp,
                "nmcli": ok_nm,
                "xl2tpd": ok_xl,
                "mode": "xl2tpd" if dev_ppp else ("nmcli" if ok_nm else "none"),
            })
        else:
            self._json({"error": "Not found"}, 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if self.path == "/disconnect":
            self._json(l2tp_disconnect())
            return

        if self.path == "/connect":
            try:
                data = json.loads(body)
            except Exception:
                self._json({"ok": False, "error": "Invalid JSON"}, 400)
                return

            result_holder = {}

            def do_connect():
                result_holder["result"] = l2tp_connect(
                    data.get("server", ""),
                    data.get("username", ""),
                    data.get("password", ""),
                    data.get("auto_routes", ""),
                )

            t = Thread(target=do_connect, daemon=True)
            t.start()
            t.join(timeout=45)   # xl2tpd butuh waktu lebih lama
            self._json(result_holder.get("result", {"ok": False, "error": "Connect Timeout (45s)"}))
            return

        self._json({"error": "Not found"}, 404)


if __name__ == "__main__":
    logger.info(f"NOC Monitoring Pro L2TP Agent v2.0 starting on {LISTEN_HOST}:{LISTEN_PORT}")
    dev_ppp = os.path.exists("/dev/ppp")
    logger.info(f"/dev/ppp: {'EXISTS ✓' if dev_ppp else 'NOT FOUND (will use nmcli/mknod fallback)'}")
    server = HTTPServer((LISTEN_HOST, LISTEN_PORT), AgentHandler)
    logger.info("L2TP Agent ready and listening.")
    server.serve_forever()
