#!/usr/bin/env python3
import socket
import threading
import sys
import select

# ANSI Color Codes
C_GREEN = '\033[92m'
C_YELLOW = '\033[93m'
C_RED = '\033[91m'
C_CYAN = '\033[96m'
C_MAGENTA = '\033[95m'
C_WHITE = '\033[97m'
C_RESET = '\033[0m'
C_BOLD = '\033[1m'

HOST = 'localhost'
PORT = 5000

client = None

def colored(msg, color):
    return f"{color}{msg}{C_RESET}"

def receive_messages():
    while True:
        try:
            msg = client.recv(1024).decode()
            if msg:
                sys.stdout.write("\r" + " " * 100 + "\r")
                print(colored(msg.strip(), C_WHITE))
                sys.stdout.write("> ")
                sys.stdout.flush()
        except:
            print(colored("\nTerputus dari server", C_RED))
            break

def main():
    global client
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        print(colored(f"{C_BOLD}╔══════════════════════════════════════╗{C_RESET}", C_CYAN))
        print(colored(f"{C_BOLD}║{C_RESET}     TERMINAL CHAT CLIENT v1.0       {C_BOLD}║{C_RESET}", C_CYAN))
        print(colored(f"{C_BOLD}╚══════════════════════════════════════╝{C_RESET}", C_CYAN))
        print(colored(f"Menghubungkan ke {HOST}:{PORT}...\n", C_YELLOW))
        
        client.connect((HOST, PORT))
        
        # Terima pesan selamat datang
        welcome = client.recv(1024).decode()
        print(colored(welcome.strip(), C_CYAN))
        
        # Thread untuk receive
        thread = threading.Thread(target=receive_messages, daemon=True)
        thread.start()
        
        print(colored("\n> Ketik pesan atau /help untuk bantuan:", C_GREEN))
        
        # Kirim pesan
        while True:
            msg = input(colored("> ", C_GREEN))
            
            if msg.lower() in ['exit', 'quit']:
                print(colored("Keluar...", C_YELLOW))
                client.close()
                break
            elif msg == "/clear":
                print("\033[2J\033[H", end="")
                continue
            
            try:
                client.send(msg.encode())
            except:
                print(colored("Gagal mengirim pesan", C_RED))
                break
                
    except ConnectionRefusedError:
        print(colored("Tidak bisa terhubung ke server!", C_RED))
        print(colored("Pastikan server sedang berjalan.", C_YELLOW))
    except KeyboardInterrupt:
        print(colored("\nKeluar...", C_YELLOW))
        if client:
            client.close()
    except Exception as e:
        print(colored(f"Error: {e}", C_RED))

if __name__ == "__main__":
    main()
