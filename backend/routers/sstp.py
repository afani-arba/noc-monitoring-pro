"""
SSTP VPN API route.
Berkomunikasi dengan SSTP Agent yang berjalan di LXC Ubuntu host via HTTP.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging
import os
import httpx as _httpx

from core.db import get_db
from core.auth import get_current_user, require_write

router = APIRouter(prefix="/sstp", tags=["sstp"])
logger = logging.getLogger(__name__)

# SSTP Agent berjalan di HOST Ubuntu LXC — Docker bridge gateway = 172.18.0.1
AGENT_URL = os.environ.get("SSTP_AGENT_URL", "http://172.18.0.1:8001")
AGENT_TIMEOUT = 15.0


class SSTPConfigSchema(BaseModel):
    server: str
    username: str
    password: str
    enabled: bool


async def _agent_get(path: str) -> dict:
    """Async GET ke SSTP Agent di host."""
    try:
        async with _httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.get(f"{AGENT_URL}{path}")
            return r.json()
    except _httpx.ConnectError:
        return {"error": f"SSTP Agent tidak tersedia di {AGENT_URL}. Jalankan: systemctl start sstp-agent di LXC host"}
    except Exception as e:
        return {"error": str(e)}


async def _agent_post(path: str, data: dict = None) -> dict:
    """Async POST ke SSTP Agent di host."""
    try:
        async with _httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.post(f"{AGENT_URL}{path}", json=data or {})
            return r.json()
    except _httpx.ConnectError:
        return {"ok": False, "error": f"SSTP Agent tidak tersedia di {AGENT_URL}. Jalankan: systemctl start sstp-agent"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/config")
async def get_sstp_config(user=Depends(get_current_user)):
    """Mengambil konfigurasi SSTP client system"""
    db = get_db()
    curr = await db.system_settings.find_one({"_id": "sstp_config"})
    if not curr:
        return {"server": "", "username": "", "password": "", "enabled": False}
    return {
        "server": curr.get("server", ""),
        "username": curr.get("username", ""),
        "password": curr.get("password", ""),
        "enabled": curr.get("enabled", False)
    }


@router.put("/config")
async def update_sstp_config(config: SSTPConfigSchema, user=Depends(require_write)):
    """Simpan config SSTP dan langsung connect ke agent di host."""
    db = get_db()

    if not config.server or not config.username or not config.password:
        raise HTTPException(status_code=400, detail="Server, Username dan Password harus diisi")

    # ── 1. Simpan konfigurasi ke DB terlebih dahulu (selalu) ─────────────────
    await db.system_settings.update_one(
        {"_id": "sstp_config"},
        {"$set": {
            "server": config.server,
            "username": config.username,
            "password": config.password,
            "enabled": config.enabled
        }},
        upsert=True
    )

    if not config.enabled:
        # Kirim perintah disconnect ke agent (best-effort)
        try:
            await _agent_post("/disconnect")
        except Exception:
            pass
        return {"status": "success", "message": "Konfigurasi disimpan dan SSTP dinonaktifkan."}

    # ── 2. Coba sambungkan via agent ─────────────────────────────────────────
    result = await _agent_post("/connect", {
        "server": config.server,
        "username": config.username,
        "password": config.password
    })

    if result.get("ok"):
        msg = result.get("message", "SSTP Connected")
        return {"status": "success", "message": msg}

    # Agent gagal / belum terinstall:
    # Tandai config sebagai tidak aktif agar status akurat
    await db.system_settings.update_one(
        {"_id": "sstp_config"},
        {"$set": {"enabled": False}}
    )

    err = result.get("error", "Gagal connect SSTP")
    return {
        "status": "agent_error",
        "message": err,
        "hint": (
            f"SSTP Agent belum tersedia di {AGENT_URL}. "
            "Jalankan perintah berikut di server Ubuntu host: "
            "cd vpn-agents/sstp-agent && sudo bash install_sstp_agent.sh"
        )
    }


@router.get("/status")
async def get_sstp_status(user=Depends(get_current_user)):
    """Mengambil status interface SSTP dari agent di host."""
    db = get_db()
    curr = await db.system_settings.find_one({"_id": "sstp_config"})
    if not curr or not curr.get("enabled", False):
        return {"status": "disabled", "message": "SSTP client tidak aktif."}

    result = await _agent_get("/status")
    if "error" in result:
        return {"status": "offline", "error": result["error"]}
    return result


@router.post("/disconnect")
async def disconnect_sstp(user=Depends(require_write)):
    """Manual force stop SSTP VPN."""
    result = await _agent_post("/disconnect")
    db = get_db()
    await db.system_settings.update_one({"_id": "sstp_config"}, {"$set": {"enabled": False}})
    return {"status": "ok", "message": result.get("message", "Disconnected")}


@router.get("/agent-health")
async def check_sstp_agent():
    """Cek apakah SSTP Agent tersedia di host."""
    result = await _agent_get("/health")
    if "error" in result:
        return {"available": False, "error": result["error"], "agent_url": AGENT_URL}
    return {"available": True, "agent_url": AGENT_URL, **result}
