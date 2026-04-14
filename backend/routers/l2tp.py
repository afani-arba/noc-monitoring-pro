"""
L2TP VPN API route.
Berkomunikasi dengan L2TP Agent yang berjalan di Ubuntu host via HTTP port 8002.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging
import os
import httpx as _httpx

from core.db import get_db
from core.auth import get_current_user, require_write
import core.l2tp_service as l2tp_svc

router = APIRouter(prefix="/l2tp", tags=["l2tp"])
logger = logging.getLogger(__name__)


class L2TPConfigSchema(BaseModel):
    server: str
    username: str
    password: str
    enabled: bool
    auto_routes: str = ""


@router.get("/config")
async def get_l2tp_config(user=Depends(get_current_user)):
    """Mengambil konfigurasi L2TP client system"""
    db = get_db()
    curr = await db.system_settings.find_one({"_id": "l2tp_config"})
    if not curr:
        return {"server": "", "username": "", "password": "", "enabled": False, "auto_routes": ""}
    return {
        "server": curr.get("server", ""),
        "username": curr.get("username", ""),
        "password": curr.get("password", ""),
        "enabled": curr.get("enabled", False),
        "auto_routes": curr.get("auto_routes", "")
    }


@router.put("/config")
async def update_l2tp_config(config: L2TPConfigSchema, user=Depends(require_write)):
    """Simpan config L2TP dan langsung connect ke agent di host."""
    db = get_db()

    if not config.server or not config.username or not config.password:
        raise HTTPException(status_code=400, detail="Server, Username dan Password harus diisi")

    # ── 1. Simpan konfigurasi ke DB terlebih dahulu (selalu) ─────────────────
    await db.system_settings.update_one(
        {"_id": "l2tp_config"},
        {"$set": {
            "server": config.server,
            "username": config.username,
            "password": config.password,
            "enabled": config.enabled,
            "auto_routes": config.auto_routes
        }},
        upsert=True
    )

    if not config.enabled:
        # Kirim perintah disconnect ke agent (best-effort, tidak mematikan app jika agent tidak ada)
        try:
            await l2tp_svc.l2tp_down()
        except Exception:
            pass
        return {"status": "success", "message": "Konfigurasi disimpan dan L2TP dinonaktifkan."}

    # ── 2. Coba sambungkan via agent ─────────────────────────────────────────
    ok, msg = await l2tp_svc.l2tp_up({
        "server": config.server,
        "username": config.username,
        "password": config.password,
        "auto_routes": config.auto_routes
    })

    if ok:
        return {"status": "success", "message": msg}

    # Agent gagal / belum terinstall:
    # Tandai config sebagai tidak aktif (disabled) agar status akurat
    await db.system_settings.update_one(
        {"_id": "l2tp_config"},
        {"$set": {"enabled": False}}
    )

    # Kembalikan HTTP 200 dengan status agent_error (bukan 500) agar frontend
    # dapat menampilkan pesan informatif tanpa crash atau generic error
    agent_url = os.environ.get("L2TP_AGENT_URL", "http://172.18.0.1:8002")
    return {
        "status": "agent_error",
        "message": msg,
        "hint": (
            f"L2TP Agent belum tersedia di {agent_url}. "
            "Jalankan perintah berikut di server Ubuntu host: "
            "cd vpn-agents/l2tp-agent && sudo bash install_l2tp_agent.sh"
        )
    }


@router.get("/status")
async def get_l2tp_status(user=Depends(get_current_user)):
    """Mengambil status interface L2TP dari agent di host."""
    db = get_db()
    curr = await db.system_settings.find_one({"_id": "l2tp_config"})
    if not curr or not curr.get("enabled", False):
        return {"status": "disabled", "message": "L2TP client tidak aktif."}

    result = await l2tp_svc.get_l2tp_status()
    if "error" in result:
        return {"status": "offline", "error": result["error"]}
    return result


@router.post("/disconnect")
async def disconnect_l2tp(user=Depends(require_write)):
    """Manual force stop L2TP VPN."""
    ok, msg = await l2tp_svc.l2tp_down()
    db = get_db()
    await db.system_settings.update_one({"_id": "l2tp_config"}, {"$set": {"enabled": False}})
    return {"status": "ok", "message": msg}


@router.get("/agent-health")
async def check_l2tp_agent():
    """Cek apakah L2TP Agent tersedia di host."""
    agent_url = os.environ.get("L2TP_AGENT_URL", "http://172.18.0.1:8002")
    try:
        async with _httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{agent_url}/health")
            data = r.json()
            return {"available": True, "agent_url": agent_url, **data}
    except Exception as e:
        return {"available": False, "agent_url": agent_url, "error": str(e)}
