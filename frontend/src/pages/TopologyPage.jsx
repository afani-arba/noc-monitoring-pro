import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import GeoMap from "@/components/topology/GeoMap";
import ErrorBoundary from "@/components/ErrorBoundary";
import { MapPin, BookOpen, Map, ChevronRight } from "lucide-react";

function GeoGuideTab() {
  const steps = [
    {
      title: "Apa itu Geographic Network Map?",
      color: "border-blue-500/40 bg-blue-500/5",
      headerColor: "text-blue-400",
      items: [
        { label: "Fungsi Utama", text: "Geographic Network Map menampilkan seluruh perangkat jaringan (router, switch, OLT) yang terdaftar di NOC Sentinel secara visual di atas peta OpenStreetMap. Anda dapat melihat status real-time, latensi, CPU, memori, serta koneksi antar perangkat (ARP Link) langsung di peta." },
        { label: "Data yang Ditampilkan", text: "Setiap marker di peta mewakili satu perangkat. Warna marker menunjukkan statusnya: Hijau = Online, Merah = Offline, Kuning = Warning. Klik marker untuk melihat detail: CPU load, memory usage, ping latency, uptime, download/upload speed." },
      ]
    },
    {
      title: "Cara Menempatkan Perangkat di Peta",
      color: "border-emerald-500/40 bg-emerald-500/5",
      headerColor: "text-emerald-400",
      items: [
        { label: "Langkah 1 — Aktifkan Edit Mode", text: "Klik tombol \"Edit Mode\" (ikon gembok terbuka, berwarna hijau) di pojok kanan atas peta. Saat Edit Mode aktif, semua marker dapat di-drag ke posisi baru." },
        { label: "Langkah 2 — Drag Marker", text: "Klik dan tahan marker perangkat, lalu seret ke lokasi fisik perangkat tersebut di peta (gedung, tower, atau titik koordinat yang sesuai). Lepaskan mouse untuk menyimpan posisi." },
        { label: "Langkah 3 — Posisi Tersimpan Otomatis", text: "Setelah Anda melepas marker, sistem secara otomatis menyimpan koordinat latitude/longitude ke database. Indikator 'Menyimpan posisi...' akan muncul sejenak di bagian atas peta." },
        { label: "Langkah 4 — Kunci Peta", text: "Setelah semua perangkat diposisikan, klik tombol \"Terkunci\" untuk mengunci marker agar tidak bergeser secara tidak sengaja saat scroll atau klik. Dalam mode terkunci, peta hanya untuk tampilan." },
      ]
    },
    {
      title: "Fitur Tambah Perangkat Jaringan",
      color: "border-purple-500/40 bg-purple-500/5",
      headerColor: "text-purple-400",
      items: [
        { label: "Perangkat yang Bisa Ditambah", text: "Selain router MikroTik (yang otomatis muncul dari daftar Devices), Anda dapat menambahkan perangkat jaringan lain secara manual: ODP (Optical Distribution Point), ODC (Optical Distribution Cabinet), ONT (Optical Network Terminal), OLT (Optical Line Terminal), Switch, atau Access Point." },
        { label: "Cara Tambah Perangkat", text: "Klik tombol \"+ Tambah Perangkat\" → pilih tipe perangkat → isi nama → opsional isi IP dan keterangan → klik \"Simpan\". Setelah tersimpan, klik marker baru yang muncul di peta dan drag ke lokasi fisiknya." },
        { label: "Visualisasi Tipe Perangkat", text: "Setiap tipe perangkat memiliki warna marker yang berbeda: ODP = oranye, ODC = ungu, ONT = cyan, OLT = merah-muda, Switch = kuning, Access Point = biru-muda. Ini memudahkan identifikasi visual infrastruktur jaringan." },
        { label: "Hapus Perangkat Manual", text: "Klik marker perangkat manual → buka popup → klik tombol Hapus (ikon tempat sampah). Perangkat MikroTik tidak bisa dihapus dari peta ini, hapus melalui menu Devices." },
      ]
    },
    {
      title: "Fitur ARP Links & Filter",
      color: "border-amber-500/40 bg-amber-500/5",
      headerColor: "text-amber-400",
      items: [
        { label: "ARP Links", text: "Tombol \"ARP Links\" menampilkan garis putus-putus biru antara perangkat yang terdeteksi saling terhubung secara L2 (Layer 2) melalui tabel ARP MikroTik. Ini memvisualisasikan topologi fisik jaringan Anda." },
        { label: "Filter Status", text: "Gunakan tombol filter [All / Online / Offline] untuk menampilkan hanya perangkat dengan status tertentu. Berguna saat ingin fokus pada perangkat yang sedang offline." },
        { label: "Fit All", text: "Tombol \"Fit All\" akan mengatur tampilan peta secara otomatis agar semua marker yang sudah diposisikan terlihat dalam satu layar." },
        { label: "Tabel Perangkat", text: "Di bawah peta terdapat tabel lengkap semua perangkat dengan kolom Status, Nama, IP, Lokasi, CPU, Memory, Ping, DL, UL. Klik baris tabel untuk langsung menavigasi peta ke marker perangkat tersebut." },
      ]
    },
    {
      title: "Tips & Troubleshooting",
      color: "border-slate-500/40 bg-slate-500/5",
      headerColor: "text-slate-300",
      items: [
        { label: "Perangkat tidak muncul di peta?", text: "Pastikan perangkat sudah terdaftar di menu Devices dan statusnya 'Online' atau setidaknya sudah pernah di-poll. Perangkat yang belum pernah terdeteksi tidak akan muncul." },
        { label: "Marker bertumpuk di satu titik?", text: "Ini terjadi jika perangkat belum diposisikan. Sistem menempatkan perangkat tanpa koordinat di sekitar pusat peta secara acak. Gunakan Edit Mode dan drag ke lokasi masing-masing." },
        { label: "Peta tidak muncul / blank?", text: "Coba refresh halaman (Ctrl+F5). Leaflet memerlukan koneksi internet untuk mengunduh tile peta dari CartoDB. Pastikan server NOC Sentinel memiliki akses internet." },
        { label: "ARP Links tidak akurat?", text: "Data ARP diambil dari polling terakhir router MikroTik. Jika router baru saja di-restart atau belum di-poll, data ARP mungkin kosong. Tunggu polling berikutnya (interval 60 detik)." },
      ]
    },
  ];

  return (
    <div className="space-y-5 pb-8">
      <div className="flex items-center gap-3 pb-3 border-b border-border">
        <BookOpen className="w-5 h-5 text-primary" />
        <div>
          <h2 className="text-base font-bold">Panduan Penggunaan Geographic Network Map</h2>
          <p className="text-xs text-muted-foreground mt-0.5">Visualisasikan dan kelola infrastruktur jaringan Anda secara geografis</p>
        </div>
      </div>

      {steps.map((sec, si) => (
        <div key={si} className={`rounded-xl border p-5 ${sec.color}`}>
          <h3 className={`font-bold text-sm mb-3 ${sec.headerColor}`}>{sec.title}</h3>
          <div className="space-y-3">
            {sec.items.map((item, i) => (
              <div key={i} className="flex gap-3">
                <ChevronRight className={`w-4 h-4 flex-shrink-0 mt-0.5 ${sec.headerColor}`} />
                <div>
                  <p className="text-xs font-semibold text-foreground">{item.label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{item.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function TopologyPage() {
  return (
    <div className="space-y-4 pb-16" data-testid="topology-page">
       <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-2">
        <div>
          <h1 className="text-xl sm:text-2xl md:text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Map className="w-6 h-6 text-primary" />
            Topology Explorer
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground">Analisis koneksi, jangkauan, dan performa jaringan</p>
        </div>
      </div>

       <Tabs defaultValue="geo" className="w-full">
         <TabsList className="mb-4 bg-muted/50 p-1 border border-border">
            <TabsTrigger value="geo" className="gap-2 px-6">
               <MapPin className="w-4 h-4" /> Geographic Map
            </TabsTrigger>
            <TabsTrigger value="guide" className="gap-2 px-6">
               <BookOpen className="w-4 h-4" /> Cara Penggunaan
            </TabsTrigger>
         </TabsList>

         <TabsContent value="geo" className="mt-0 outline-none">
            <ErrorBoundary>
               <GeoMap />
            </ErrorBoundary>
         </TabsContent>
         <TabsContent value="guide" className="mt-0 outline-none">
            <GeoGuideTab />
         </TabsContent>
       </Tabs>
    </div>
  )
}
