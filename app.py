from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime
from dotenv import load_dotenv
import ipaddress
import csv
import time
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
import socket
import random
import threading
import pandas as pd
import zipfile
from sqlalchemy import func
from datetime import timedelta

# .env 読み込み
load_dotenv()

# Flaskアプリ初期化
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")

# DB設定
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/plc_db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# DBとマイグレーション
from db import db
from db.models import Equipment, Log
db.init_app(app)
migrate = Migrate(app, db)

# === DB起動待ち関数 ===
def wait_for_db(session, retries=10, delay=3):
    for i in range(retries):
        try:
            session.execute(text('SELECT 1'))
            print("✅ Database is ready.")
            return
        except OperationalError as e:
            print(f"⏳ DB not ready yet, retrying in {delay}s... ({i+1}/{retries})")
            time.sleep(delay)
    raise Exception("❌ Database connection failed after retries.")

# === 初回セットアップ用CSV読み込み ===
def init_equipment_from_csv():
    if Equipment.query.count() == 0:
        csv_path = "config/equipment.csv"
        if os.path.exists(csv_path):
            print("📄 equipment.csv を検出。設備情報をDBに登録します。")
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ipaddress.ip_address(row["ip"])
                        equipment = Equipment(
                            equipment_id=row["equipment_id"].strip(),
                            manufacturer=row["manufacturer"].strip(),
                            series=row.get("series", "").strip(),
                            ip=row["ip"].strip(),
                            port=int(row["port"]),
                            interval=int(row["interval"])
                        )
                        db.session.add(equipment)
                    except Exception as e:
                        print(f"❌ 登録失敗: {row} → {e}")
                db.session.commit()
                print("✅ 登録完了。")
        else:
            print("⚠️ [WARNING] 設備が未登録です。")
            print("🔧 初回セットアップのため、ブラウザで http://<ラズパイのIP>:5000/equipment_config にアクセスしてください。")

@app.route("/")
def index():
    equipment = Equipment.query.first()
    if not equipment or equipment.status == "未登録":
        return redirect(url_for("equipment_config"))

    # PLCから最新値を取得
    values = read_from_plc(equipment.ip, equipment.port, equipment.manufacturer)

    # 異常判定（例：電流 or 温度が0以下なら停止とする）
    abnormal = False
    if values:
        current = values["current"]
        temperature = values["temperature"]
        pressure = values["pressure"]
        abnormal = current <= 0 or temperature <= 0
        latest_value = f"電流: {current}A / 温度: {temperature}℃ / 圧力: {pressure}MPa"
        equipment.status = "稼働中" if not abnormal else "停止"
        db.session.commit()
    else:
        latest_value = "PLC接続エラー"
        abnormal = True
        equipment.status = "停止"
        db.session.commit()

    return render_template("monitoring.html",
                           equipment=equipment,
                           equipment_id=equipment.equipment_id,
                           latest_value=latest_value,
                           abnormal=abnormal)

@app.route("/equipment_config", methods=["GET", "POST"])
def equipment_config():
    equipment = Equipment.query.first()

    series_dict = {
        "Mitsubishi": ["FX", "Q", "iQ-R", "iQ-F"],
        "Keyence": ["KV-5000", "KV-5500", "KV-Nano", "KV-8000"],
        "Omron": ["CJ", "CP", "NX", "NJ"]
    }

    if request.method == "POST":
        try:
            equipment_id = request.form.get("equipment_id", "").strip()
            manufacturer = request.form.get("manufacturer", "").strip()
            series = request.form.get("series", "").strip()
            ip = request.form.get("ip", "").strip()
            port = int(request.form.get("port"))
            interval = int(request.form.get("interval"))

            if not equipment_id or not ip or not manufacturer:
                raise ValueError("必須項目が入力されていません。")
            ipaddress.ip_address(ip)

            if equipment:
                equipment.equipment_id = equipment_id
                equipment.manufacturer = manufacturer
                equipment.series = series
                equipment.ip = ip
                equipment.port = port
                equipment.interval = interval
            else:
                equipment = Equipment(
                    equipment_id=equipment_id,
                    manufacturer=manufacturer,
                    series=series,
                    ip=ip,
                    port=port,
                    interval=interval
                )
                db.session.add(equipment)

            db.session.commit()
            flash("設定を保存しました。", "success")
            return redirect(url_for("equipment_config"))

        except ValueError as ve:
            flash(str(ve), "error")
        except Exception as e:
            flash(f"エラー: {str(e)}", "error")

    return render_template("equipment_config.html",
                           current=equipment,
                           manufacturers=list(series_dict.keys()),
                           series_list=series_dict)

@app.route("/api/series")
def get_series():
    series_dict = {
        "Mitsubishi": ["FX", "Q", "iQ-R", "iQ-F"],
        "Keyence": ["KV-5000", "KV-5500", "KV-Nano", "KV-8000"],
        "Omron": ["CJ", "CP", "NX", "NJ"]
    }
    manufacturer = request.args.get("manufacturer")
    return jsonify(series_dict.get(manufacturer, []))

from pymcprotocol import Type3E

def read_from_plc(ip, port, manufacturer):
    # ✅ ダミー通信モード（環境変数でON/OFF）
    if os.getenv("USE_DUMMY_PLC", "false").lower() == "true":
        print("⚠️ [DUMMY MODE] PLC通信をスキップし、ダミーデータを返します。")
        return {
            "current": round(random.uniform(2.0, 5.0), 1),       # 例：3.7A
            "temperature": round(random.uniform(20.0, 40.0), 1), # 例：32.4℃
            "pressure": round(random.uniform(0.1, 0.8), 2)       # 例：0.45MPa
        }

    try:
        if manufacturer.lower() in ["mitsubishi", "keyence"]:
            from pymcprotocol import Type3E
            plc = Type3E()
            plc.connect(ip, port)

            current_raw = plc.batchread_wordunits(headdevice="D100", readsize=1)
            temperature_raw = plc.batchread_wordunits(headdevice="D101", readsize=1)
            pressure_raw = plc.batchread_wordunits(headdevice="D102", readsize=1)

            current = current_raw / 10.0
            temperature = temperature_raw / 10.0
            pressure = pressure_raw / 100.0

            return {
                "current": current,
                "temperature": temperature,
                "pressure": pressure
            }

        elif manufacturer.lower() == "omron":
            import fins.udp
            fins_client = fins.udp.udp_master()
            fins_client.dest_ip = ip
            fins_client.connect()

            def read_word(addr):
                res = fins_client.memory_area_read(b'\x82', addr, 1)
                return int.from_bytes(res[0:2], byteorder='big')

            current_raw = read_word(100)
            temperature_raw = read_word(101)
            pressure_raw = read_word(102)

            current = current_raw / 10.0
            temperature = temperature_raw / 10.0
            pressure = pressure_raw / 100.0

            return {
                "current": current,
                "temperature": temperature,
                "pressure": pressure
            }

        else:
            raise ValueError(f"不明なメーカー: {manufacturer}")
    except Exception as e:
        print(f"PLC読取エラー: {e}")
        return None

@app.route("/api/logs")
def get_logs():
    try:
        equipment = Equipment.query.first()
        if not equipment:
            return jsonify({"error": "設備が未登録です"}), 400

        values = read_from_plc(equipment.ip, equipment.port, equipment.manufacturer)

        if not values:
            equipment.status = "停止"
            db.session.commit()
            return jsonify({"error": "PLCからのデータ取得に失敗しました"}), 500

        log = Log(
            equipment_id=equipment.id,
            timestamp=datetime.utcnow(),
            current=values["current"],
            temperature=values["temperature"],
            pressure=values["pressure"]
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "values": values
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/test-connection", methods=["POST"])
def test_connection():
    try:
        equipment = Equipment.query.first()
        if not equipment:
            return jsonify({"success": False, "error": "設備情報が見つかりませんでした。"}), 400

        ip = equipment.ip
        port = equipment.port
        timeout = 3

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((ip, port))
            success = True
        except (socket.timeout, socket.error):
            success = False
        finally:
            sock.close()

        equipment.status = "稼働中" if success else "停止"
        db.session.commit()

        return jsonify({"success": success})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def api_register():
    try:
        data = request.get_json()

        ip = data.get("ip", "").strip()
        mac = data.get("mac_address", "").strip()
        hostname = data.get("hostname", "").strip()

        if not ip or not mac or not hostname:
            return jsonify({"success": False, "error": "ip, mac_address, hostname は必須です"}), 400

        equipment = Equipment.query.filter(
            (Equipment.ip == ip) | (Equipment.mac_address == mac)
        ).first()

        if not equipment:
            equipment = Equipment(
                equipment_id=f"temp-{hostname}",
                ip=ip,
                mac_address=mac,
                hostname=hostname,
                manufacturer="",
                port=0,
                interval=1000,
                status="未登録",
                updated_at=datetime.utcnow()
            )
            db.session.add(equipment)
            db.session.commit()
            return jsonify({"success": True, "redirect": "/equipment_config"}), 201

        equipment.updated_at = datetime.utcnow()
        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ログ取得ループの中で、たとえば 1時間に1回アーカイブ実行 など
last_archive_time = datetime.utcnow()

def periodic_log_fetch():
    global last_archive_time
    with app.app_context():
        while True:
            try:
                equipment = Equipment.query.first()
                if equipment:
                    values = read_from_plc(equipment.ip, equipment.port, equipment.manufacturer)
                    if values:
                        log = Log(
                            equipment_id=equipment.id,
                            timestamp=datetime.utcnow(),
                            current=values["current"],
                            temperature=values["temperature"],
                            pressure=values["pressure"]
                        )
                        db.session.add(log)
                        db.session.commit()
                        print(f"✅ Log saved: {values}")

                    # １週間ごとにアーカイブ
                    if (datetime.utcnow() - last_archive_time).total_seconds() >= 3600:
                        archive_old_logs(days=7)
                        last_archive_time = datetime.utcnow()

            except Exception as e:
                print(f"❌ ログ取得エラー: {e}")

            time.sleep(equipment.interval / 1000.0 if equipment else 5)

def archive_old_logs(days=7):
    cutoff_date = datetime.utcnow().date() - timedelta(days=days)

    logs_by_day = (
        db.session.query(
            func.date(Log.timestamp).label("log_date")
        )
        .filter(Log.timestamp < cutoff_date)
        .group_by(func.date(Log.timestamp))
        .all()
    )

    for log_date_tuple in logs_by_day:
        log_date = log_date_tuple.log_date
        filename = f"log_archives/{log_date}.csv"
        zipname = f"log_archives/{log_date}.zip"

        # すでにアーカイブ済みならスキップ
        if os.path.exists(zipname):
            continue

        logs = Log.query.filter(func.date(Log.timestamp) == log_date).all()

        # CSV保存
        df = pd.DataFrame([{
            "equipment_id": log.equipment_id,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "current": log.current,
            "temperature": log.temperature,
            "pressure": log.pressure
        } for log in logs])
        df.to_csv(filename, index=False, encoding="utf-8")

        # ZIP圧縮してCSV削除
        with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(filename, arcname=os.path.basename(filename))
        os.remove(filename)

        # DBから削除
        for log in logs:
            db.session.delete(log)
        db.session.commit()
        print(f"🗃️ アーカイブ完了: {zipname}")

if __name__ == "__main__":
    with app.app_context():
        wait_for_db(db.session)
        # init_equipment_from_csv()
        threading.Thread(target=periodic_log_fetch, daemon=True).start()
    app.run(debug=True, host="0.0.0.0")