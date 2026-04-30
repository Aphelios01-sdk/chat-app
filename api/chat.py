"""
Chat API for Vercel Serverless
Uses in-memory store for demo - swap with Redis/DB for production
"""

import json
import time
import uuid
from datetime import datetime, timedelta

# In-memory store (resets on cold start)
MESSAGES = []
USERS = {}
LAST_POLL = time.time() - 10  # Initialize to 10s ago so all messages show

class ChatStore:
    @staticmethod
    def add_message(username, content, msg_type='message'):
        msg = {
            'id': str(uuid.uuid4())[:8],
            'username': username,
            'content': content,
            'type': msg_type,
            'timestamp': time.time()
        }
        MESSAGES.append(msg)
        # Keep only last 100 messages
        if len(MESSAGES) > 100:
            MESSAGES.pop(0)
        return msg
    
    @staticmethod
    def get_messages(since=0):
        return [m for m in MESSAGES if m['timestamp'] > since]
    
    @staticmethod
    def get_users():
        now = time.time()
        online = []
        for user, last_seen in list(USERS.items()):
            if now - last_seen < 300:  # 5 min timeout
                online.append(user)
            else:
                USERS.pop(user, None)
        return online
    
    @staticmethod
    def register_user(username):
        USERS[username] = time.time()
    
    @staticmethod
    def heartbeat(username):
        if username in USERS or len([u for u, t in USERS.items() if now := time.time() and now - t < 300]) < 50:
            USERS[username] = time.time()

store = ChatStore()

def handler(request):
    """Vercel serverless function handler"""
    
    # CORS headers
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }
    
    if request.method == 'OPTIONS':
        return {'statusCode': 204, 'headers': headers, 'body': ''}
    
    if request.method != 'POST' and request.method != 'GET':
        return {'statusCode': 405, 'headers': headers, 'body': json.dumps({'error': 'Method not allowed'})}
    
    # Parse path
    path = request.path
    if path == '/api/chat/poll' or path == '/api/chat':
        return poll_messages(request, headers)
    elif path == '/api/chat/send':
        return send_message(request, headers)
    elif path == '/api/chat/users':
        return get_users(request, headers)
    elif path == '/api/chat/register':
        return register(request, headers)
    else:
        return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Not found'})}

def poll_messages(request, headers):
    """GET /api/chat - Poll for new messages"""
    since = float(request.query.get('since', 0))
    messages = store.get_messages(since)
    users = store.get_users()
    
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps({
            'messages': messages[-20:],  # Last 20 messages
            'users': users,
            'timestamp': time.time()
        })
    }

def send_message(request, headers):
    """POST /api/chat/send - Send a message"""
    try:
        body = json.loads(request.body) if request.body else {}
        username = body.get('username', 'Anonymous')
        content = body.get('content', '')
        
        if not content or len(content) > 1000:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid message'})
            }
        
        msg = store.add_message(username, content)
        store.heartbeat(username)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'success': True, 'message': msg})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }

def get_users(request, headers):
    """GET /api/chat/users - Get online users"""
    return {
        'statusCode': 200,
        'headers': headers,
        'body': json.dumps({'users': store.get_users()})
    }

def register(request, headers):
    """POST /api/chat/register - Register/heartbeat user"""
    try:
        body = json.loads(request.body) if request.body else {}
        username = body.get('username', '')
        
        if not username or len(username) > 30:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({'error': 'Invalid username'})
            }
        
        store.register_user(username)
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'success': True})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
