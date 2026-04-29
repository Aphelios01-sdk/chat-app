"""
Chat Terminal - Kivy Android App
Build with: buildozer init && buildozer android debug
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import TextBase
from kivy.properties import StringProperty, BooleanProperty
import socket
import threading
import json

# Color scheme
BG_DARK = '#1e1e1e'
BG_HEADER = '#2c3e50'
BG_INPUT = '#34495e'
ACCENT = '#27ae60'
ACCENT_HOVER = '#2ecc71'
TEXT_LIGHT = '#ffffff'
TEXT_MUTED = '#95a5a6'


class ChatMessage(Label):
    """Single chat message widget"""
    def __init__(self, text='', msg_type='other', sender='', **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.size_hint_y = None
        self.height = 60
        self.padding = (10, 10)
        self.markup = True
        
        if msg_type == 'own':
            self.color = ACCENT_HOVER
            self.halign = 'right'
        elif msg_type == 'system':
            self.color = TEXT_MUTED
            self.halign = 'center'
            self.font_size = '12sp'
        else:
            self.color = TEXT_LIGHT
            self.halign = 'left'


class ConnectScreen(Screen):
    """Connection screen - enter host/port/nickname"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.init_ui()
    
    def init_ui(self):
        layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Title
        title = Label(
            text='[size=24][b]💬[/b] Chat Terminal[/size]',
            markup=True,
            size_hint_y=0.2,
            color=TEXT_LIGHT
        )
        layout.add_widget(title)
        
        # Mode toggle
        mode_layout = GridLayout(cols=2, size_hint_y=0.1, spacing=10)
        self.server_btn = Button(text='🖥️ Server', background_color=ACCENT)
        self.client_btn = Button(text='👤 Client', background_color=BG_INPUT)
        mode_layout.add_widget(self.server_btn)
        mode_layout.add_widget(self.client_btn)
        layout.add_widget(mode_layout)
        
        # Nickname
        self.nickname_input = TextInput(
            hint_text='Nickname',
            multiline=False,
            size_hint_y=0.1,
            background_color=BG_INPUT,
            foreground_color=TEXT_LIGHT,
            padding=(15, 10)
        )
        layout.add_widget(self.nickname_input)
        
        # Host
        self.host_input = TextInput(
            hint_text='Host / IP Server',
            text='localhost',
            multiline=False,
            size_hint_y=0.1,
            background_color=BG_INPUT,
            foreground_color=TEXT_LIGHT,
            padding=(15, 10)
        )
        layout.add_widget(self.host_input)
        
        # Port
        self.port_input = TextInput(
            hint_text='Port',
            text='5000',
            multiline=False,
            input_filter='int',
            size_hint_y=0.1,
            background_color=BG_INPUT,
            foreground_color=TEXT_LIGHT,
            padding=(15, 10)
        )
        layout.add_widget(self.port_input)
        
        # Connect button
        connect_btn = Button(
            text='[b]CONNECT[/b]',
            markup=True,
            background_color=ACCENT,
            size_hint_y=0.15
        )
        connect_btn.bind(on_press=self.do_connect)
        layout.add_widget(connect_btn)
        
        self.add_widget(layout)
    
    def do_connect(self, *args):
        nickname = self.nickname_input.text.strip() or 'User'
        host = self.host_input.text.strip() or 'localhost'
        port = int(self.port_input.text.strip() or '5000')
        
        # Switch to chat screen
        chat_screen = self.parent.get_screen('chat')
        chat_screen.connect(host, port, nickname, is_server=False)
        self.parent.current = 'chat'


class ChatScreen(Screen):
    """Main chat screen"""
    messages = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.socket = None
        self.running = False
        self.nickname = ''
        self.init_ui()
    
    def init_ui(self):
        layout = BoxLayout(orientation='vertical')
        
        # Header
        header = BoxLayout(orientation='horizontal', size_hint_y=0.08, padding=10)
        header.add_widget(Label(
            text='💬 Chat',
            font_size='18sp',
            color=TEXT_LIGHT,
            halign='left'
        ))
        self.status_label = Label(
            text='● Offline',
            font_size='12sp',
            color=TEXT_MUTED,
            halign='right'
        )
        header.add_widget(self.status_label)
        layout.add_widget(header)
        
        # Messages scroll view
        self.messages_container = GridLayout(
            cols=1,
            size_hint_y=0.82,
            spacing=5,
            padding=10
        )
        scroll = ScrollView(size_hint_y=0.82)
        scroll.add_widget(self.messages_container)
        layout.add_widget(scroll)
        
        # Input area
        input_layout = BoxLayout(size_hint_y=0.1, spacing=10, padding=10)
        self.msg_input = TextInput(
            hint_text='Ketik pesan...',
            multiline=False,
            background_color=BG_INPUT,
            foreground_color=TEXT_LIGHT,
            padding=(15, 10)
        )
        self.msg_input.bind(on_text_validate=self.send_message)
        input_layout.add_widget(self.msg_input)
        
        send_btn = Button(
            text='➤',
            background_color=ACCENT,
            on_press=self.send_message
        )
        input_layout.add_widget(send_btn)
        layout.add_widget(input_layout)
        
        self.add_widget(layout)
    
    def connect(self, host, port, nickname, is_server=False):
        self.nickname = nickname
        self.status_label.color = ACCENT_HOVER
        self.status_label.text = '● Online'
        
        if is_server:
            # Start as server
            threading.Thread(target=self._server_loop, args=(port,), daemon=True).start()
        else:
            # Connect as client
            threading.Thread(target=self._client_loop, args=(host, port,), daemon=True).start()
    
    def _server_loop(self, port):
        """Server mode - wait for connections"""
        try:
            server = socket.socket()
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', port))
            server.listen()
            self.add_system_message(f'Server started on port {port}')
            
            self.server = server
            self.clients = []
            self.nicknames = []
            
            while True:
                client, addr = server.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
        except Exception as e:
            self.add_system_message(f'Server error: {e}')
    
    def _handle_client(self, client):
        try:
            nickname = client.recv(1024).decode().strip() or 'User'
            self.clients.append(client)
            self.nicknames.append(nickname)
            self.add_system_message(f'[{nickname}] bergabung!')
            
            while True:
                msg = client.recv(1024).decode()
                if not msg:
                    break
                
                if msg.startswith('/list'):
                    online = ', '.join(self.nicknames)
                    client.send(f'Online: {online}\n'.encode())
                elif msg.startswith('/nick '):
                    new_nick = msg[6:].strip()
                    idx = self.clients.index(client)
                    old = self.nicknames[idx]
                    self.nicknames[idx] = new_nick
                    self.add_system_message(f'{old} → {new_nick}')
                elif msg.startswith('/msg '):
                    parts = msg[4:].split(' ', 1)
                    if len(parts) == 2:
                        target, text = parts
                        if target in self.nicknames:
                            idx = self.nicknames.index(target)
                            pm_msg = f'[PM dari {self.nicknames[self.clients.index(client)]}] {text}'
                            client.send(f'{pm_msg}\n'.encode())
                            self.clients[idx].send(f'{pm_msg}\n'.encode())
                else:
                    idx = self.clients.index(client)
                    sender = self.nicknames[idx]
                    self.broadcast(f'[{sender}] {msg}', exclude=client)
                    self.add_message(f'[{sender}] {msg}', 'other')
        except:
            if client in self.clients:
                idx = self.clients.index(client)
                nickname = self.nicknames.pop(idx)
                self.clients.remove(client)
                self.add_system_message(f'[{nickname}] keluar')
    
    def broadcast(self, message, exclude=None):
        for c in self.clients:
            if c != exclude:
                try:
                    c.send(f'{message}\n'.encode())
                except:
                    pass
    
    def _client_loop(self, host, port):
        """Client mode - connect to server"""
        try:
            self.socket = socket.socket()
            self.socket.connect((host, port))
            self.socket.send(self.nickname.encode())
            self.add_system_message(f'Terhubung ke {host}:{port}')
            self.running = True
            
            while self.running:
                data = self.socket.recv(1024).decode()
                if data:
                    self.add_message(data.strip(), 'other')
        except Exception as e:
            self.add_system_message(f'Terputus: {e}')
            self.status_label.color = TEXT_MUTED
            self.status_label.text = '● Offline'
    
    def send_message(self, *args):
        msg = self.msg_input.text.strip()
        if not msg:
            return
        
        if self.socket:
            try:
                self.socket.send(msg.encode())
                self.add_message(msg, 'own')
            except:
                self.add_system_message('Gagal mengirim')
        elif hasattr(self, 'server'):
            self.broadcast(f'[SERVER] {msg}')
            self.add_message(f'[SERVER] {msg}', 'own')
        else:
            self.add_system_message('Belum terhubung')
        
        self.msg_input.text = ''
    
    def add_message(self, text, msg_type='other'):
        def _add():
            msg = ChatMessage(text=text, msg_type=msg_type)
            self.messages_container.add_widget(msg)
        Clock.predicted_tick(_add)
    
    def add_system_message(self, text):
        def _add():
            msg = Label(
                text=text,
                size_hint_y=None,
                height=30,
                color=TEXT_MUTED,
                font_size='12sp',
                halign='center'
            )
            self.messages_container.add_widget(msg)
        Clock.predicted_tick(_add)


class ChatApp(App):
    def build(self):
        Window.clearcolor = (0.12, 0.12, 0.12, 1)
        
        sm = ScreenManager()
        sm.add_widget(ConnectScreen(name='connect'))
        sm.add_widget(ChatScreen(name='chat'))
        
        return sm


if __name__ == '__main__':
    ChatApp().run()
