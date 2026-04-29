#!/usr/bin/env python3
import socket
import threading

HOST = '0.0.0.0'
PORT = 5000

# ANSI Color Codes
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_WHITE = '\033[97m'
C_RESET = '\033[0m'
C_BOLD = '\033[1m'

def colored(msg, color):
    return f"{color}{msg}{C_RESET}"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind((HOST, PORT))
server.listen()

clients = []
nicknames = []

def broadcast(message, exclude=None):
    for client in clients:
        if client != exclude:
            try:
                client.send(message.encode())
            except:
                remove_client(client)

def remove_client(client):
    if client in clients:
        idx = clients.index(client)
        clients.remove(client)
        nickname = nicknames.pop(idx)
        broadcast(colored(f"[{nickname}] telah keluar", C_RED))

def handle_client(client):
    while True:
        try:
            msg = client.recv(1024).decode()
            if not msg:
                break
            
            if msg.startswith("/nick "):
                new_nick = msg[6:].strip()
                if new_nick and new_nick not in nicknames:
                    idx = clients.index(client)
                    old_nick = nicknames[idx]
                    nicknames[idx] = new_nick
                    broadcast(colored(f"{old_nick} ganti nama menjadi {new_nick}", C_YELLOW))
                    client.send(colored(f"Nickname diubah ke {new_nick}\n", C_GREEN).encode())
                elif new_nick in nicknames:
                    client.send(colored("Nickname sudah digunakan!\n", C_RED).encode())
            elif msg.startswith("/msg "):
                parts = msg[4:].split(" ", 1)
                if len(parts) == 2:
                    target, text = parts
                    if target in nicknames:
                        idx = nicknames.index(target)
                        sender = nicknames[clients.index(client)]
                        msg_to_send = colored(f"[PM dari {sender}] {text}\n", C_CYAN)
                        client.send(msg_to_send.encode())
                        clients[idx].send(msg_to_send.encode())
                    else:
                        client.send(colored("User tidak ditemukan\n", C_RED).encode())
            elif msg == "/list":
                online = ", ".join(nicknames) if nicknames else "Tidak ada"
                client.send(colored(f"User online ({len(nicknames)}): {online}\n", C_CYAN).encode())
            elif msg == "/help":
                help_text = f"""
{C_BOLD}╔══════════════════════════════════════╗{C_RESET}
{C_BOLD}║{C_RESET}         PERINTAH YANG TERSEDIA        {C_BOLD}║{C_RESET}
{C_BOLD}╠══════════════════════════════════════╣{C_RESET}
{C_BOLD}║{C_RESET} /nick [nama]  - Ganti nickname       {C_BOLD}║{C_RESET}
{C_BOLD}║{C_RESET} /msg [user] [text] - Kirim PM        {C_BOLD}║{C_RESET}
{C_BOLD}║{C_RESET} /list         - Lihat user online    {C_BOLD}║{C_RESET}
{C_BOLD}║{C_RESET} /help         - Tampilkan bantuan    {C_BOLD}║{C_RESET}
{C_BOLD}║{C_RESET} exit          - Keluar               {C_BOLD}║{C_RESET}
{C_BOLD}╚══════════════════════════════════════╝{C_RESET}
"""
                client.send(help_text.encode())
            elif msg == "/clear":
                client.send("\033[2J\033[H".encode())
            else:
                idx = clients.index(client)
                nickname = nicknames[idx]
                broadcast(colored(f"[{nickname}] {msg}", C_MAGENTA), exclude=client)
                print(colored(f"[{nickname}] {msg}", C_MAGENTA))
        except Exception as e:
            remove_client(client)
            break

def accept_connections():
    print(colored(f"{C_BOLD}╔══════════════════════════════════════╗{C_RESET}", C_GREEN))
    print(colored(f"{C_BOLD}║{C_RESET}     TERMINAL CHAT SERVER v1.0        {C_BOLD}║{C_RESET}", C_GREEN))
    print(colored(f"{C_BOLD}╚══════════════════════════════════════╝{C_RESET}", C_GREEN))
    print(colored(f"Server running on port {PORT}...", C_CYAN))
    print(colored("Menunggu koneksi...\n", C_YELLOW))
    
    while True:
        client, addr = server.accept()
        print(colored(f"[+] Koneksi baru dari {addr[0]}:{addr[1]}", C_GREEN))
        
        client.send(colored("Nickname: ", C_CYAN).encode())
        nickname = client.recv(1024).decode().strip()
        
        if not nickname:
            nickname = f"User{len(nicknames)+1}"
        if nickname in nicknames:
            nickname = f"{nickname}{len(nicknames)+1}"
        
        clients.append(client)
        nicknames.append(nickname)
        
        broadcast(colored(f"[{nickname}] bergabung!", C_GREEN))
        client.send(colored("\nSelamat datang! Ketik /help untuk bantuan\n\n", C_CYAN).encode())
        
        thread = threading.Thread(target=handle_client, args=(client,))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    try:
        accept_connections()
    except KeyboardInterrupt:
        print(colored("\nServer dimatikan...", C_RED))
        server.close()
