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
    """Cek apakah container cloudflared sedang running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        status = result.stdout.strip()
        return bool(status and "Up" in status)
    except Exception:
        return False


def _container_exists() -> bool:
    """Cek apakah container cloudflared ada (running atau stopped)."""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


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
    """Restart container cloudflared (jika sudah dikonfigurasi)."""
    if not _container_exists():
        raise HTTPException(
            status_code=404,
            detail="Container cloudflared tidak ditemukan. Pastikan service cloudflared aktif di docker-compose.yml dan jalankan: docker compose up -d cloudflared"
        )

    try:
        result = subprocess.run(
            ["docker", "restart", CONTAINER_NAME],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Gagal restart: {result.stderr.strip()}")
        return {"status": "success", "message": f"Container {CONTAINER_NAME} berhasil direstart."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error restart container: {e}")


# ── POST /api/cloudflare/start ────────────────────────────────────────────
@router.post("/start")
async def start_cloudflared():
    """Start container cloudflared via docker compose."""
    try:
        compose_file = APP_HOST_DIR / "docker-compose.yml"
        cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "cloudflared"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Gagal start cloudflared: {result.stderr.strip()}")
        return {"status": "success", "message": "Cloudflare tunnel started."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


# ── POST /api/cloudflare/stop ─────────────────────────────────────────────
@router.post("/stop")
async def stop_cloudflared():
    """Stop container cloudflared."""
    if not _container_exists():
        raise HTTPException(status_code=404, detail="Container cloudflared tidak ditemukan.")
    try:
        result = subprocess.run(
            ["docker", "stop", CONTAINER_NAME],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Gagal stop: {result.stderr.strip()}")
        return {"status": "success", "message": "Cloudflare tunnel dihentikan."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
