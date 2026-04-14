import os
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── SSTP Agent berjalan di HOST Ubuntu LXC (di luar Docker) ──────────────────
# Docker backend memanggil agent via HTTP pada bridge gateway.
# 172.18.0.1 = IP host dari dalam bridge network Docker (docker gateway).
# Agent listen di 0.0.0.0:8001 di host → bisa diakses dari container.
AGENT_URL = os.environ.get("SSTP_AGENT_URL", "http://172.18.0.1:8001")
AGENT_TIMEOUT = 60.0  # detik


def _agent_get(path: str) -> Dict[str, Any]:
    """HTTP GET ke SSTP Agent."""
    try:
        r = httpx.get(f"{AGENT_URL}{path}", timeout=AGENT_TIMEOUT)
        return r.json()
    except httpx.ConnectError:
        logger.error(f"[SSTP] Agent tidak bisa dihubungi di {AGENT_URL} — pastikan sstp-agent service running di LXC host")
        return {"error": f"SSTP Agent tidak tersedia. Jalankan: systemctl start sstp-agent di LXC host"}
    except Exception as e:
        logger.error(f"[SSTP] Agent error: {e}")
        return {"error": str(e)}


def _agent_post(path: str, data: dict = None) -> Dict[str, Any]:
    """HTTP POST ke SSTP Agent."""
    try:
        r = httpx.post(f"{AGENT_URL}{path}", json=data or {}, timeout=AGENT_TIMEOUT)
        return r.json()
    except httpx.ConnectError:
        logger.error(f"[SSTP] Agent tidak bisa dihubungi di {AGENT_URL}")
        return {"ok": False, "error": f"SSTP Agent tidak tersedia di {AGENT_URL}. Jalankan: systemctl start sstp-agent"}
    except Exception as e:
        logger.error(f"[SSTP] Agent error POST {path}: {e}")
        return {"ok": False, "error": str(e)}


def sstp_up(config: dict) -> tuple[bool, str]:
    """
    Menyambungkan SSTP VPN via agent di Ubuntu LXC host.
    Agent (sstp_agent.py) yang berjalan di HOST menjalankan sstpc secara native.
    """
    server = config.get("server", "").strip()
    username = config.get("username", "").strip()
    password = config.get("password", "").strip()

    if not server or not username or not password:
        return False, "SSTP Config tidak lengkap (server/username/password kosong)"

    logger.info(f"[SSTP] Mengirim perintah connect ke agent: {AGENT_URL}/connect")
    result = _agent_post("/connect", {
        "server": server,
        "username": username,
        "password": password
    })

    if result.get("ok"):
        status = result.get("status", {})
        ip = status.get("endpoint", "")
        msg = result.get("message", "Connected")
        return True, f"{msg}" + (f" — IP: {ip}" if ip else "")
    else:
        err = result.get("error", "Gagal connect ke SSTP")
        return False, err


def sstp_down() -> tuple[bool, str]:
    """Mematikan SSTP VPN via agent."""
    result = _agent_post("/disconnect")
    if result.get("ok"):
        return True, "SSTP Disconnected"
    return False, result.get("error", "Gagal disconnect")


def get_sstp_status() -> Dict[str, Any]:
    """
    Membaca status VPN dari agent di HOST.
    Agent membaca /sys/class/net/VPN yang hanya ada di network namespace host.
    """
    default = {
        "status": "offline",
        "uptime": 0,
        "endpoint": "",
        "rx_bytes": 0,
        "tx_bytes": 0
    }

    result = _agent_get("/status")
    if "error" in result:
        default["error"] = result["error"]
        return default

    return {
        "status": result.get("status", "offline"),
        "endpoint": result.get("endpoint", ""),
        "rx_bytes": result.get("rx_bytes", 0),
        "tx_bytes": result.get("tx_bytes", 0),
        "uptime": result.get("uptime", 0),
    }


def check_agent_health() -> Dict[str, Any]:
    """Cek apakah SSTP Agent tersedia di host."""
    result = _agent_get("/health")
    if "error" in result:
        return {"available": False, "error": result["error"]}
    return {"available": True, **result}
