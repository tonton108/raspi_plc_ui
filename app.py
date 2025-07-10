from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os
from datetime import datetime
from dotenv import load_dotenv
import ipaddress

# .env 読み込み
load_dotenv()

# Flaskアプリ初期化
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")  # フラッシュメッセージ用

# DB設定
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/plc_db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# DBとマイグレーション
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# === モデル定義 ===
class Equipment(db.Model):
    __tablename__ = 'equipments'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String(50), unique=True, nullable=False)
    manufacturer = db.Column(db.String(50))
    ip = db.Column(db.String(100))
    port = db.Column(db.Integer)
    interval = db.Column(db.Integer)
    status = db.Column(db.String(50), default="正常")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String(50), db.ForeignKey('equipments.equipment_id'))
    current = db.Column(db.Float)
    temperature = db.Column(db.Float)
    pressure = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# === ルーティング ===

@app.route("/")
def index():
    equipment = Equipment.query.first()
    if not equipment:
        return redirect(url_for("equipment_config"))
    return render_template("monitoring.html",
                           equipment=equipment,
                           equipment_id=equipment.equipment_id,
                           latest_value="N/A",
                           abnormal=False)

@app.route("/equipment_config", methods=["GET", "POST"])
def equipment_config():
    equipment = Equipment.query.first()

    if request.method == "POST":
        try:
            equipment_id = request.form.get("equipment_id", "").strip()
            manufacturer = request.form.get("manufacturer", "").strip()
            ip = request.form.get("ip", "").strip()
            port = int(request.form.get("port"))
            interval = int(request.form.get("interval"))

            # バリデーション
            if not equipment_id or not ip or not manufacturer:
                raise ValueError("必須項目が入力されていません。")
            ipaddress.ip_address(ip)

            if equipment:
                equipment.equipment_id = equipment_id
                equipment.manufacturer = manufacturer
                equipment.ip = ip
                equipment.port = port
                equipment.interval = interval
            else:
                equipment = Equipment(
                    equipment_id=equipment_id,
                    manufacturer=manufacturer,
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

    return render_template("equipment_config.html", current=equipment, manufacturers=["Mitsubishi", "Omron", "Keyence"])

@app.route("/api/logs")
def get_logs():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {
        "timestamp": now,
        "values": {
            "電流": round(2.0 + (5.0 - 2.0) * os.urandom(1)[0] / 255, 2),
            "温度": round(20.0 + (40.0 - 20.0) * os.urandom(1)[0] / 255, 1),
            "圧力": round(1.0 + (2.0 - 1.0) * os.urandom(1)[0] / 255, 2)
        }
    }
    return jsonify(data)

@app.route("/test-connection", methods=["POST"])
def test_connection():
    try:
        data = request.get_json()
        ip = data.get("ip")
        port = int(data.get("port"))
        manufacturer = data.get("manufacturer")
        success = ip and port and manufacturer
        return jsonify({"success": bool(success)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/register", methods=["POST"])
def api_register():
    try:
        data = request.get_json()

        equipment_id = data.get("equipment_id", "").strip()
        manufacturer = data.get("manufacturer", "").strip()
        ip = data.get("ip", "").strip()
        port = int(data.get("port", 0))
        interval = int(data.get("interval", 1000))

        if not equipment_id or not ip or not manufacturer:
            return jsonify({"success": False, "error": "必須項目が不足しています"}), 400

        ipaddress.ip_address(ip)  # IP形式チェック

        # 既存レコードがあれば更新、なければ新規追加
        equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
        if equipment:
            equipment.manufacturer = manufacturer
            equipment.ip = ip
            equipment.port = port
            equipment.interval = interval
            equipment.updated_at = datetime.utcnow()
        else:
            equipment = Equipment(
                equipment_id=equipment_id,
                manufacturer=manufacturer,
                ip=ip,
                port=port,
                interval=interval
            )
            db.session.add(equipment)

        db.session.commit()
        return jsonify({"success": True})

    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
