"""
NOC Sentinel — Network Tools Router
=====================================
Endpoint untuk diagnostik jaringan real-time:
  - Ping (streaming SSE, 1 host)
  - Bulk Ping Sweep (semua device dengan bgp/snmp monitoring)
  - Traceroute
"""

import asyncio
import os
import re
import json
import shutil
import platform
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from core.db import get_db
from core.auth import get_current_user, decode_token

router = APIRouter(prefix="/network-tools", tags=["network-tools"])


# ── Helper: parse 1 baris output ping ────────────────────────────────────────
def _parse_ping_line(line: str) -> dict | None:
    """
    Parse output dari ping Linux/Windows ke dict terstandarisasi.
    Return None jika bukan baris data.
    """
    line = line.strip()
    if not line:
        return None

    # Linux: "64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=12.3 ms"
    # Or with domain: "64 bytes from sf-in-f100.1e100.net (74.125.24.100): icmp_seq=1 ttl=118 time=12.3 ms"
    m = re.search(
        r"(\d+)\s+bytes from\s+([^:]+):?.*?icmp_seq=(\d+).*?ttl=(\d+).*?time=([\d.]+)\s*ms",
        line
    )
    if m:
        return {
            "type": "reply",
            "bytes": int(m.group(1)),
            "from": m.group(2).strip(),
            "seq": int(m.group(3)),
            "ttl": int(m.group(4)),
            "rtt": float(m.group(5)),
            "raw": line,
        }

    # Request timeout
    if "Request timeout" in line or "no answer" in line.lower() or "Destination Host Unreachable" in line:
        seq_m = re.search(r"icmp_seq[= ](\d+)", line)
        return {
            "type": "timeout",
            "seq": int(seq_m.group(1)) if seq_m else 0,
            "rtt": None,
            "raw": line,
        }

    # Summary line: "5 packets transmitted, 5 received, 0% packet loss"
    m_sum = re.search(r"(\d+) packets? transmitted,\s*(\d+) received.*?([\d.]+)% packet loss", line)
    if m_sum:
        return {
            "type": "summary",
            "transmitted": int(m_sum.group(1)),
            "received": int(m_sum.group(2)),
            "loss_pct": float(m_sum.group(3)),
            "raw": line,
        }

    # RTT stats: "round-trip min/avg/max/stddev = 11.9/12.5/13.4/0.6 ms"
    m_rtt = re.search(r"(min|rtt).*?([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms", line)
    if m_rtt:
        return {
            "type": "rtt_stats",
            "min": float(m_rtt.group(2)),
            "avg": float(m_rtt.group(3)),
            "max": float(m_rtt.group(4)),
            "mdev": float(m_rtt.group(5)),
            "raw": line,
        }

    # Windows reply: "Reply from 8.8.8.8: bytes=32 time=14ms TTL=118"
    m_win = re.search(r"Reply from ([\d.]+).*?time[=<]([\d]+)ms.*?TTL=(\d+)", line, re.IGNORECASE)
    if m_win:
        return {
            "type": "reply",
            "bytes": 32,
            "from": m_win.group(1),
            "seq": 0,
            "ttl": int(m_win.group(3)),
            "rtt": float(m_win.group(2)),
            "raw": line,
        }

    # Generic interesting lines
    if any(kw in line.lower() for kw in ["ping", "connect", "network", "unreachable", "unknown", "error"]):
        return {"type": "info", "raw": line}

    return None


# ── SSE streaming ping ────────────────────────────────────────────────────────
async def _stream_ping(host: str, count: int, interval: float, size: int):
    """
    Async generator untuk streaming output ping sebagai Server-Sent Events.
    Tiap event adalah JSON dengan format yang konsisten.
    """
    # Validasi host
    host = host.strip()
    if not host or len(host) > 253:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Host tidak valid'})}\n\n"
        return

    # Bangun perintah ping: Linux/macOS
    is_win = platform.system().lower() == "windows"
    if is_win:
        cmd = ["ping", "-n", str(count), "-l", str(size), host]
    else:
        cmd = ["ping", "-c", str(count), "-i", str(interval), "-s", str(size), host]

    # Kirim event "start"
    yield f"data: {json.dumps({'type': 'start', 'host': host, 'count': count, 'size': size, 'ts': datetime.now(timezone.utc).isoformat()})}\n\n"

    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )

        replies = []
        async for raw_bytes in proc.stdout:
            line = raw_bytes.decode("utf-8", errors="replace").rstrip()
            parsed = _parse_ping_line(line)
            if parsed:
                if parsed["type"] == "reply":
                    replies.append(parsed["rtt"])
                parsed["ts"] = datetime.now(timezone.utc).isoformat()
                yield f"data: {json.dumps(parsed)}\n\n"
            elif line.strip():
                yield f"data: {json.dumps({'type': 'raw', 'raw': line})}\n\n"

        await proc.wait()

        # Kirim event "done" dengan statistik final
        if replies:
            yield f"data: {json.dumps({'type': 'done', 'success': True, 'stats': {'min': round(min(replies), 2), 'max': round(max(replies), 2), 'avg': round(sum(replies)/len(replies), 2), 'count': len(replies)}})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'success': False, 'stats': None})}\n\n"

    except FileNotFoundError:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Binary ping tidak ditemukan di sistem'})}\n\n"
    except asyncio.CancelledError:
        yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


# ── Endpoint: streaming ping ──────────────────────────────────────────────────
@router.get("/ping/stream")
async def ping_stream(
    host: str = Query(..., description="Hostname atau IP address"),
    count: int = Query(default=10, ge=1, le=100),
    interval: float = Query(default=1.0, ge=0.2, le=10.0),
    size: int = Query(default=56, ge=8, le=1400),
    token: Optional[str] = Query(None, description="Auth token via query untuk SSE"),
):
    """
    Streaming ping via Server-Sent Events (SSE).
    Frontend membuka EventSource ke endpoint ini dan menerima data real-time.
    """
    user = decode_token(token) if token else None
    if not user:
        # Kembalikan JSON error stream langsung untuk menutup EventSource di frontend
        async def unauthorized_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Unauthorized'})}\n\n"
        return StreamingResponse(unauthorized_stream(), media_type="text/event-stream")

    return StreamingResponse(
        _stream_ping(host, count, interval, size),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


# ── Endpoint: bulk device ping sweep ─────────────────────────────────────────
@router.get("/ping/bulk")
async def ping_bulk(
    user=Depends(get_current_user),
):
    """
    Ping semua device yang terdaftar di database secara paralel.
    Cocok untuk NOC sweep: langsung tahu device mana yang down.
    """
    db = get_db()
    devices = await db.devices.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "ip_address": 1}
    ).to_list(None)

    if not devices:
        return {"results": [], "message": "Tidak ada device terdaftar"}

    async def ping_one(dev: dict) -> dict:
        """Ping 1 device: kirim 3 paket, timeout 2 detik."""
        ip = dev.get("ip_address", "").split(":")[0].strip()
        if not ip:
            return {**dev, "status": "error", "rtt": None, "loss": 100}

        is_win = platform.system().lower() == "windows"
        if is_win:
            cmd = ["ping", "-n", "3", "-w", "2000", ip]
        else:
            cmd = ["ping", "-c", "3", "-W", "2", "-q", ip]

        try:
            env = os.environ.copy()
            env["LC_ALL"] = "C"
            env["LANG"] = "C"

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            output = stdout.decode("utf-8", errors="replace")

            # Parse packet loss
            loss_m = re.search(r"([\d.]+)% packet loss", output)
            loss = float(loss_m.group(1)) if loss_m else 100.0

            # Parse RTT avg
            rtt_m = re.search(r"([\d.]+)/([\d.]+)/([\d.]+)", output)
            rtt = round(float(rtt_m.group(2)), 2) if rtt_m else None

            return {
                **dev,
                "ip": ip,
                "status": "up" if loss < 100 else "down",
                "loss_pct": loss,
                "rtt_avg": rtt,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        except asyncio.TimeoutError:
            return {**dev, "ip": ip, "status": "timeout", "rtt_avg": None, "loss_pct": 100}
        except Exception as e:
            return {**dev, "ip": ip, "status": "error", "rtt_avg": None, "loss_pct": 100, "error": str(e)}

    # Jalankan semua ping secara paralel (max 30 concurrent untuk tidak overload)
    semaphore = asyncio.Semaphore(30)

    async def ping_with_sem(dev):
        async with semaphore:
            return await ping_one(dev)

    results = await asyncio.gather(*[ping_with_sem(d) for d in devices])

    up_count   = sum(1 for r in results if r.get("status") == "up")
    down_count = sum(1 for r in results if r.get("status") == "down")

    return {
        "results": sorted(results, key=lambda r: (r.get("status") != "down", r.get("rtt_avg") or 9999)),
        "summary": {
            "total": len(results),
            "up": up_count,
            "down": down_count,
            "loss_pct": round((down_count / len(results)) * 100, 1) if results else 0,
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ── Model: single ping request (non-streaming fallback) ──────────────────────
class PingRequest(BaseModel):
    host: str
    count: int = 5
    size: int = 56

@router.post("/ping")
async def ping_single(payload: PingRequest, user=Depends(get_current_user)):
    """
    Ping non-streaming: tunggu selesai dan kembalikan statistik ringkas.
    Digunakan untuk ping cepat dari modal device action.
    """
    host = payload.host.strip()
    if not host:
        raise HTTPException(status_code=400, detail="Host tidak boleh kosong")

    is_win = platform.system().lower() == "windows"
    if is_win:
        cmd = ["ping", "-n", str(payload.count), "-l", str(payload.size), host]
    else:
        cmd = ["ping", "-c", str(payload.count), "-i", "0.5", "-s", str(payload.size), "-q", host]

    try:
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30.0)
        output = stdout.decode("utf-8", errors="replace")

        loss_m = re.search(r"([\d.]+)% packet loss", output)
        loss = float(loss_m.group(1)) if loss_m else 100.0

        rtt_m = re.search(r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms", output)
        rtt_stats = None
        if rtt_m:
            rtt_stats = {
                "min": float(rtt_m.group(1)),
                "avg": float(rtt_m.group(2)),
                "max": float(rtt_m.group(3)),
                "mdev": float(rtt_m.group(4)),
            }

        tx_m = re.search(r"(\d+) packets? transmitted,\s*(\d+) received", output)

        return {
            "host": host,
            "status": "up" if loss < 100 else "down",
            "loss_pct": loss,
            "rtt": rtt_stats,
            "transmitted": int(tx_m.group(1)) if tx_m else payload.count,
            "received": int(tx_m.group(2)) if tx_m else 0,
            "raw_output": output[-500:],
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Ping timeout — host tidak merespons")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
