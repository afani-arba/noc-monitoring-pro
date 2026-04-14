"""
L2TP VPN API route.
Berkomunikasi dengan L2TP Agent yang berjalan di Ubuntu host via HTTP port 8002.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging
import os
import httpx

from core.db import get_db
from core.auth import get_current_user, require_write
# Import service yang baru dibuat
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
    curr = await db.settings.find_one({"_id": "l2tp_config"})
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

    # Simpan ke DB
    await db.settings.update_one(
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

    if config.enabled:
        # Kirim perintah connect ke L2TP Agent di host via service
        ok, msg = await l2tp_svc.l2tp_up({
            "server": config.server,
            "username": config.username,
            "password": config.password,
            "auto_routes": config.auto_routes
        })
        if not ok:
            raise HTTPException(status_code=500, detail=msg)
        return {"status": "success", "message": msg}
    else:
        # Kirim perintah disconnect ke agent
        ok, msg = await l2tp_svc.l2tp_down()
        return {"status": "success", "message": "Konfigurasi disimpan dan L2TP dinonaktifkan."}

@router.get("/status")
async def get_l2tp_status(user=Depends(get_current_user)):
    """Mengambil status interface L2TP dari agent di host."""
    db = get_db()
    curr = await db.settings.find_one({"_id": "l2tp_config"})
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
    # Update DB agar enabled=false juga
    db = get_db()
    await db.settings.update_one({"_id": "l2tp_config"}, {"$set": {"enabled": False}})
    return {"status": "ok", "message": msg}
