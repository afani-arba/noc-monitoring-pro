"""
Daily Snapshot Service — Menyimpan ringkasan harian ke DB.

Snapshot disimpan sekali per hari ke koleksi 'daily_snapshots' (date-keyed).
Data yang disimpan:
  - total PPPoE secrets (semua yang terdaftar) per device
  - PPPoE active sessions per device
  - Hotspot users total
  - Hotspot active sessions
  - CPU avg, memory avg
  - Bandwidth avg (download/upload Mbps)

Report mingguan/bulanan menggunakan snapshot ini agar data historis akurat
tanpa harus query ulang ke MikroTik.

Background loop berjalan setiap 1 jam dan menyimpan snapshot harian (idempotent).
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from core.db import get_db
from mikrotik_api import get_api_client

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 3600   # cek setiap 1 jam
FETCH_TIMEOUT = 30                  # detik per device


async def _fetch_device_snapshot(device: dict) -> dict:
    """
    Ambil data snapshot dari satu device MikroTik.
    Return dict dengan semua counter yang dibutuhkan laporan.
    Gagal = return dict kosong (jangan crash loop).
    """
    dev_id   = device.get("id", "")
    dev_name = device.get("name", dev_id)

    result = {
        "device_id":      dev_id,
        "device_name":    dev_name,
        "ip_address":     device.get("ip_address", ""),
        "status":         device.get("status", "unknown"),
        "pppoe_total":    0,
        "pppoe_active":   device.get("pppoe_active", 0),   # dari DB cache
        "hotspot_total":  0,
        "hotspot_active": device.get("hotspot_active", 0),  # dari DB cache
        "cpu_load":       device.get("cpu_load", 0),
        "memory_usage":   device.get("memory_usage", 0),
    }

    if device.get("status") != "online":
        return result

    try:
        mt = get_api_client(device)

        # Query hanya pppoe_secrets (total) dan hotspot_users (total)
        # active sudah tersedia dari DB cache — lebih cepat
        fetch_results = await asyncio.gather(
            asyncio.wait_for(mt.list_pppoe_secrets(), timeout=FETCH_TIMEOUT),
            asyncio.wait_for(mt.list_hotspot_users(), timeout=FETCH_TIMEOUT),
            return_exceptions=True,
        )
        secrets_res, hs_users_res = fetch_results

        if isinstance(secrets_res, list):
            result["pppoe_total"] = len(secrets_res)
        if isinstance(hs_users_res, list):
            result["hotspot_total"] = len(hs_users_res)

    except Exception as e:
        logger.debug(f"[daily_snap] Failed to fetch {dev_name}: {e}")

    return result


async def take_daily_snapshot():
    """
    Ambil snapshot semua device dan simpan sebagai dokumen harian di DB.
    Idempotent: hanya simpan 1 snapshot per hari (upsert by date_str).
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    # gunakan WIB (UTC+7) agar snapshot cocok dengan hari kerja lokal
    now_local = now + timedelta(hours=7)
    date_str = now_local.strftime("%Y-%m-%d")

    # Cek apakah sudah ada snapshot hari ini
    existing = await db.daily_snapshots.find_one({"date": date_str})
    if existing:
        logger.debug(f"[daily_snap] Snapshot {date_str} sudah ada, skip.")
        return

    logger.info(f"[daily_snap] Mengambil snapshot harian: {date_str}")

    # Ambil semua device
    all_devs = await db.devices.find({}, {"_id": 0}).to_list(500)
    if not all_devs:
        logger.warning("[daily_snap] Tidak ada device ditemukan.")
        return

    # Fetch snapshot per device (paralel, max 10 concurrent)
    sem = asyncio.Semaphore(10)

    async def throttled(device):
        async with sem:
            return await _fetch_device_snapshot(device)

    device_snapshots = await asyncio.gather(
        *[throttled(d) for d in all_devs],
        return_exceptions=True,
    )

    # Filter result yang valid
    valid_snapshots = [
        s for s in device_snapshots
        if isinstance(s, dict) and s.get("device_id")
    ]

    # Hitung aggregate
    total_pppoe_total    = sum(s["pppoe_total"]    for s in valid_snapshots)
    total_pppoe_active   = sum(s["pppoe_active"]   for s in valid_snapshots)
    total_hotspot_total  = sum(s["hotspot_total"]  for s in valid_snapshots)
    total_hotspot_active = sum(s["hotspot_active"] for s in valid_snapshots)
    online_count = sum(1 for s in valid_snapshots if s["status"] == "online")

    # Rata2 CPU & memory dari device online
    online_snaps = [s for s in valid_snapshots if s["status"] == "online"]
    avg_cpu    = round(sum(s["cpu_load"]       for s in online_snaps) / max(len(online_snaps), 1), 1)
    avg_memory = round(sum(s["memory_usage"]   for s in online_snaps) / max(len(online_snaps), 1), 1)

    # Ambil average bandwidth dari traffic_history hari ini
    ts_start = (now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                - timedelta(hours=7)).isoformat()  # kembali ke UTC

    bw_pipeline = [
        {"$match": {"timestamp": {"$gte": ts_start}}},
        {"$project": {
            "pppoe_total":  {"$ifNull": ["$pppoe_total",  0]},
            "pppoe_active": {"$ifNull": ["$pppoe_active", 0]},
        }},
    ]

    # Ambil juga dari traffic_history untuk avg bandwidth
    th_docs = await db.traffic_history.find(
        {"timestamp": {"$gte": ts_start}},
        {"_id": 0, "bandwidth": 1, "isp_bandwidth": 1}
    ).to_list(5000)

    total_dl = total_ul = 0
    for doc in th_docs:
        isp_bw = doc.get("isp_bandwidth") or {}
        bw     = doc.get("bandwidth") or {}
        if isp_bw:
            for v in isp_bw.values():
                if isinstance(v, dict):
                    total_dl += v.get("download_bps", 0)
                    total_ul += v.get("upload_bps", 0)
        elif bw:
            for v in bw.values():
                if isinstance(v, dict):
                    total_dl += v.get("download_bps", 0)
                    total_ul += v.get("upload_bps", 0)

    doc_count = max(len(th_docs), 1)
    avg_dl_mbps = round(total_dl / doc_count / 1_000_000, 2)
    avg_ul_mbps = round(total_ul / doc_count / 1_000_000, 2)

    snapshot_doc = {
        "date":               date_str,
        "timestamp":          now.isoformat(),
        "devices_total":      len(valid_snapshots),
        "devices_online":     online_count,
        "pppoe_total":        total_pppoe_total,
        "pppoe_active":       total_pppoe_active,
        "hotspot_total":      total_hotspot_total,
        "hotspot_active":     total_hotspot_active,
        "avg_cpu":            avg_cpu,
        "avg_memory":         avg_memory,
        "avg_dl_mbps":        avg_dl_mbps,
        "avg_ul_mbps":        avg_ul_mbps,
        "device_details":     valid_snapshots,
    }

    await db.daily_snapshots.update_one(
        {"date": date_str},
        {"$set": snapshot_doc},
        upsert=True,
    )

    logger.info(
        f"[daily_snap] Snapshot {date_str} disimpan: "
        f"{len(valid_snapshots)} devices, "
        f"pppoe_total={total_pppoe_total}, pppoe_active={total_pppoe_active}, "
        f"hotspot_total={total_hotspot_total}"
    )


async def daily_snapshot_loop():
    """Background loop: cek dan ambil snapshot setiap SNAPSHOT_INTERVAL_SECONDS."""
    logger.info("[daily_snap] Service dimulai.")
    # Delay 30 detik saat startup agar semua service lain siap
    await asyncio.sleep(30)
    while True:
        try:
            await take_daily_snapshot()
        except Exception as e:
            logger.error(f"[daily_snap] Error: {e}")
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
