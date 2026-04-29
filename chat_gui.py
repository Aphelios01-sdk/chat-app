#!/usr/bin/env python3
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, ttk

class ChatApp:
    def __init__(self, root, is_server=False):
        self.root = root
        self.is_server = is_server
        self.root.title("Chat Terminal - SERVER" if is_server else "Chat Terminal - CLIENT")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        self.client = None
        self.clients = []
        self.nicknames = []
        self.running = True
        
        self._build_ui()
        
        if is_server:
            self._start_server()
    
    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", pady=10)
        header.pack(fill=tk.X)
        
        tk.Label(
            header, 
            text="💬 Terminal Chat" if not self.is_server else "🖥️ Chat Server",
            font=("Helvetica", 16, "bold"),
            fg="white", bg="#2c3e50"
        ).pack()
        
        # Chat area
        self.chat_area = scrolledtext.ScrolledText(
            self.root,
            wrap=tk.WORD,
            font=("Courier", 10),
            bg="#1e1e1e",
            fg="#00ff00",
            insertbackground="#00ff00",
            state='disabled'
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tag colors for chat
        self.chat_area.tag_config('server', foreground="#3498db")
        self.chat_area.tag_config('join', foreground="#2ecc71")
        self.chat_area.tag_config('leave', foreground="#e74c3c")
        self.chat_area.tag_config('nick', foreground="#f39c12")
        self.chat_area.tag_config('pm', foreground="#9b59b6")
        self.chat_area.tag_config('error', foreground="#e74c3c")
        
        # Input frame
        input_frame = tk.Frame(self.root, bg="#2c3e50", pady=5)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.msg_entry = tk.Entry(
            input_frame,
            font=("Helvetica", 12),
            bg="#34495e",
            fg="white",
            insertbackground="white"
        )
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.msg_entry.bind("<Return>", self._send_message)
        
        tk.Button(
            input_frame,
            text="Send",
            command=self._send_message,
            bg="#27ae60",
            fg="white",
            activebackground="#2ecc71",
            font=("Helvetica", 10, "bold"),
            padx=15
        ).pack(side=tk.RIGHT, padx=5)
        
        # Nickname
        if not self.is_server:
            self.nickname = simpledialog.askstring("Nickname", "Masukkan nickname:", parent=self.root)
            if not self.nickname:
                self.nickname = f"User{hash(self) % 10000}"
    
    def _start_server(self):
        HOST = '0.0.0.0'
        PORT = 5000
        
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((HOST, PORT))
            self.server.listen()
            self._log(f"Server started on port {PORT}", 'server')
            
            # Start accept thread
            thread = threading.Thread(target=self._accept_connections, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal start server: {e}")
    
    def _accept_connections(self):
        while self.running:
            try:
                client, addr = self.server.accept()
                self._log(f"Connection from {addr[0]}:{addr[1]}", 'server')
                
                client.send(b"Nickname: ")
                nickname = client.recv(1024).decode().strip() or f"User{len(self.clients)+1}"
                
                self.clients.append(client)
                self.nicknames.append(nickname)
                
                self._log(f"[{nickname}] bergabung!", 'join')
                self.broadcast(f"[{nickname}] bergabung!", exclude=client)
                
                thread = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                thread.start()
            except:
                break
    
    def _handle_client(self, client):
        while self.running:
            try:
                msg = client.recv(1024).decode()
                if not msg:
                    break
                
                idx = self.clients.index(client)
                nickname = self.nicknames[idx]
                
                if msg.startswith("/nick "):
                    new_nick = msg[6:].strip()
                    if new_nick and new_nick not in self.nicknames:
                        self.nicknames[idx] = new_nick
                        self._log(f"{nickname} ganti nama menjadi {new_nick}", 'nick')
                        self.broadcast(f"{nickname} ganti nama menjadi {new_nick}")
                        client.send(f"Nickname diubah ke {new_nick}\n".encode())
                elif msg.startswith("/msg "):
                    parts = msg[4:].split(" ", 1)
                    if len(parts) == 2:
                        target, text = parts
                        if target in self.nicknames:
                            t_idx = self.nicknames.index(target)
                            pm_msg = f"[PM dari {nickname}] {text}"
                            client.send(f"{pm_msg}\n".encode())
                            self.clients[t_idx].send(f"{pm_msg}\n".encode())
                            self._log(pm_msg, 'pm')
                elif msg == "/list":
                    online = ", ".join(self.nicknames) if self.nicknames else "Tidak ada"
                    client.send(f"User online ({len(self.nicknames)}): {online}\n".encode())
                elif msg == "/help":
                    help_text = """
Perintah:
/nick [nama] - Ganti nickname
/msg [user] [text] - Kirim PM
/list - User online
/help - Bantuan
"""
                    client.send(help_text.encode())
                else:
                    self._log(f"[{nickname}] {msg}", 'normal')
                    self.broadcast(f"[{nickname}] {msg}", exclude=client)
            except:
                break
        
        # Remove client
        if client in self.clients:
            idx = self.clients.index(client)
            nickname = self.nicknames.pop(idx)
            self.clients.remove(client)
            self._log(f"[{nickname}] telah keluar", 'leave')
            self.broadcast(f"[{nickname}] telah keluar")
    
    def broadcast(self, message, exclude=None):
        for c in self.clients:
            if c != exclude:
                try:
                    c.send(f"{message}\n".encode())
                except:
                    pass
    
    def _connect_to_server(self):
        HOST = self.host_entry.get()
        PORT = int(self.port_entry.get())
        
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((HOST, PORT))
            self._log(f"Terhubung ke {HOST}:{PORT}", 'server')
            
            welcome = self.client.recv(1024).decode()
            self._log(welcome.strip(), 'server')
            
            self.client.send(self.nickname.encode())
            
            thread = threading.Thread(target=self._receive_messages, daemon=True)
            thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Gagal terhubung: {e}")
    
    def _receive_messages(self):
        while self.running:
            try:
                msg = self.client.recv(1024).decode()
                if msg:
                    self._log(msg.strip(), 'normal')
            except:
                break
    
    def _send_message(self, event=None):
        msg = self.msg_entry.get().strip()
        if not msg:
            return
        
        if self.is_server:
            # Server sends to all
            self._log(f"[SERVER] {msg}", 'server')
            self.broadcast(f"[SERVER] {msg}")
        else:
            if self.client:
                try:
                    self.client.send(msg.encode())
                except:
                    self._log("Gagal mengirim pesan", 'error')
        
        self.msg_entry.delete(0, tk.END)
    
    def _log(self, message, msg_type='normal'):
        self.chat_area.config(state='normal')
        
        # Color based on type
        tag = ''
        if msg_type == 'server':
            tag = 'server'
        elif msg_type == 'join':
            tag = 'join'
        elif msg_type == 'leave':
            tag = 'leave'
        elif msg_type == 'nick':
            tag = 'nick'
        elif msg_type == 'pm':
            tag = 'pm'
        elif msg_type == 'error':
            tag = 'error'
        
        self.chat_area.insert(tk.END, f"{message}\n", tag)
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')
    
    def on_close(self):
        self.running = False
        if self.client:
            self.client.close()
        self.root.destroy()

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--server':
        # Run as server
        root = tk.Tk()
        app = ChatApp(root, is_server=True)
        root.protocol("WM_DELETE_WINDOW", app.on_close)
        root.mainloop()
    else:
        # Run as client (will show connection dialog)
        root = tk.Tk()
        
        # Connection dialog
        dialog = tk.Toplevel(root)
        dialog.title("Connect to Server")
        dialog.geometry("300x150")
        dialog.resizable(False, False)
        
        tk.Label(dialog, text="Host:").pack(pady=5)
        host_entry = tk.Entry(dialog, width=30)
        host_entry.insert(0, "localhost")
        host_entry.pack()
        
        tk.Label(dialog, text="Port:").pack(pady=5)
        port_entry = tk.Entry(dialog, width=30)
        port_entry.insert(0, "5000")
        port_entry.pack()
        
        def do_connect():
            HOST = host_entry.get()
            PORT = int(port_entry.get())
            dialog.destroy()
            root.withdraw()
            
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                client.connect((HOST, PORT))
                
                nickname = simpledialog.askstring("Nickname", "Masukkan nickname:", parent=root)
                if not nickname:
                    nickname = f"User{hash(client) % 10000}"
                
                client.send(nickname.encode())
                welcome = client.recv(1024).decode()
                
                # Create chat window
                chat_root = tk.Toplevel()
                chat_root.title(f"Chat - {nickname}")
                chat_root.geometry("600x500")
                
                chat_area = scrolledtext.ScrolledText(chat_root, wrap=tk.WORD, font=("Courier", 10), bg="#1e1e1e", fg="#00ff00", state='disabled')
                chat_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                input_frame = tk.Frame(chat_root, bg="#2c3e50", pady=5)
                input_frame.pack(fill=tk.X, side=tk.BOTTOM)
                
                msg_entry = tk.Entry(input_frame, font=("Helvetica", 12), bg="#34495e", fg="white")
                msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
                
                def send_msg(e=None):
                    msg = msg_entry.get().strip()
                    if msg:
                        try:
                            client.send(msg.encode())
                        except:
                            pass
                    msg_entry.delete(0, tk.END)
                
                msg_entry.bind("<Return>", send_msg)
                
                def receive():
                    while True:
                        try:
                            data = client.recv(1024).decode()
                            if data:
                                chat_area.config(state='normal')
                                chat_area.insert(tk.END, data.strip() + "\n")
                                chat_area.see(tk.END)
                                chat_area.config(state='disabled')
                        except:
                            break
                
                threading.Thread(target=receive, daemon=True).start()
                
                def on_close():
                    client.close()
                    chat_root.destroy()
                
                chat_root.protocol("WM_DELETE_WINDOW", on_close)
                chat_root.mainloop()
                
            except Exception as e:
                messagebox.showerror("Error", f"Gagal terhubung: {e}")
        
        tk.Button(dialog, text="Connect", command=do_connect, bg="#27ae60", fg="white", padx=20).pack(pady=15)
        
        root.withdraw()
        root.mainloop()

if __name__ == "__main__":
    main()
