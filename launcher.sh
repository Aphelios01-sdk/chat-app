#!/bin/bash
# Chat Terminal Launcher

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "╔══════════════════════════════════════╗"
echo "║     TERMINAL CHAT APP LAUNCHER       ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Pilih mode:"
echo "  1) Jalankan sebagai SERVER"
echo "  2) Jalankan sebagai CLIENT"
echo "  3) Jalankan GUI (Tkinter)"
echo "  4) Lihat README"
echo ""
read -p "Pilihan [1-4]: " choice

case $choice in
  1)
    echo ""
    echo "Memulai Server..."
    python3 server.py
    ;;
  2)
    echo ""
    echo "Memulai Client..."
    python3 client.py
    ;;
  3)
    echo ""
    echo "Memulai GUI..."
    python3 chat_gui.py --server  # Server GUI
    ;;
  4)
    cat README.md
    ;;
  *)
    echo "Pilihan tidak valid"
    ;;
esac
