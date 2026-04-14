"""
SSTP VPN API route.
Berkomunikasi dengan SSTP Agent yang berjalan di LXC Ubuntu host via HTTP.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import os
import httpx

from core.db import get_db

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
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.get(f"{AGENT_URL}{path}")
            return r.json()
    except httpx.ConnectError:
        return {"error": f"SSTP Agent tidak tersedia di {AGENT_URL}. Jalankan: systemctl start sstp-agent di LXC host"}
    except Exception as e:
        return {"error": str(e)}


async def _agent_post(path: str, data: dict = None) -> dict:
    """Async POST ke SSTP Agent di host."""
    try:
        async with httpx.AsyncClient(timeout=AGENT_TIMEOUT) as client:
            r = await client.post(f"{AGENT_URL}{path}", json=data or {})
            return r.json()
    except httpx.ConnectError:
        return {"ok": False, "error": f"SSTP Agent tidak tersedia di {AGENT_URL}. Jalankan: systemctl start sstp-agent"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/config")
async def get_sstp_config():
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
async def update_sstp_config(config: SSTPConfigSchema):
    """Simpan config SSTP dan langsung connect ke agent di host."""
    db = get_db()

    if not config.server or not config.username or not config.password:
        raise HTTPException(status_code=400, detail="Server, Username dan Password harus diisi")

    # Simpan ke DB
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

    if config.enabled:
        # Kirim perintah connect ke SSTP Agent di host
        result = await _agent_post("/connect", {
            "server": config.server,
            "username": config.username,
            "password": config.password
        })
        if not result.get("ok"):
            err = result.get("error", "Gagal connect SSTP")
            raise HTTPException(status_code=500, detail=err)
        msg = result.get("message", "SSTP Connected")
        return {"status": "success", "message": msg}
    else:
        # Kirim perintah disconnect ke agent
        result = await _agent_post("/disconnect")
        return {"status": "success", "message": "Konfigurasi disimpan dan SSTP dinonaktifkan."}


@router.get("/status")
async def get_sstp_status():
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
async def disconnect_sstp():
    """Manual force stop SSTP VPN."""
    result = await _agent_post("/disconnect")
    # Update DB agar enabled=false juga
    db = get_db()
    await db.system_settings.update_one({"_id": "sstp_config"}, {"$set": {"enabled": False}})
    return {"status": "ok", "message": result.get("message", "Disconnected")}


@router.get("/agent-health")
async def check_agent():
    """Cek apakah SSTP Agent tersedia di host."""
    result = await _agent_get("/health")
    if "error" in result:
        return {"available": False, "error": result["error"], "agent_url": AGENT_URL}
    return {"available": True, "agent_url": AGENT_URL, **result}
