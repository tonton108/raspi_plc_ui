import requests
import socket
import uuid
import re
import os
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# .envから取得
FLASK_SERVER = os.getenv("FLASK_SERVER")
if not FLASK_SERVER:
    raise RuntimeError("❌ FLASK_SERVER が .env に定義されていません")

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(re.findall('..', f'{mac:012x}'))

def get_ip():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

data = {
    "ip": get_ip(),
    "mac_address": get_mac_address(),
    "hostname": socket.gethostname()
}

try:
    r = requests.post(f"{FLASK_SERVER}/api/register", json=data, timeout=5)
    r.raise_for_status()
    print("✅ 登録レスポンス:", r.json())
except requests.RequestException as e:
    print("❌ 登録失敗:", e)
