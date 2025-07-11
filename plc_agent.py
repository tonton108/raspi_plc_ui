import os
import time
import random
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

# DB送信先のFlaskサーバ（例: http://<FlaskサーバのIP>:5000）
FLASK_API_URL = os.getenv("FLASK_API_URL", "http://localhost:5000/api/logs")
INTERVAL = int(os.getenv("LOG_INTERVAL_MS", 5000))  # ms間隔

# PLC接続情報（.env から取得）
PLC_IP = os.getenv("PLC_IP", "192.168.0.10")
PLC_PORT = int(os.getenv("PLC_PORT", "5000"))
PLC_MANUFACTURER = os.getenv("PLC_MANUFACTURER", "Mitsubishi")
USE_DUMMY_PLC = os.getenv("USE_DUMMY_PLC", "false").lower() == "true"

# === PLCから値を取得する関数 ===
def read_from_plc(ip, port, manufacturer):
    if USE_DUMMY_PLC:
        print("⚠️ [DUMMY MODE] ダミーデータを返します。")
        return {
            "current": round(random.uniform(2.0, 5.0), 1),
            "temperature": round(random.uniform(20.0, 40.0), 1),
            "pressure": round(random.uniform(0.1, 0.8), 2)
        }

    try:
        if manufacturer.lower() in ["mitsubishi", "keyence"]:
            from pymcprotocol import Type3E
            plc = Type3E()
            plc.connect(ip, port)

            current_raw = plc.batchread_wordunits(headdevice="D100", readsize=1)
            temperature_raw = plc.batchread_wordunits(headdevice="D101", readsize=1)
            pressure_raw = plc.batchread_wordunits(headdevice="D102", readsize=1)

            return {
                "current": current_raw / 10.0,
                "temperature": temperature_raw / 10.0,
                "pressure": pressure_raw / 100.0
            }

        elif manufacturer.lower() == "omron":
            import fins.udp
            fins_client = fins.udp.udp_master()
            fins_client.dest_ip = ip
            fins_client.connect()

            def read_word(addr):
                res = fins_client.memory_area_read(b'\x82', addr, 1)
                return int.from_bytes(res[0:2], byteorder='big')

            return {
                "current": read_word(100) / 10.0,
                "temperature": read_word(101) / 10.0,
                "pressure": read_word(102) / 100.0
            }

        else:
            raise ValueError(f"❌ 不明なメーカー: {manufacturer}")

    except Exception as e:
        print(f"❌ PLC読取エラー: {e}")
        return None

# === メインループ ===
def main_loop():
    while True:
        values = read_from_plc(PLC_IP, PLC_PORT, PLC_MANUFACTURER)

        if values:
            payload = {
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "values": values
            }

            try:
                res = requests.get(FLASK_API_URL, json=payload, timeout=3)
                print(f"✅ 送信成功: {res.status_code} / {values}")
            except Exception as e:
                print(f"❌ 送信エラー: {e}")
        else:
            print("⚠️ データ取得失敗。")

        time.sleep(INTERVAL / 1000.0)

if __name__ == "__main__":
    main_loop()
