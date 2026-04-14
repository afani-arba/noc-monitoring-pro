import os
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)

# ── L2TP Agent berjalan di HOST Ubuntu (port 8002) ───────────────────
# Docker gateway = 172.18.0.1 (default bridge)
AGENT_URL = os.environ.get("L2TP_AGENT_URL", "http://172.18.0.1:8002")
AGENT_TIMEOUT = 60.0

async def _agent_get(path: str) -> Dict[str, Any]:
    """Async HTTP GET ke L2TP Agent."""
    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.get(f"{AGENT_URL}{path}")
            return r.json()
    except httpx.ConnectError:
        logger.error(f"[L2TP] Agent tidak bisa dihubungi di {AGENT_URL}")
        return {"error": f"L2TP Agent tidak tersedia di {AGENT_URL}"}
    except Exception as e:
        logger.error(f"[L2TP] Agent error: {e}")
        return {"error": str(e)}

async def _agent_post(path: str, data: dict = None) -> Dict[str, Any]:
    """Async HTTP POST ke L2TP Agent."""
    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.post(f"{AGENT_URL}{path}", json=data or {})
            return r.json()
    except httpx.ConnectError:
        logger.error(f"[L2TP] Agent tidak bisa dihubungi di {AGENT_URL}")
        return {"ok": False, "error": f"L2TP Agent tidak tersedia di {AGENT_URL}"}
    except Exception as e:
        logger.error(f"[L2TP] Agent error POST {path}: {e}")
        return {"ok": False, "error": str(e)}

async def l2tp_up(config: dict) -> tuple[bool, str]:
    """Menyambungkan L2TP VPN via agent di host (Async)."""
    server = config.get("server", "").strip()
    username = config.get("username", "").strip()
    password = config.get("password", "").strip()

    if not server or not username or not password:
        return False, "L2TP Config tidak lengkap (server/username/password kosong)"

    logger.info(f"[L2TP] Mengirim perintah connect ke agent: {AGENT_URL}/connect")
    result = await _agent_post("/connect", {
        "server": server,
        "username": username,
        "password": password,
        "auto_routes": config.get("auto_routes", "")
    })

    if result.get("ok"):
        status = result.get("status", {})
        ip = status.get("endpoint", "")
        msg = result.get("message", "Connected")
        return True, f"{msg}" + (f" — IP: {ip}" if ip else "")
    else:
        err = result.get("error", "Gagal connect ke L2TP")
        return False, err

async def l2tp_down() -> tuple[bool, str]:
    """Mematikan L2TP VPN via agent (Async)."""
    result = await _agent_post("/disconnect")
    if result.get("ok"):
        return True, "L2TP Disconnected"
    return False, result.get("error", "Gagal disconnect")

async def get_l2tp_status() -> Dict[str, Any]:
    """Membaca status VPN dari agent di host (Async)."""
    default = {
        "status": "offline",
        "uptime": 0,
        "endpoint": "",
        "rx_bytes": 0,
        "tx_bytes": 0
    }
    result = await _agent_get("/status")
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
