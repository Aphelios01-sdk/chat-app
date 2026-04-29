# 📱 Chat Terminal - Android App

Aplikasi chat terminal untuk Android. Dua opsi:

## Opsi 1: Web App (Jalankan Sekarang!)

Buka file ini di browser HP:
```
~/chat_app/android/www/index.html
```

Atau serving langsung:
```bash
cd ~/chat_app/android/www
python3 -m http.server 8080
# Buka http://[IP_SERVER]:8080 di browser HP
```

**Fitur:**
- ✅ Responsive mobile UI
- ✅ Mode Server & Client
- ✅ Dark theme
- ✅ Real-time chat
- ✅ User list
- ✅ Install as PWA (Add to Home Screen)

---

## Opsi 2: Kivy App (Build APK)

### Prerequisites (PC/Linux):

```bash
# Install dependencies
sudo apt update
sudo apt install -y python3-pip git unzip

# Install Kivy
pip3 install kivy[base]

# Install Buildozer
pip3 install buildozer

# Install Android SDK (Ubuntu)
sudo apt install -y android-sdk
```

### Build APK:

```bash
cd ~/chat_app/android

# Initialize buildozer
buildozer init

# Build debug APK
buildozer android debug

# Atau release APK
buildozer android release
```

APK akan ada di: `./bin/`

### Build di Cloud (Tanpa Install SDK):

Gunakan **Google Colab** atau **GitHub Actions**:

```python
# Colab notebook
!pip install buildozer kivy
!buildozer android debug
```

---

## Struktur File

```
android/
├── www/
│   └── index.html      # Web app (bisa langsung buka di browser)
├── chat_app.py          # Kivy source code
├── buildozer.spec       # Build config
└── README.md            # Dok ini
```

---

## Screenshot Web App

```
┌─────────────────────────┐
│ 💬 Chat Terminal   ●Online│
├─────────────────────────┤
│                         │
│  [User1] Halo semua!   │
│                         │
│        [Kamu] Hi!       │
│                         │
│  [User2] Apa kabar?     │
│                         │
├─────────────────────────┤
│ [Ketik pesan...    ] ➤ │
└─────────────────────────┘
```

---

## Perintah

| Perintah | Fungsi |
|----------|--------|
| `/nick [nama]` | Ganti nickname |
| `/msg [user] [text]` | Kirim PM |
| `/list` | Lihat user online |
| `/help` | Bantuan |

---

## Tips Running

### Server Mode (di HP 1):
1. Pilih mode **Server**
2. Masukkan nickname
3. Port default: **5000**
4. Tap **Connect**

### Client Mode (di HP lain):
1. Pilih mode **Client**
2. Masukkan nickname
3. Masukkan **IP** HP server + port
4. Tap **Connect**

---

## Troubleshooting

**Web app tidak bisa connect?**
- Pastikan server Python sudah jalan: `python3 server.py`
- Cek firewall: `sudo ufw allow 5000`

**Kivy build gagal?**
- Pastikan Android SDK terinstall
- Cek `buildozer debug` output untuk error detail

**Socket timeout?**
- Gunakan IP lokal (192.168.x.x) bukan localhost
- Cek kedua device satu jaringan
