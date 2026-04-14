# VPN Agents untuk NOC Monitoring Pro

Folder ini berisi dua agen VPN yang WAJIB diinstall di server Ubuntu host (di luar container Docker) agar fitur **Koneksi VPN** di menu Pengaturan dapat berfungsi.

---

## Arsitektur

```
[ Docker Container (Backend) ]
          ↕ HTTP
[ VPN Agent (Port 8001/8002) ] ← berjalan di HOST Ubuntu
          ↕
[ VPN Connection (SSTP/L2TP) ]
          ↕
[ MikroTik ]
```

---

## 1. SSTP Agent (Port 8001)

Digunakan untuk koneksi **SSTP VPN Client** ke MikroTik via TCP/443.

### Install (jalankan di server Ubuntu **sebagai root**):

```bash
cd /tmp
git clone https://github.com/afani-arba/noc-monitoring-pro.git
cd noc-monitoring-pro/vpn-agents/sstp-agent
sudo bash install_sstp_agent.sh
```

### Verifikasi:

```bash
systemctl status sstp-agent
curl http://127.0.0.1:8001/health
```

---

## 2. L2TP Agent (Port 8002)

Digunakan untuk koneksi **L2TP VPN Client (Plain)** ke MikroTik via UDP/1701.

### Install (jalankan di server Ubuntu **sebagai root**):

```bash
cd /tmp
git clone https://github.com/afani-arba/noc-monitoring-pro.git
cd noc-monitoring-pro/vpn-agents/l2tp-agent
sudo bash install_l2tp_agent.sh
```

### Verifikasi:

```bash
systemctl status l2tp-agent
curl http://127.0.0.1:8002/health
```

---

## Troubleshooting

| Error | Solusi |
|-------|--------|
| `L2TP Agent tidak tersedia di http://172.18.0.1:8002` | Jalankan `install_l2tp_agent.sh` di server host |
| `SSTP Agent tidak tersedia di http://172.18.0.1:8001` | Jalankan `install_sstp_agent.sh` di server host |
| Agent berjalan tapi tidak bisa tersambung | Pastikan Docker bridge IP adalah `172.18.0.1`. Cek: `ip addr show docker0` |
| xl2tpd tidak ditemukan | `sudo apt-get install xl2tpd ppp` |
| sstpc tidak ditemukan | `sudo apt-get install sstp-client ppp` |

---

## Catatan

- Kedua agent harus diinstall di server **HOST Ubuntu** (bukan di dalam container Docker).
- Agent sudah dikonfigurasi sebagai **systemd service** sehingga otomatis hidup kembali saat server restart.
- Parameter VPN dikonfigurasi via UI Dashboard → Pengaturan → Koneksi VPN.
