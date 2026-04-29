# 💬 Terminal Chat App

Aplikasi chat berbasis terminal menggunakan Python socket.

## Struktur File

```
chat_app/
├── server.py    # Server chat
├── client.py    # Client chat
└── README.md    # Dokumentasi
```

## Cara Pakai

### 1. Jalankan Server
```bash
cd ~/chat_app
python3 server.py
```

### 2. Jalankan Client (terminal baru)
```bash
cd ~/chat_app
python3 client.py
```

### 3. Buka terminal baru untuk client tambahan
```bash
python3 client.py
```

## Fitur

| Perintah | Fungsi |
|----------|--------|
| `/nick [nama]` | Ganti nickname |
| `/msg [user] [text]` | Kirim pesan pribadi |
| `/list` | Lihat user online |
| `/help` | Tampilkan bantuan |
| `/clear` | Clear screen |
| `exit` | Keluar |

## Warna

Pesan menggunakan warna ANSI:
- 🟢 Hijau = Server info, bergabung
- 🔴 Merah = Keluar, error
- 🟡 Kuning = Warning, nickname change
- 🔵 Cyan = Private message, info
- 🟣 Magenta = Pesan broadcast

## Dependency

Tidak ada dependency eksternal. Hanya gunakan library standar Python:
- `socket` - Networking
- `threading` - Multi-client support
- `colorama` (optional) - Warna cross-platform

## Screenshot

```
┌─────────────────────────────────┐
│  TERMINAL CHAT SERVER v1.0     │
│  Server running on port 5000  │
│  Menunggu koneksi...           │
│                                 │
│  [+] Koneksi baru dari 127.0.0.1│
│  [Alice] bergabung!            │
│  [Bob] bergabung!              │
│  [Alice] Halo semua!          │
└─────────────────────────────────┘
```
