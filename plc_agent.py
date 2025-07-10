import time
import json
import requests
import socket
from datetime import datetime

# ====== 設備設定（ラズパイ側で事前に変更） ======
equipment_info = {
    "equipment_id": "ep001",
    "manufacturer": "Mitsubishi",  # "Omron", "Keyence" など
    "ip": "192.168.0.101",
    "port": 5000,
    "interval": 5000  # 5秒
}

SERVER_URL = "http://<FlaskサーバのIP>:5000"
REGISTER_ENDPOINT = f"{SERVER_URL}/api/register"
LOG_ENDPOINT = f"{SERVER_URL}/api/log"

# ====== 模擬的なPLC読み取り関数（仮） ======
def read_plc_values():
    import random
    return {
        "current": round(random.uniform(2.0, 5.0), 2),
        "temperature": round(random.uniform(20.0, 40.0), 1),
        "pressure": round(random.uniform(1.0, 2.0), 2),
        "timestamp": datetime.now().isoformat()
    }

# ====== 登録処理 ======
def register_equipment():
    try:
        response = requests.post(REGISTER_ENDPOINT, json=equipment_info, timeout=5)
        response.raise_for_status()
        print("✅ 設備登録成功")
    except Exception as e:
        print(f"❌ 設備登録失敗: {e}")

# ====== ログ送信処理 ======
def send_log():
    try:
        data = read_plc_values()
        data["equipment_id"] = equipment_info["equipment_id"]
        response = requests.post(LOG_ENDPOINT, json=data, timeout=5)
        response.raise_for_status()
        print(f"📡 ログ送信成功: {data}")
    except Exception as e:
        print(f"❌ ログ送信失敗: {e}")

# ====== メインループ ======
if __name__ == "__main__":
    register_equipment()

    while True:
        send_log()
        time.sleep(equipment_info["interval"] / 1000)  # intervalはms単位
