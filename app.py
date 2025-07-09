from flask import Flask, render_template, request, redirect, jsonify, url_for
import json
import os
import csv
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CONFIG_DIR = os.path.join("config", "equipments")
LOG_DIR = os.path.join("logs")
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

DEFAULT_PORTS = {
    "Mitsubishi": 5000,
    "Omron": 9600,
    "Keyence": 8501
}

@app.route("/")
def index():
    equipment_ids = [f.replace(".json", "") for f in os.listdir(CONFIG_DIR) if f.endswith(".json")]
    equipment_data = []

    for eid in equipment_ids:
        # 最新ログ取得
        latest_value = "-"
        abnormal = False
        log_file = os.path.join(LOG_DIR, f"{eid}.csv")
        if os.path.exists(log_file):
            with open(log_file, newline="") as csvfile:
                reader = list(csv.DictReader(csvfile))
                if reader:
                    latest_value = int(reader[-1]["value"])
                    abnormal = latest_value <= 110 or latest_value >= 130

        equipment_data.append({
            "id": eid,
            "latest": latest_value,
            "abnormal": abnormal
        })

    return render_template("equipment_list.html", equipment_data=equipment_data)



@app.route("/equipment_config/<equipment_id>", methods=["GET", "POST"])
def equipment_config(equipment_id):
    setting_path = os.path.join(CONFIG_DIR, f"{equipment_id}.json")

    if request.method == "POST":
        data = request.form.to_dict()
        data["port"] = int(data.get("port", 0))
        data["interval"] = int(data.get("interval", 1000))
        with open(setting_path, "w") as f:
            json.dump(data, f, indent=2)
        return redirect(url_for("equipment_config", equipment_id=equipment_id))

    current_settings = {}
    if os.path.exists(setting_path):
        with open(setting_path, "r") as f:
            current_settings = json.load(f)

    return render_template("equipment_config.html",
                           equipment_id=equipment_id,
                           manufacturers=DEFAULT_PORTS.keys(),
                           current=current_settings)


@app.route("/api/logs", methods=["GET"])
def get_logs():
    equipment_id = request.args.get("id")
    if not equipment_id:
        return jsonify({"error": "設備IDが必要です"}), 400

    log_file = os.path.join(LOG_DIR, f"{equipment_id}.csv")
    if not os.path.exists(log_file):
        return jsonify([])

    logs = []
    with open(log_file, newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            logs.append({
                "timestamp": row["timestamp"],
                "value": int(row["value"])
            })

    return jsonify(logs)

@app.route("/equipment_add", methods=["GET", "POST"])
def equipment_add():
    if request.method == "POST":
        equipment_id = request.form["equipment_id"]
        new_path = os.path.join(CONFIG_DIR, f"{equipment_id}.json")
        if os.path.exists(new_path):
            return "既に存在します", 400

        # 初期値でファイルを作成
        data = {
            "manufacturer": "Mitsubishi",
            "ip": "192.168.0.1",
            "port": DEFAULT_PORTS["Mitsubishi"],
            "interval": 1000
        }
        with open(new_path, "w") as f:
            json.dump(data, f, indent=2)
        return redirect(url_for("index"))

    return render_template("equipment_add.html")

@app.route("/test-connection", methods=["POST"])
def test_connection():
    equipment_id = request.json.get("id")
    # 仮：成功と返す（実際はIPで ping や socket 通信するなど）
    return jsonify({"success": True})

# 最後に
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
