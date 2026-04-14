import logging
import asyncio
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

from core.db import get_db
from core.auth import get_current_user, require_admin
from mikrotik_api import get_api_client

router = APIRouter(tags=["topology"])
logger = logging.getLogger(__name__)

# ── TOPOLOGY ──

@router.get("/topology")
async def get_topology(user=Depends(get_current_user)):
    """
    Return data topology jaringan Logical/Geographic.
    Menarik semua device dan membuat Edges berdasarkan ARP neighbors.
    Dilengkapi fitur Auto-Discovery ONT dari sesi PPPoE aktif pada MikroTik.
    """
    db = get_db()
    devices = await db.devices.find(
        {},
        {"_id": 0, "id": 1, "name": 1, "ip_address": 1, "status": 1,
         "model": 1, "cpu_load": 1, "memory_usage": 1, "uptime": 1,
         "description": 1, "last_poll": 1, "last_poll_data": 1,
         "device_type": 1, "topo_x": 1, "topo_y": 1, "lat": 1, "lng": 1, "location_name": 1}
    ).to_list(1000)

    nodes = []
    edges = []
    seen_edges = set()
    ip_to_id = {d["ip_address"]: d["id"] for d in devices if d.get("ip_address")}

    # Proses device utama
    for d in devices:
        status = d.get("status", "unknown")
        device_type = d.get("device_type") or "Unknown"

        last_poll = d.get("last_poll_data") or {}
        cpu = last_poll.get("cpu_load", d.get("cpu_load", 0)) or 0
        mem = last_poll.get("memory_usage", d.get("memory_usage", 0)) or 0

        # Identifikasi role untuk Logical Map icons
        role = device_type.lower()
        if not role or role == "unknown":
            model_str = (d.get("model") or "").lower()
            if any(k in model_str for k in ["router", "routeros", "chr"]):
                role = "router"
            elif any(k in model_str for k in ["switch", "css", "crs"]):
                role = "switch"
            elif any(k in model_str for k in ["wap", "cap", "hap", "ap"]):
                role = "wifi ap"
            else:
                role = "mikrotik"

        nodes.append({
            "id": d["id"],
            "label": d.get("name", d["id"]),
            "ip": d.get("ip_address", ""),
            "status": status,
            "role": role,
            "device_type": device_type,
            "model": d.get("model", ""),
            "cpu": cpu,
            "memory": mem,
            "uptime": d.get("uptime", ""),
            "description": d.get("description", ""),
            "last_poll": d.get("last_poll", ""),
            "topo_x": d.get("topo_x"),
            "topo_y": d.get("topo_y"),
            "lat": d.get("lat"),
            "lng": d.get("lng"),
            "location_name": d.get("location_name"),
        })

        # Edges via ARP
        arp_table = last_poll.get("arp", []) or []
        for arp in arp_table:
            neighbor_ip = arp.get("address") or arp.get("ip") or ""
            if neighbor_ip and neighbor_ip in ip_to_id:
                neighbor_id = ip_to_id[neighbor_ip]
                edge_key = tuple(sorted([d["id"], neighbor_id]))
                if edge_key not in seen_edges and d["id"] != neighbor_id:
                    seen_edges.add(edge_key)
                    edges.append({
                        "id": f"e_arp_{edge_key[0]}_{edge_key[1]}",
                        "source": edge_key[0],
                        "target": edge_key[1],
                        "label": "ARP",
                        "type": "arp"
                    })

    # AUTO-DISCOVERY ONT (PPPoE Clients)
    # Loop over devices that are MikroTik routers. We will fetch PPPoE Active locally if device API is reachable
    # Wait, polling live might slow down the topology API heavily if there are many routers.
    # Instead, we will use the `ppp_active` data from `last_poll_data` if available.
    # We should ensure `last_poll_data` contains PPPoE active users.
    for d in devices:
        last_poll = d.get("last_poll_data", {})
        if not last_poll:
            continue
            
        ppp_active = last_poll.get("ppp_active", [])
        if not ppp_active:
            continue
            
        for ppp in ppp_active:
            username = ppp.get("name") or "Unknown ONT"
            ip = ppp.get("address") or ""
            uptime = ppp.get("uptime") or ""
            
            # Buat ID unik untuk ONT
            ont_id = f"ont_{d['id']}_{username}"
            
            nodes.append({
                "id": ont_id,
                "label": username,
                "ip": ip,
                "status": "online",
                "role": "ont",
                "device_type": "ONT",
                "model": "PPPoE Client",
                "cpu": 0,
                "memory": 0,
                "uptime": uptime,
                "description": f"Connected via {d.get('name')}",
                "last_poll": d.get("last_poll", ""),
                "parent_router_id": d["id"], # Untuk keperluan diagnostik (Ping)
                # Secara visual kita biarkan posisinya nol atau letakkan di sekitar parent
                # Sigma akan menata ulang dengan ForceAtlas jika topo_x null
                "topo_x": None, 
                "topo_y": None,
            })
            
            edges.append({
                "id": f"e_pppoe_{d['id']}_{ont_id}",
                "source": d["id"],
                "target": ont_id,
                "label": "PPPoE",
                "type": "pppoe",
                "dashed": True
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total": len(nodes),
            "online": sum(1 for n in nodes if n["status"] == "online"),
            "offline": sum(1 for n in nodes if n["status"] == "offline"),
            "ont_count": sum(1 for n in nodes if n.get("role") == "ont")
        }
    }


class PingOntRequest(BaseModel):
    router_id: str
    target_ip: str

@router.post("/topology/ping-ont")
async def ping_ont(req: PingOntRequest, user=Depends(get_current_user)):
    """
    Melakukan tools/ping secara live dari router asal ke IP ONT (PPPoE Client).
    """
    db = get_db()
    router = await db.devices.find_one({"id": req.router_id}, {"_id": 0})
    if not router:
        raise HTTPException(status_code=404, detail="Parent Router not found")
        
    try:
        mt = get_api_client(router)
        if router.get("api_mode") == "api":
            try:
                result = await asyncio.to_thread(
                    mt._api.get_resource("/tool/ping").call,
                    'ping',
                    {"address": req.target_ip, "count": "3"}
                )
                res_list = list(result)
            except Exception as e:
                res_list = []
        else:
            # REST
            result = await asyncio.to_thread(
                mt.post, "/tool/ping",
                {"address": req.target_ip, "count": "3", "interval": "1s"}
            )
            res_list = result if isinstance(result, list) else []

        # Hitung rerata ping dan packet loss
        total_pings = len(res_list)
        if total_pings == 0:
            return {"status": "timeout", "latency_ms": 999, "loss": 100, "message": "No reply - Timeout (Redaman sangat tinggi / Putus kabel)"}
            
        success = sum(1 for r in res_list if r.get("received", "0") != "0" or r.get("status") == "")
        loss_percent = int(((total_pings - success) / total_pings) * 100) if total_pings > 0 else 100
        
        times = []
        for r in res_list:
            if "time" in r:
                t_str = r["time"]
                try:
                    if t_str.endswith("ms"):
                        times.append(float(t_str.replace("ms", "")))
                    elif t_str.endswith("s"):
                        times.append(float(t_str.replace("s", "")) * 1000)
                except ValueError:
                    pass

        avg_latency = sum(times) / len(times) if times else 999
        
        # Diagnosis
        diag_status = "healthy"
        msg = "Kabel Sehat"
        if loss_percent == 100:
            diag_status = "timeout"
            msg = "Timeout 100% - Indikasi FO Cut/Power Off"
        elif loss_percent > 0:
            diag_status = "warning"
            msg = f"Packet Loss {loss_percent}% - Indikasi Redaman Tinggi"
        elif avg_latency > 50:
            diag_status = "warning"
            msg = f"Latency Tinggi ({int(avg_latency)}ms) - Indikasi Redaman Bapuk"
            
        return {
            "status": diag_status,
            "latency_ms": int(avg_latency),
            "loss": loss_percent,
            "message": msg,
            "raw": res_list
        }
        
    except Exception as e:
        logger.error(f"Ping ONT failed: {e}")
        raise HTTPException(status_code=502, detail=f"Ping execution failed: {str(e)}")


# ─── Extra Topology Nodes (ODP, ODC, ONT, Switch dll) ───────────────────────

class ExtraNodeCreate(BaseModel):
    device_type: str       # ODP, ODC, ONT, OLT, Switch, AP, Router
    name: str
    ip_address: Optional[str] = None
    description: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

@router.post("/topology/nodes")
async def create_topology_node(payload: ExtraNodeCreate, user=Depends(get_current_user)):
    """Tambah perangkat manual (ODP/ODC/ONT/Switch) ke peta topologi."""
    db = get_db()
    node = {
        "id": str(uuid.uuid4()),
        "device_type": payload.device_type,
        "name": payload.name,
        "ip_address": payload.ip_address or "",
        "description": payload.description or "",
        "lat": payload.lat,
        "lng": payload.lng,
        "status": "unknown",
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user.get("username", "system"),
    }
    await db.topology_nodes.insert_one(node)
    node.pop("_id", None)
    return node

@router.get("/topology/nodes")
async def list_topology_nodes(user=Depends(get_current_user)):
    """Ambil semua perangkat manual yang ditambahkan ke peta."""
    db = get_db()
    nodes = await db.topology_nodes.find({}, {"_id": 0}).to_list(5000)
    return nodes

@router.patch("/topology/nodes/{node_id}/location")
async def update_node_location(node_id: str, payload: dict, user=Depends(get_current_user)):
    """Update koordinat posisi perangkat manual di peta."""
    db = get_db()
    await db.topology_nodes.update_one(
        {"id": node_id},
        {"$set": {"lat": payload.get("lat"), "lng": payload.get("lng")}}
    )
    return {"ok": True}

@router.delete("/topology/nodes/{node_id}")
async def delete_topology_node(node_id: str, user=Depends(get_current_user)):
    """Hapus perangkat manual dari peta topologi."""
    db = get_db()
    result = await db.topology_nodes.delete_one({"id": node_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True}

