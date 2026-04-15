"""
NOC-Monitoring-Pro — Cloudflare Tunnel Router
Mengelola konfigurasi token Cloudflare Tunnel dan status container cloudflared.
"""
import os
import subprocess
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cloudflare", tags=["cloudflare"])

# Lokasi file .env di direktori /app-host (mount dari host)
APP_HOST_DIR = Path("/app-host")
ENV_FILE     = APP_HOST_DIR / ".env"
BACKEND_ENV  = Path(__file__).parent.parent / ".env"

CONTAINER_NAME = "noc-monitoring-pro-cloudflared"


def _read_token_from_env() -> str:
    """Baca CLOUDFLARE_TUNNEL_TOKEN dari backend .env file."""
    env_path = BACKEND_ENV if BACKEND_ENV.exists() else None
    if not env_path:
        return ""
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _write_token_to_env(token: str) -> None:
    """Tulis / update CLOUDFLARE_TUNNEL_TOKEN di backend .env file."""
    env_path = BACKEND_ENV

    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()

    key = "CLOUDFLARE_TUNNEL_TOKEN"
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f'{key}="{token}"'
            updated = True
            break

    if not updated:
        lines.append(f'{key}="{token}"')

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("Cloudflare token updated in .env")


def _container_running() -> bool:
    """Cek apakah proses cloudflared sedang berjalan."""
    try:
        result = subprocess.run(["pgrep", "-x", "cloudflared"], capture_output=True)
        return result.returncode == 0
    except Exception:
        return False


def _container_exists() -> bool:
    """Sama dengan _container_running untuk backward compatibility."""
    return _container_running()


# ── GET /api/cloudflare/status ─────────────────────────────────────────────
@router.get("/status")
async def get_cloudflare_status():
    """Cek status Cloudflare tunnel (token ada, container running)."""
    token = _read_token_from_env()
    running = _container_running()
    exists  = _container_exists()

    # Masking token — tampilkan hanya 8 karakter pertama
    masked_token = (token[:8] + "..." + token[-4:]) if len(token) > 16 else ("****" if token else "")

    return {
        "configured": bool(token),
        "token_preview": masked_token,
        "container_running": running,
        "container_exists": exists,
        "status": "running" if running else ("stopped" if exists else "not_installed"),
        "container_name": CONTAINER_NAME,
    }


# ── PUT /api/cloudflare/config ─────────────────────────────────────────────
class CloudflareConfigPayload(BaseModel):
    token: str


@router.put("/config")
async def update_cloudflare_config(payload: CloudflareConfigPayload):
    """Simpan Cloudflare Tunnel Token ke file .env backend."""
    token = payload.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token tidak boleh kosong")

    try:
        _write_token_to_env(token)
    except Exception as e:
        logger.error(f"Failed to write cloudflare token: {e}")
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan token: {e}")

    return {
        "status": "success",
        "message": "Token Cloudflare berhasil disimpan. Aktifkan service cloudflared di docker-compose.yml lalu restart.",
    }


# ── POST /api/cloudflare/restart ───────────────────────────────────────────
@router.post("/restart")
async def restart_cloudflared():
    """Restart proses cloudflared."""
    try:
        # Hentikan dulu jika berjalan
        subprocess.run(["pkill", "-x", "cloudflared"], capture_output=True)
        
        token = _read_token_from_env()
        if not token:
            raise HTTPException(status_code=400, detail="Token tidak dikonfigurasi.")
            
        cmd = ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", token]
        # Jalankan di background (detached)
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        
        return {"status": "success", "message": "Proses cloudflared berhasil direstart."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restart cloudflared: {e}")


# ── POST /api/cloudflare/start ────────────────────────────────────────────
@router.post("/start")
async def start_cloudflared():
    """Start proses cloudflared via subprocess."""
    if _container_running():
        return {"status": "success", "message": "Cloudflare tunnel sudah berjalan."}
        
    try:
        token = _read_token_from_env()
        if not token:
            raise HTTPException(status_code=400, detail="Token belum dikonfigurasi. Simpan token dahulu.")
            
        cmd = ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", token]
        # Executing as a background daemon process
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setsid)
        
        return {"status": "success", "message": "Cloudflare tunnel started."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error start cloudflared: {e}")


# ── POST /api/cloudflare/stop ─────────────────────────────────────────────
@router.post("/stop")
async def stop_cloudflared():
    """Stop proses cloudflared."""
    if not _container_running():
        raise HTTPException(status_code=404, detail="Proses cloudflared tidak berjalan.")
    try:
        result = subprocess.run(["pkill", "-x", "cloudflared"], capture_output=True, text=True)
        return {"status": "success", "message": "Cloudflare tunnel dihentikan."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping cloudflared: {e}")

