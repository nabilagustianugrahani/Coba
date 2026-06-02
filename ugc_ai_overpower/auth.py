import os, hmac, hashlib, json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

env_path = os.path.expanduser('~/ugc/.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

SECRET = os.getenv('JWT_SECRET', 'skynet-jwt-secret-2024')
ALGO = 'HS256'
USERS = {}

def _load_users():
    USERS.clear()
    for key in ['ADMIN', 'OWNER']:
        u = os.getenv(f'{key}_USERNAME')
        p = os.getenv(f'{key}_PASSWORD')
        if u and p:
            USERS[u] = {'password': p, 'role': key.lower()}
    if not USERS:
        USERS['admin'] = {'password': 'admin123', 'role': 'admin'}
        USERS['owner'] = {'password': 'skynet2024', 'role': 'owner'}

_load_users()

def verify_user(username, password):
    u = USERS.get(username)
    if u and u['password'] == password:
        return u
    return None

def create_token(username, role):
    import jwt
    payload = {
        'sub': username,
        'role': role,
        'iat': datetime.now(timezone.utc),
        'exp': datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)

def verify_token(token):
    import jwt
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGO])
    except:
        return None
