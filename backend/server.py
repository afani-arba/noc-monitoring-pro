"""
NOC-Monitoring-Pro Backend — Entry Point

Edition : MONITORING PRO (Network Monitoring tanpa Billing)
Features:
  1.  Dashboard Interface
  2.  Device Management
  3.  Wall Display
  4.  Data Report
  5.  Device Hub (Topology + Ping Tool)
  6.  SLA Monitor
  7.  Incident Management
  8.  Backup Config
  9.  Notifikasi System
  10. Pengaturan Platform
  11. User Management
  12. Update Aplikasi
  13. Lisensi Sistem

Router TIDAK disertakan (monitoring only):
  - PPPoE / Hotspot Billing
  - GenieACS / ZTP
  - Peering Eye / BGP Steering
  - CS Command Center
  - Client Portal
  - Finance Report
  - RADIUS Server
"""
import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from core.db import init_db
init_db()

# ── Routers ────────────────────────────────────────────────────────────────
from fastapi import APIRouter
from routers.auth import router as auth_router
from routers.devices import router as devices_router
from routers.metrics import router as metrics_router
from routers.events import router as events_router
from routers.wallboard import router as wallboard_router
from routers.reports import router as reports_router
from routers.topology import router as topology_router
from routers.network_tools import router as network_tools_router
from routers.sla import router as sla_router
from routers.incidents import router as incidents_router
from routers.backups import router as backups_router
from routers.notifications import router as notifications_router
from routers.system import router as system_router
from routers.admin import router as admin_router
from routers.license import router as license_router
from routers.speedtest import router as speedtest_router
from routers.routing_alerts import router as routing_alerts_router
from routers.syslog import router as syslog_router
from routers.audit import router as audit_router
from routers.scheduler import router as scheduler_router
from routers.sstp import router as sstp_router
from routers.l2tp import router as l2tp_router
_background_tasks: list = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 65)
    logger.info("  🖥️   NOC-Monitoring-Pro v1.0 — Starting up")
    logger.info("       Edition  : MONITORING PRO")
    logger.info("       Billing  : DISABLED")
    logger.info("       Focus    : Network Monitoring + SLA + Incident")
    logger.info("=" * 65)

    # DB Indexes
    try:
        from core.db import get_db
        db = get_db()
        await db.traffic_history.create_index([("device_id", 1), ("timestamp", -1)], background=True)
        await db.traffic_history.create_index([("timestamp", -1)], background=True)
        await db.traffic_snapshots.create_index([("device_id", 1)], background=True)
        await db.devices.create_index([("id", 1)], unique=True, background=True)
        await db.sla_records.create_index([("device_id", 1), ("timestamp", -1)], background=True)
        await db.incidents.create_index([("device_id", 1), ("created_at", -1)], background=True)
        logger.info("MongoDB indexes verified.")

        # Ensure default admin user exists
        admin_count = await db.admin_users.count_documents({"username": "admin"})
        if admin_count == 0:
            from core.auth import pwd_context
            import uuid
            default_admin = {
                "id": str(uuid.uuid4()),
                "username": "admin",
                "password": pwd_context.hash("admin123"),
                "full_name": "Administrator",
                "role": "administrator",
                "is_active": True,
            }
            await db.admin_users.insert_one(default_admin)
            logger.info("✅ Default admin user created (admin / admin123)")

    except Exception as e:
        logger.error(f"DB init error: {e}")

    # TTL Indexes
    try:
        from core.db import get_db
        db = get_db()
        await db.audit_logs.create_index([("timestamp", 1)], expireAfterSeconds=7_776_000, background=True, name="ttl_audit_90d")
        await db.syslog_logs.create_index([("timestamp", 1)], expireAfterSeconds=5_184_000, background=True, name="ttl_syslog_60d")
        await db.traffic_history.create_index([("timestamp", 1)], expireAfterSeconds=604_800, background=True, name="ttl_traffic_7d")
    except Exception as e:
        logger.error(f"TTL index error: {e}")

    def _svc(key: str, default: str = "true") -> bool:
        return os.environ.get(key, default).lower() == "true"

    # Ping scanner / polling
    if _svc("ENABLE_POLLING"):
        from core.polling import polling_loop
        t = asyncio.create_task(polling_loop())
        _background_tasks.append(t)
        logger.info("Ping scanner started")

    # SSE event poller
    if _svc("ENABLE_SSE"):
        from routers.events import start_poller
        t = start_poller()
        _background_tasks.append(t)
        logger.info("SSE event poller started")

    # Syslog UDP
    loop = asyncio.get_running_loop()
    if _svc("ENABLE_SYSLOG"):
        from syslog_server import start_syslog_server
        ts = await start_syslog_server(loop)
        if ts:
            _background_tasks.extend(ts)

    # Auto backup
    if _svc("ENABLE_BACKUP"):
        from services.backup_service import auto_backup_loop
        t = asyncio.create_task(auto_backup_loop())
        _background_tasks.append(t)
        logger.info("Auto backup scheduler started")

    # Firebase
    try:
        from services.firebase_service import initialize_firebase
        if initialize_firebase():
            logger.info("Firebase: OK")
        else:
            logger.warning("Firebase: credentials not found")
    except Exception as e:
        logger.error(f"Firebase init error: {e}")

    # Routing alerts (BGP/OSPF monitor)
    if _svc("ENABLE_ROUTING_ALERTS"):
        from services.routing_alert_service import bgp_ospf_alert_loop
        t = asyncio.create_task(bgp_ospf_alert_loop())
        _background_tasks.append(t)
        logger.info("BGP/OSPF alert monitor started")

    # SNMP Poller
    if _svc("ENABLE_SNMP_POLLER"):
        try:
            from core.snmp_poller import start_snmp_poller
            t = asyncio.create_task(start_snmp_poller())
            _background_tasks.append(t)
            logger.info("SNMP Poller started")
        except Exception as e:
            logger.error(f"SNMP Poller error: {e}")

    # Speedtest
    if _svc("ENABLE_SPEEDTEST"):
        from services.speedtest_service import speedtest_loop
        t = asyncio.create_task(speedtest_loop())
        _background_tasks.append(t)
        logger.info("Speedtest scheduler started")

    # Session cache
    if _svc("ENABLE_SESSION_CACHE"):
        from services.session_cache_service import session_cache_loop
        t = asyncio.create_task(session_cache_loop())
        _background_tasks.append(t)
        logger.info("Session cache started")

    # License verification
    from services.license_service import license_check_loop
    t = asyncio.create_task(license_check_loop())
    _background_tasks.append(t)
    logger.info("License verification started")

    logger.info("✅ NOC-Monitoring-Pro READY!")

    yield

    logger.info("NOC-Monitoring-Pro shutting down...")
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    if _background_tasks:
        await asyncio.gather(*_background_tasks, return_exceptions=True)
    from core.db import close_db
    close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="NOC-Monitoring-Pro API",
    version="1.0.0",
    description="NOC Monitoring Pro — Dashboard + Device + SLA + Incident + Wall Display",
    lifespan=lifespan
)

# CORS
_cors_origins_raw = os.environ.get("CORS_ORIGINS", "").strip()
if _cors_origins_raw and _cors_origins_raw != "*":
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    _allow_credentials = True
else:
    _cors_origins = ["*"]
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_credentials,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# License middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from core.db import get_db

@app.middleware("http")
async def license_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        allowed = [
            "/api/auth/", "/api/system/license", "/api/syslog/",
            "/api/devices/events", "/api/edition", "/api/system/info",
        ]
        if not any(path.startswith(p) for p in allowed):
            try:
                db = get_db()
                if db is not None:
                    status_doc = await db.system_settings.find_one({"_id": "license_status"})
                    if (status_doc or {}).get("status") != "valid":
                        msg = (status_doc or {}).get("message", "Unlicensed")
                        return JSONResponse(status_code=403, content={"detail": f"License Error: {msg}"})
            except Exception:
                pass
    return await call_next(request)


# ── API Router ─────────────────────────────────────────────────────────────
api = APIRouter(prefix="/api")

@api.get("/edition", tags=["system"])
async def get_edition_info():
    return {
        "edition": "pro",
        "edition_name": "NOC-Monitoring-Pro",
        "is_enterprise": False,
        "is_pro": True,
        "features": {
            "dashboard": True,
            "device": True,
            "wall_display": True,
            "data_report": True,
            "device_hub": True,
            "topology": True,
            "ping_tool": True,
            "sla": True,
            "incidents": True,
            "backup": True,
            "notifications": True,
            "settings": True,
            "user_management": True,
            "update": True,
            "license": True,
        },
        "disabled_features": [
            "billing", "hotspot", "pppoe", "genieacs",
            "peering_eye", "bgp_steering", "client_portal",
            "cs_command_center", "finance_report", "radius"
        ],
        "billing_enabled": False,
        "version": "1.0.0",
    }


# ── Auth ──────────────────────────────────────────────────────────────────
api.include_router(auth_router)

# ── 1. Dashboard Interface ────────────────────────────────────────────────
api.include_router(metrics_router)
api.include_router(events_router)            # SSE real-time events
api.include_router(speedtest_router)
api.include_router(wallboard_router)         # Wall Display data

# ── 2. Device Management ──────────────────────────────────────────────────
api.include_router(devices_router)

# ── 3. Wall Display ───────────────────────────────────────────────────────
# (wallboard_router & events_router sudah termasuk di atas)

# ── 4. Data Report ────────────────────────────────────────────────────────
api.include_router(reports_router)

# ── 5. Device Hub (Topology + Ping Tool) ─────────────────────────────────
api.include_router(topology_router)
api.include_router(network_tools_router)

# ── 6. SLA Monitor ────────────────────────────────────────────────────────
api.include_router(sla_router)

# ── 7. Incident Management ────────────────────────────────────────────────
api.include_router(incidents_router)

# ── 8. Backup Config ──────────────────────────────────────────────────────
api.include_router(backups_router)

# ── 9. Notifikasi System ──────────────────────────────────────────────────
api.include_router(notifications_router)

# ── 10. Pengaturan Platform ───────────────────────────────────────────────
api.include_router(system_router)

# ── 11. User Management ───────────────────────────────────────────────────
api.include_router(admin_router)

# ── 12. Update Aplikasi ───────────────────────────────────────────────────
# (bagian dari system_router)

# ── 13. Lisensi Sistem ────────────────────────────────────────────────────
api.include_router(license_router)

# ── Admin Pendukung ───────────────────────────────────────────────────────
api.include_router(syslog_router)
api.include_router(audit_router)
api.include_router(scheduler_router)
api.include_router(routing_alerts_router)

# ── VPN Clients ───────────────────────────────────────────────────────────
api.include_router(sstp_router)
api.include_router(l2tp_router)

app.include_router(api)


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "NOC-Monitoring-Pro",
        "edition": "monitoring_pro",
        "version": "1.0.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
