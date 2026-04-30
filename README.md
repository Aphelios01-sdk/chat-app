# 💬 Terminal Chat App

Aplikasi chat real-time berbasis Python dengan WebSocket support, GUI, dan AI integration.

## 🌐 Live Demo

**Web Chat:** [chat-demo-psi.vercel.app](https://chat-demo-psi.vercel.app)

> Gunakan banyak tab/browser untuk testing multi-user chat

## Tech Stack

| Komponen | Teknologi |
|----------|-----------|
| Web Frontend | HTML5, CSS3, JavaScript (Vanilla) |
| WebSocket Server | Python + `websockets` library |
| AI Integration | Claude API (Anthropic) |
| Real-time Bridge | WebSocket ↔ Telegram Bot |
| GUI Client | Python + Tkinter |

## Struktur File

```
chat_app/
├── ai_server.py        # AI chat server (Claude API)
├── bridge_server.py     # WebSocket-Telegram bridge
├── chat_gui.py         # GUI client (Tkinter)
├── client.py           # CLI client
├── server.py           # Basic socket server (legacy)
├── server.js           # Node.js WebSocket server
├── web_server.py       # HTTP web server
├── ws_server.py        # WebSocket server
├── volleyball.html     # Mini game demo
├── launcher.sh         # Auto-start script
└── README.md
```

## ⚡ Quick Start

### Web Chat (Paling Mudah)

1. Buka [chat-demo-psi.vercel.app](https://chat-demo-psi.vercel.app)
2. Masukkan username
3. Mulai chat!

### Local Development

```bash
# Clone repo
git clone https://github.com/Aphelios01-sdk/chat-app
cd chat-app

# Jalankan WebSocket server
python3 ws_server.py

# Buka web chat (terminal lain)
python3 web_server.py

# Buka browser ke http://localhost:8080
```

### GUI Client (Tkinter)

```bash
python3 chat_gui.py
```

### CLI Client

```bash
python3 client.py
```

### AI Chat Server (Butuh API Key)

```bash
# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Jalankan
python3 ai_server.py
```

## 🎮 Fitur

| Perintah | Fungsi |
|----------|--------|
| `/nick [nama]` | Ganti nickname |
| `/msg [user] [text]` | Kirim pesan private |
| `/list` | Lihat user online |
| `/help` | Tampilkan bantuan |
| `/clear` | Clear screen |
| `exit` | Keluar |

### Special Commands (AI Mode)

| Perintah | Fungsi |
|----------|--------|
| `/ai [pertanyaan]` | Tanya ke AI (Claude) |
| `/img [deskripsi]` | Generate gambar |

## 🎨 Warna Pesan

| Warna | Penggunaan |
|-------|-----------|
| 🟢 Hijau | Server info, user join |
| 🔴 Merah | User leave, error |
| 🟡 Kuning | Nickname change, warning |
| 🔵 Cyan | Private message |
| 🟣 Magenta | Broadcast message |

## 🌏 Deployment ke Vercel

### Prerequisites

- [Vercel CLI](https://vercel.com/cli): `npm i -g vercel`
- Domain kustom (optional)

### Deploy Steps

```bash
# 1. Login ke Vercel
vercel login

# 2. Deploy
cd chat-app
vercel

# 3. Set domain (optional)
vercel domain add yourdomain.com
```

### DNS Records untuk Custom Domain

| Type | Name | Value |
|------|------|-------|
| CNAME | www | `cname.vercel-dns.com` |
| A | @ | `76.76.21.21` |

> Setelah set DNS, verify di Vercel Dashboard → Settings → Domains

## 📡 API Endpoints

### WebSocket `/ws`

```javascript
// Connect
const ws = new WebSocket('wss://chat-demo-psi.vercel.app/ws');

// Send message
ws.send(JSON.stringify({
  type: 'message',
  username: 'Alice',
  content: 'Halo!'
}));

// Receive
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.username}: ${data.content}`);
};
```

### HTTP Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web chat interface |
| `/api/health` | GET | Health check |
| `/api/users` | GET | List online users |

## 🔧 Environment Variables

```env
# Untuk AI Server
ANTHROPIC_API_KEY=sk-ant-...      # Claude API key

# Untuk Bridge Server  
TELEGRAM_BOT_TOKEN=...            # Telegram bot token
TELEGRAM_CHAT_ID=...              # Target chat ID

# Untuk Vercel (auto-set)
VERCEL_URL=https://chat-demo.vercel.app
```

## 📝 Catatan Development

- WebSocket server menggunakan port `8080` (Vercel: auto-assign)
- HTTP server menggunakan port `8080`
- Bridge server connect WS client ke Telegram bot
- AI server memerlukan `anthropic` library: `pip install anthropic`

## 📜 License

MIT License

## 👤 Author

[Aphelios01-sdk](https://github.com/Aphelios01-sdk)
