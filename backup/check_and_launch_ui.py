from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import json
import socket
import requests
from dotenv import load_dotenv
import datetime
import uuid

# Flask 初期化
app = Flask(__name__)
load_dotenv()

# 環境変数読み込み
FLASK_SERVER = os.getenv("FLASK_SERVER", "http://localhost:5000")
RASPI_UI_URL = os.getenv("RASPI_UI_URL", "http://localhost")
RASPI_UI_PORT = os.getenv("RASPI_UI_PORT", "5001")

print("[DEBUG] FLASK_SERVER =", FLASK_SERVER)
print("[DEBUG] RASPI_UI_URL =", RASPI_UI_URL)
print("[DEBUG] RASPI_UI_PORT =", RASPI_UI_PORT)

# IP/MAC取得ユーティリティ
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join(f'{(mac >> ele) & 0xff:02x}' for ele in range(40, -1, -8))

# PLCメーカー・シリーズ
series_list = {
    "三菱": ["FX", "Q", "iQ-R", "iQ-F"],
    "キーエンス": ["KV-8000", "KV-5000", "KV Nano"],
    "オムロン": ["CJ", "CP", "NX", "NJ"]
}
manufacturers = list(series_list.keys())

@app.route("/equipment_config", methods=["GET", "POST"])
def equipment_config():
    ip = get_ip()
    mac = get_mac_address()

    if request.method == "POST":
        equipment_data = {
            "equipment_id": request.form["equipment_id"],
            "manufacturer": request.form["manufacturer"],
            "series": request.form["series"],
            "ip": request.form["ip"],
            "port": int(request.form["port"]),
            "interval": int(request.form["interval"]),
            "mac_address": mac,
            "hostname": socket.gethostname()
        }

        print("[POST] 設備情報送信データ:", equipment_data)

        try:
            response = requests.post(f"{FLASK_SERVER}/api/register", json=equipment_data)
            print("[POST] 中央サーバー応答:", response.status_code, response.text)
            response.raise_for_status()
        except requests.RequestException as e:
            print("[POST] 中央サーバーへの送信失敗:", e)
            return f"中央サーバーへの登録に失敗しました: {e}"

        return redirect(url_for("monitoring"))

    # GET: 既存情報を問い合わせてフォームに表示
    payload = {"ip": ip, "mac_address": mac}
    current = {
        "equipment_id": "",
        "manufacturer": "",
        "series": "",
        "ip": ip,
        "port": 25565,
        "interval": 1000
    }

    try:
        res = requests.post(f"{FLASK_SERVER}/api/check-equipment", json=payload)
        if res.status_code == 200 and res.json().get("found"):
            current.update(res.json())
            print("[GET] 登録済み設備:", current)
    except Exception as e:
        print("[GET] 登録確認失敗:", e)

    return render_template("equipment_config.html", current=current,series_list=series_list, manufacturers=manufacturers)

@app.route("/monitoring")
def monitoring():
    ip = get_ip()
    mac = get_mac_address()

    print("[GET] IP:", ip)
    print("[GET] MAC:", mac)

    payload = {"ip": ip, "mac_address": mac}

    try:
        res = requests.post(f"{FLASK_SERVER}/api/check-equipment", json=payload)
        print("[POST] 中央サーバー応答:", res.status_code, res.text)
        if res.status_code != 200 or not res.json().get("found"):
            return redirect(url_for("equipment_config"))
        data = res.json()
    except requests.RequestException as e:
        print("[POST] 中央サーバーとの通信失敗:", e)
        return "中央サーバーとの通信に失敗しました"

    return render_template("monitoring.html", equipment=data)

@app.route("/api/series")
def api_series():
    manufacturer = request.args.get("manufacturer") or ""
    return jsonify(series_list.get(manufacturer, []))

@app.route("/api/logs")
def api_logs():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify([
        {"timestamp": now, "status": "running", "value": 123.4},
        {"timestamp": now, "status": "running", "value": 124.1}
    ])

if __name__ == "__main__":
    port = int(RASPI_UI_PORT)
    app.run(debug=True, host="0.0.0.0", port=port)
