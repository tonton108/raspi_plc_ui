# check_and_launch_ui.py

import requests
import socket
import uuid
import os
import subprocess
from dotenv import load_dotenv

# .env読み込み
load_dotenv()

FLASK_SERVER = os.getenv("FLASK_SERVER")      # 中央サーバーのURL
RASPI_UI_URL = os.getenv("RASPI_UI_URL")      # ラズパイ自身のUI URL

if not FLASK_SERVER:
    raise RuntimeError("❌ FLASK_SERVER が .env に定義されていません")
if not RASPI_UI_URL:
    raise RuntimeError("❌ RASPI_UI_URL が .env に定義されていません")

def get_mac():
    mac = uuid.getnode()
    return ':'.join([f"{(mac >> ele) & 0xff:02x}" for ele in range(0, 8*6, 8)][::-1])

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

def main():
    mac = get_mac()
    ip = get_ip()

    payload = {
        "mac_address": mac,
        "ip": ip,
        "hostname": socket.gethostname()
    }

    print(f"[GET] IP: {ip}")
    print(f"[GET] MAC: {mac}")
    print(f"[POST] /api/check-equipment 宛に送信: {payload}")

    # Flask UI をバックグラウンドで起動
    print("🌐 Flask UI をバックグラウンドで起動します...")
    flask_process = subprocess.Popen(["python3", "app.py", "--port", "5001"])

    try:
        # 設備登録状態を確認
        res = requests.post(f"{FLASK_SERVER}/api/check-equipment", json=payload)
        print(f"[POST] 中央サーバー応答: {res.status_code} {res.text}")
        res.raise_for_status()
        data = res.json()

        # Chromium を kiosk モードで起動
        print("🌐 Chromium を kiosk モードで起動します...")
        if data.get("found"):
            print("✅ 登録済みの設備です。モニタリング画面へ遷移します。")
            subprocess.run(["chromium-browser", "--kiosk", f"{RASPI_UI_URL}/monitoring"])
        else:
            print("🆕 未登録の設備です。設定画面へ遷移します。")
            subprocess.run(["chromium-browser", "--kiosk", f"{RASPI_UI_URL}/equipment_config"])

    except Exception as e:
        print(f"❌ 通信エラー: {e}")
        print("🔁 Flask UI のトップを通常ブラウザで開きます")
        subprocess.run(["chromium-browser", f"{RASPI_UI_URL}/"])

    finally:
        # ブラウザを閉じた後、Flask UI プロセスを終了
        print("🛑 Flask UI を停止します...")
        flask_process.terminate()

if __name__ == "__main__":
    main()
