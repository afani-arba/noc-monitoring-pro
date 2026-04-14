#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║   NOC Monitoring Pro — Fresh Install Script                                  ║
# ║   Edition : MONITORING PRO (Network Monitoring tanpa Billing)                ║
# ║                                                                               ║
# ║   SATU PERINTAH:                                                              ║
# ║   curl -fsSL https://raw.githubusercontent.com/afani-arba/                   ║
# ║   noc-monitoring-pro/main/install-noc-monitoring-pro.sh | sudo bash          ║
# ║                                                                               ║
# ║   Fitur: Dashboard • Device • Wall Display • Data Report • Device Hub         ║
# ║          SLA • Incident • Backup • Notifikasi • Pengaturan • License         ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
set -euo pipefail

# ── Warna & helpers ────────────────────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'
B='\033[1;34m'; C='\033[0;36m'; BOLD='\033[1m'; N='\033[0m'

ok()   { echo -e "  ${G}✔${N}  $*"; }
warn() { echo -e "  ${Y}⚠${N}  $*"; }
err()  { echo -e "\n${R}${BOLD}✗  ERROR: $*${N}\n"; exit 1; }
step() { echo -e "\n${BOLD}${B}══════════════════════════════════════════${N}"; \
         echo -e "${BOLD}${C}  $*${N}"; \
         echo -e "${BOLD}${B}══════════════════════════════════════════${N}"; }
info() { echo -e "  ${B}ℹ${N}  $*"; }

APP_DIR="/opt/noc-monitoring-pro"
REPO="https://github.com/afani-arba/noc-monitoring-pro.git"
COMPOSE_FILE="$APP_DIR/docker-compose.yml"
ENV_FILE="$APP_DIR/backend/.env"

[[ $EUID -ne 0 ]] && err "Jalankan sebagai root: sudo bash install-noc-monitoring-pro.sh"

clear
echo -e "${BOLD}${C}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   NOC Monitoring Pro — Fresh Install Script                          ║"
echo "║   Edition: MONITORING PRO (Network Monitoring)                       ║"
echo "║   Fitur: Dashboard • Device • Wall Display • SLA • Incident          ║"
echo "║          Backup • Notifikasi • Pengaturan • License                  ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${N}"
echo -e "  Waktu   : $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "  App Dir : $APP_DIR"
echo -e "  OS      : $(lsb_release -d 2>/dev/null | cut -f2 || uname -o)"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# STEP 0: Input Konfigurasi
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 0/6 — Konfigurasi Awal"

if [[ -f "$ENV_FILE" ]]; then
    warn ".env sudah ada — konfigurasi dipertahankan."
    SKIP_ENV=true
else
    SKIP_ENV=false
    echo -e "  ${Y}${BOLD}Masukkan konfigurasi NOC Monitoring Pro:${N}"
    echo ""

    read -r -p "  Nama layanan Anda [NOC Monitoring Pro]: " _NAME
    NOC_NAME="${_NAME:-NOC Monitoring Pro}"

    read -r -p "  Domain / URL akses [http://$(hostname -I | awk '{print $1}'):8083]: " _URL
    APP_URL="${_URL:-http://$(hostname -I | awk '{print $1}'):8083}"

    echo ""
    echo -e "  ${Y}${BOLD}GitHub Container Registry (GHCR):${N}"
    read -r -p "  GitHub Username [afani-arba]: " _GHUSER
    GHCR_USER="${_GHUSER:-afani-arba}"
    read -r -s -p "  GitHub Token (Personal Access Token): " _GHTOKEN
    echo ""
    GHCR_TOKEN="$_GHTOKEN"
fi

ok "Konfigurasi siap"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1: Dependensi Sistem
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 1/6 — Dependensi Sistem"

export DEBIAN_FRONTEND=noninteractive
rm -f /etc/apt/sources.list.d/docker.list
apt-get update -qq || true
apt-get install -y -qq curl wget git nano ufw \
    ca-certificates gnupg lsb-release \
    net-tools dnsutils iputils-ping > /dev/null 2>&1
ok "Paket sistem OK"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2: Docker & Docker Compose
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 2/6 — Docker Engine"

if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version | grep -oP '[\d.]+' | head -1)
    ok "Docker sudah ada (v${DOCKER_VER})"
else
    warn "Docker belum ada — install..."
    apt-get remove -y -qq docker docker-engine docker.io containerd runc 2>/dev/null || true
    OS_ID=$(lsb_release -is | tr '[:upper:]' '[:lower:]' || grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"' || echo "ubuntu")
    [[ "$OS_ID" != "debian" && "$OS_ID" != "ubuntu" ]] && OS_ID="ubuntu"
    CODENAME=$(lsb_release -cs)
    [[ "$CODENAME" == "trixie" ]] && CODENAME="bookworm"
    
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL "https://download.docker.com/linux/${OS_ID}/gpg" \
        | gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/${OS_ID} ${CODENAME} stable" \
        | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin > /dev/null 2>&1
    systemctl enable docker --now > /dev/null
    ok "Docker Engine terinstall"
fi
docker compose version &>/dev/null && ok "Docker Compose OK" || err "Docker Compose tidak ditemukan"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3: Source Code
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 3/6 — Source Code NOC Monitoring Pro"

mkdir -p /opt
if [[ -d "$APP_DIR/.git" ]]; then
    info "Update repository..."
    cd "$APP_DIR"
    git fetch --all -q 2>/dev/null || warn "git fetch gagal"
    git reset --hard origin/main -q 2>/dev/null || true
    ok "Updated → $(git log -1 --format='%h — %s' 2>/dev/null || echo 'ok')"
else
    info "Clone repository..."
    rm -rf "$APP_DIR"
    git clone "$REPO" "$APP_DIR" -q 2>/dev/null && \
        ok "Cloned → $(git -C "$APP_DIR" log -1 --format='%h — %s' 2>/dev/null || echo 'ok')" || \
        { mkdir -p "$APP_DIR"; warn "Clone gagal — pastikan taruh file manual di $APP_DIR"; }
fi

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4: Konfigurasi .env
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 4/6 — Konfigurasi Environment"

if [[ "$SKIP_ENV" == false ]]; then
    mkdir -p "$(dirname "$ENV_FILE")"
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || \
                 cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)

    cat > "$ENV_FILE" << ENVEOF
# NOC Monitoring Pro — Backend Configuration
# Auto-generated: $(date '+%Y-%m-%d %H:%M:%S')

MONGO_URI=mongodb://mongodb:27017/nocmonitoringpro
MONGO_DB_NAME=nocmonitoringpro

SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=1440

NOC_SERVICE_NAME=${NOC_NAME}
APP_URL=${APP_URL}
APP_EDITION=pro
CORS_ORIGINS=*

# ── Core Monitoring ────────────────────────────────────────────────────────────
ENABLE_POLLING=true
ENABLE_SSE=true
ENABLE_SYSLOG=true
SYSLOG_PORT=5143
ENABLE_BACKUP=true
ENABLE_ROUTING_ALERTS=true
ENABLE_SPEEDTEST=true
ENABLE_SESSION_CACHE=true
ENABLE_SNMP_POLLER=true

# ── Billing DISABLED ──────────────────────────────────────────────────────────
ENABLE_BILLING_SCHEDULER=false
ENABLE_ISOLIR=false
ENABLE_HOTSPOT_CLEANUP=false
ENABLE_RADIUS=false

# ── GenieACS / BGP DISABLED ───────────────────────────────────────────────────
ENABLE_GENIEACS_SYNC=false
ENABLE_BGP_STEERING=false
ENABLE_ROUTE_OPTIMIZER=false
ENABLE_NETWATCH_POLLER=false
ENABLE_NETFLOW=false

# ── License ────────────────────────────────────────────────────────────────────
LICENSE_SERVER_URL=https://license.arbatraining.com

# ── Firebase ───────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH=/app/firebase-service-account.json
ENVEOF
    ok ".env NOC Monitoring Pro dibuat"
else
    ok ".env sudah ada — dipertahankan"
fi

touch "$APP_DIR/firebase-service-account.json" 2>/dev/null || true

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5: Pull Docker Images
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 5/6 — Docker Images (Pull dari GHCR)"

if [[ "$SKIP_ENV" == false && -n "$GHCR_TOKEN" ]]; then
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin \
        && ok "GHCR login OK" || warn "GHCR login gagal"
fi

cd "$APP_DIR"
docker compose pull --quiet 2>/dev/null && ok "Images di-pull" || \
    warn "Pull gagal — jalankan manual: cd $APP_DIR && docker compose pull"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6: Start NOC Monitoring Pro
# ══════════════════════════════════════════════════════════════════════════════
step "STEP 6/6 — Start NOC Monitoring Pro"

cd "$APP_DIR"
docker compose down --remove-orphans 2>/dev/null || true
sleep 2
docker compose up -d 2>&1 | grep -v "^#" || err "docker compose up gagal"
sleep 5

echo ""
echo -e "  ${BOLD}Status Container:${N}"
for cname in "noc-monitoring-pro-backend" "noc-monitoring-pro-frontend" \
             "noc-monitoring-pro-mongodb" "noc-monitoring-pro-updater"; do
    state=$(docker inspect --format='{{.State.Status}}' "$cname" 2>/dev/null || echo "not_found")
    label=$(echo "$cname" | sed 's/noc-monitoring-pro-//')
    [[ "$state" == "running" ]] && ok "$label: RUNNING ✔" || warn "$label: $state"
done

# UFW Firewall
if command -v ufw &>/dev/null && ufw status | grep -q "active"; then
    ufw allow 8083/tcp comment "NOC Monitoring Pro — Dashboard" 2>/dev/null
    ufw allow 8003/tcp comment "NOC Monitoring Pro — API" 2>/dev/null
    ufw allow 5143/udp comment "Syslog UDP — NOC Monitoring Pro" 2>/dev/null
    ok "UFW: port dibuka"
fi

# Shortcut command
cat > /usr/local/bin/noc-monitoring-pro << 'CMDEOF'
#!/bin/bash
APP_DIR="/opt/noc-monitoring-pro"
case "${1:-status}" in
    start)   cd "$APP_DIR" && docker compose up -d ;;
    stop)    cd "$APP_DIR" && docker compose down ;;
    restart) cd "$APP_DIR" && docker compose restart ;;
    update)  cd "$APP_DIR" && docker compose pull && docker compose up -d --force-recreate ;;
    logs)    cd "$APP_DIR" && docker compose logs -f --tail=50 "${2:-noc-backend}" ;;
    status)  docker compose -f "$APP_DIR/docker-compose.yml" ps ;;
    *)       echo "Cara pakai: noc-monitoring-pro [start|stop|restart|update|logs|status]" ;;
esac
CMDEOF
chmod +x /usr/local/bin/noc-monitoring-pro
ok "Shortcut 'noc-monitoring-pro' tersedia"

_HOST_IP=$(hostname -I | awk '{print $1}')

echo ""
echo -e "${BOLD}${C}╔══════════════════════════════════════════════════════════════════════╗${N}"
echo -e "${BOLD}${C}║   ✅  NOC MONITORING PRO — INSTALASI SELESAI!                        ║${N}"
echo -e "${BOLD}${C}╠══════════════════════════════════════════════════════════════════════╣${N}"
echo -e "${BOLD}${C}║${N}                                                                       ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}  ${BOLD}Akses Dashboard:${N}                                                  ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    🌐 Web    : http://${_HOST_IP}:8083                                   ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    📡 API    : http://${_HOST_IP}:8003/docs                              ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}                                                                       ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}  ${BOLD}Login Default:${N}                                                    ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    👤 Username  : admin                                                ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    🔑 Password  : admin123                                             ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}                                                                       ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}  ${BOLD}Port yang Dibuka:${N}                                                 ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    8083  Frontend Web   | 8003  Backend API                           ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    5143  Syslog UDP (terima log MikroTik)                             ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}                                                                       ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}  ${BOLD}Perintah Berguna:${N}                                                 ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    noc-monitoring-pro status   # cek semua container                  ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    noc-monitoring-pro logs     # lihat log realtime                   ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    noc-monitoring-pro update   # update ke versi terbaru              ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}                                                                       ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}  ${BOLD}Langkah Selanjutnya:${N}                                              ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    1. Buka http://${_HOST_IP}:8083 dan login                             ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    2. Masukkan License Key (ArBa-MP-XXXX-XXXX)                        ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    3. Tambahkan perangkat di menu Device                              ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}║${N}    4. Aktifkan SLA & Incident monitoring                              ${BOLD}${C}║${N}"
echo -e "${BOLD}${C}╚══════════════════════════════════════════════════════════════════════╝${N}"
echo ""
