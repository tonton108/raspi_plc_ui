import requests
import socket
import uuid
import re
import os
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

# .envから取得（デフォルト値を設定）
FLASK_SERVER = os.getenv("FLASK_SERVER", "http://localhost:5000")
print(f"[DEBUG] FLASK_SERVER: {FLASK_SERVER}")

def get_cpu_serial_number():
    """ラズパイのCPUシリアル番号を取得（不変識別子）"""
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    # Serial行から値を抽出
                    serial = line.split(':')[1].strip()
                    if serial and serial != "0000000000000000":
                        return serial
        # SerialがないかデフォルトIDの場合は、fallback
        print("⚠️ CPU Serial情報が見つからないため、フォールバックIDを使用")
        return _generate_fallback_serial()
    except Exception as e:
        print(f"❌ CPUシリアル番号取得エラー: {e}")
        print("🔄 フォールバックIDを生成します")
        return _generate_fallback_serial()

def _generate_fallback_serial():
    """CPUシリアル番号が取得できない場合の固定フォールバックIDを返す"""
    # 不変の固定値を使用
    fallback_id = "FALLBACK_FIXED_ID"
    print(f"💡 フォールバックID使用: {fallback_id} (固定値)")
    return fallback_id

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(re.findall('..', f'{mac:012x}'))

def get_ip():
    hostname = socket.gethostname()
    return socket.gethostbyname(hostname)

# 設備IDを自動生成（MACアドレスベース）
mac_address = get_mac_address()
cpu_serial = get_cpu_serial_number()
equipment_id = f"EP_{mac_address.replace(':', '').upper()[:8]}"

data = {
    "equipment_id": equipment_id,  # 設備IDを追加
    "ip": get_ip(),
    "mac_address": mac_address,
    "cpu_serial_number": cpu_serial,  # CPUシリアル番号を追加
    "hostname": socket.gethostname(),
    "manufacturer": "",  # 空文字で初期化
    "series": "",        # 空文字で初期化
    "port": 502,         # デフォルトポート
    "interval": 60       # デフォルト間隔（秒）
}

print(f"[INFO] 送信データ: {data}")
print(f"[INFO] CPUシリアル番号: {cpu_serial}")

try:
    r = requests.post(f"{FLASK_SERVER}/api/register", json=data, timeout=5)
    r.raise_for_status()
    print("✅ 登録レスポンス:", r.json())
except requests.RequestException as e:
    print("❌ 登録失敗:", e)
    print("ℹ️ 中央サーバーが起動しているか確認してください")
