from flask import request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import or_
from backend.db import db
from backend.db.models import Equipment, PLCDataConfig, Log
from datetime import datetime

def register_routes(app, socketio=None):
    @app.route("/api/register", methods=["POST"])
    def api_register():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        equipment_id = data.get("equipment_id")
        mac_address = data.get("mac_address")

        if not equipment_id or not mac_address:
            return jsonify({"error": "equipment_id and mac_address are required"}), 400

        # 既存レコード検索（mac_address or equipment_id）
        equipment = Equipment.query.filter(
            or_(
                getattr(Equipment, "mac_address") == mac_address,
                getattr(Equipment, "equipment_id") == equipment_id
            )
        ).first()

        if equipment:
            # ✅ equipment_id も上書きする（これが重要）
            equipment.equipment_id = equipment_id
            equipment.manufacturer = data.get("manufacturer")
            equipment.series = data.get("series")
            equipment.ip = data.get("ip")
            equipment.hostname = data.get("hostname")
            equipment.port = data.get("port")
            equipment.interval = data.get("interval")
            equipment.status = "登録済み"
        else:
            # 新規作成
            equipment = Equipment(
                equipment_id=equipment_id,
                manufacturer=data.get("manufacturer"),
                series=data.get("series"),
                ip=data.get("ip"),
                mac_address=mac_address,
                hostname=data.get("hostname"),
                port=data.get("port"),
                interval=data.get("interval"),
                status="登録済み"
            )
            db.session.add(equipment)

        db.session.commit()
        return jsonify({"message": "登録完了"}), 200

    @app.route("/api/check-equipment", methods=["POST"])
    def check_equipment():
        data = request.get_json()
        mac = data.get("mac_address")
        ip = data.get("ip")

        if not mac or not ip:
            return jsonify({"error": "Missing mac_address or ip"}), 400

        equipment = Equipment.query.filter_by(mac_address=mac, ip=ip).first()
        if equipment:
            return jsonify({
                "found": True,
                "id": equipment.id,
                "equipment_id": equipment.equipment_id,
                "manufacturer": equipment.manufacturer,
                "series": equipment.series,
                "ip": equipment.ip,
                "port": equipment.port,
                "interval": equipment.interval,
                "status": equipment.status,
                "hostname": equipment.hostname
            }), 200
        else:
            return jsonify({"found": False}), 200

    # ラズパイ側APIコール対応エンドポイント
    @app.route("/api/equipment/<equipment_id>", methods=["GET"])
    def get_equipment_config(equipment_id):
        """設備基本設定を取得"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404
            
            return jsonify({
                "equipment_id": equipment.equipment_id,
                "manufacturer": equipment.manufacturer,
                "series": equipment.series,
                "ip": equipment.ip,
                "plc_ip": getattr(equipment, "plc_ip", ""),
                "port": equipment.port,
                "modbus_port": getattr(equipment, "modbus_port", 502),
                "interval": equipment.interval,
                "status": equipment.status,
                "hostname": equipment.hostname,
                "mac_address": equipment.mac_address
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>", methods=["PUT"])
    def save_equipment_config(equipment_id):
        """設備基本設定を保存"""
        try:
            data = request.get_json()
            print(f"🔧 [DEBUG] PUT /api/equipment/{equipment_id} 受信データ: {data}")
            
            if not data:
                print("❌ [DEBUG] データが空です")
                return jsonify({"error": "Invalid JSON"}), 400

            # CPUシリアル番号で既存設備を検索（不変識別子による確実な特定）
            cpu_serial_number = data.get("cpu_serial_number")
            equipment = None
            
            if cpu_serial_number:
                # CPUシリアル番号で既存設備を検索（最優先）
                equipment = Equipment.query.filter_by(cpu_serial_number=cpu_serial_number).first()
                
                if equipment:
                    print(f"✅ [DEBUG] CPUシリアル番号で既存設備を発見: '{equipment.equipment_id}' → '{equipment_id}' に更新")
                    print(f"    CPUシリアル番号: {cpu_serial_number}")
                    # 設備IDを新しい値に更新（設備IDは可変）
                    equipment.equipment_id = equipment_id
                else:
                    print(f"🔄 [DEBUG] CPUシリアル番号 '{cpu_serial_number}' に対応する設備が存在しないため新規作成: {equipment_id}")
            else:
                print(f"⚠️ [DEBUG] CPUシリアル番号が未提供です")
            
            # 既存設備が見つからない場合は新規作成
            if not equipment:
                print(f"🔄 [DEBUG] 新規設備を作成: {equipment_id}")
                equipment = Equipment(
                    equipment_id=equipment_id,
                    manufacturer=data.get("manufacturer"),
                    series=data.get("series"),
                    ip=data.get("raspi_ip", data.get("ip")),
                    plc_ip=data.get("plc_ip"),
                    port=data.get("plc_port"),
                    modbus_port=data.get("modbus_port", 502),
                    interval=data.get("interval"),
                    mac_address=data.get("mac_address"),
                    cpu_serial_number=cpu_serial_number,
                    hostname=data.get("hostname"),
                    status="設定済み"
                )
                db.session.add(equipment)
            
            # 設備情報を更新（既存設備・新規設備共通）
            equipment.manufacturer = data.get("manufacturer", equipment.manufacturer)
            equipment.series = data.get("series", equipment.series)
            equipment.ip = data.get("raspi_ip", data.get("ip", equipment.ip))
            equipment.plc_ip = data.get("plc_ip", equipment.plc_ip)
            equipment.port = data.get("plc_port", equipment.port)
            equipment.modbus_port = data.get("modbus_port", equipment.modbus_port)
            equipment.interval = data.get("interval", equipment.interval)
            equipment.mac_address = data.get("mac_address", equipment.mac_address)
            equipment.cpu_serial_number = data.get("cpu_serial_number", equipment.cpu_serial_number)
            equipment.hostname = data.get("hostname", equipment.hostname)
            equipment.status = "設定済み"
            equipment.updated_at = datetime.utcnow()

            db.session.commit()
            print(f"✅ [DEBUG] 設備設定保存成功: {equipment_id}")
            return jsonify({"message": "Equipment config saved"}), 200
            
        except Exception as e:
            print(f"❌ [DEBUG] 設備設定保存エラー: {str(e)}")
            print(f"❌ [DEBUG] エラー詳細: {repr(e)}")
            import traceback
            print(f"❌ [DEBUG] スタックトレース: {traceback.format_exc()}")
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/search", methods=["GET"])
    def search_equipment():
        """デバイス情報（MACアドレス、IPアドレス）で設備を検索"""
        try:
            mac_address = request.args.get("mac_address")
            ip_address = request.args.get("ip_address")      # ← ラズパイのIPアドレス

            if not mac_address and not ip_address:
                return jsonify({"error": "mac_address or ip_address is required"}), 400

            query = Equipment.query
            if mac_address:
                query = query.filter_by(mac_address=mac_address)
            if ip_address:
                query = query.filter_by(ip=ip_address)       # ← ipフィールド（ラズパイIP）で検索

            equipment = query.first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            return jsonify({
                "equipment_id": equipment.equipment_id,
                "manufacturer": equipment.manufacturer,
                "series": equipment.series,
                "ip": equipment.ip,                         # ラズパイのIPアドレス
                "plc_ip": getattr(equipment, "plc_ip", ""), # PLCのIPアドレス
                "port": equipment.port,
                "modbus_port": getattr(equipment, "modbus_port", 502),
                "interval": equipment.interval,
                "status": equipment.status,
                "hostname": equipment.hostname,
                "mac_address": equipment.mac_address
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>/setup_status", methods=["GET"])
    def get_setup_status(equipment_id):
        """設備のセットアップ完了状態を確認"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # 設備ステータスが "設定済み" の場合はセットアップ完了とみなす
            setup_completed = equipment.status == "設定済み"
            
            return jsonify({
                "equipment_id": equipment_id,
                "setup_completed": setup_completed,
                "status": equipment.status
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>/mark_setup_completed", methods=["POST"])
    def mark_setup_completed(equipment_id):
        """設備のセットアップ完了をマーク"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # ステータスを "設定済み" に更新
            equipment.status = "設定済み"
            equipment.updated_at = datetime.utcnow()
            db.session.commit()

            return jsonify({
                "message": "Setup completed marked",
                "equipment_id": equipment_id,
                "status": equipment.status
            }), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>/plc_configs", methods=["GET"])
    def get_plc_data_configs(equipment_id):
        """PLCデータ設定を取得"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404
            
            plc_configs = PLCDataConfig.query.filter_by(equipment_id=equipment.id).all()
            configs = []
            for config in plc_configs:
                configs.append({
                    "data_type": config.data_type,
                    "enabled": config.enabled,
                    "address": config.address,
                    "scale_factor": config.scale_factor,
                    "plc_data_type": getattr(config, "plc_data_type", "word")
                })
            
            return jsonify(configs), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>/plc_configs", methods=["PUT"])
    def save_plc_data_configs(equipment_id):
        """PLCデータ設定を保存"""
        try:
            data = request.get_json()
            if not isinstance(data, list):
                return jsonify({"error": "Expected list of configurations"}), 400

            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # 既存のPLC設定を削除
            PLCDataConfig.query.filter_by(equipment_id=equipment.id).delete()

            # 新しい設定を追加
            for config_data in data:
                plc_config = PLCDataConfig(
                    equipment_id=equipment.id,
                    data_type=config_data.get("data_type"),
                    enabled=config_data.get("enabled", False),
                    address=config_data.get("address", ""),
                    scale_factor=config_data.get("scale_factor", 1)
                )
                # plc_data_type フィールドが存在する場合は設定
                if hasattr(plc_config, "plc_data_type"):
                    plc_config.plc_data_type = config_data.get("plc_data_type", "word")
                db.session.add(plc_config)

            db.session.commit()
            return jsonify({"message": "PLC configs saved"}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/logs", methods=["POST"])
    def save_log_data():
        """改良版：ログデータをDBに保存 + WebSocketでリアルタイム配信"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Invalid JSON"}), 400

            equipment_id = data.get("equipment_id")
            if not equipment_id:
                return jsonify({"error": "equipment_id is required"}), 400

            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # タイムスタンプの処理
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif timestamp is None:
                timestamp = datetime.utcnow()

            # 1. DBに保存（既存機能）
            log_entry = Log()
            log_entry.equipment_id = equipment.id
            log_entry.timestamp = timestamp
            log_entry.production_count = data.get("production_count")
            log_entry.current = data.get("current")
            log_entry.temperature = data.get("temperature")
            log_entry.pressure = data.get("pressure")
            log_entry.cycle_time = data.get("cycle_time")
            log_entry.error_code = data.get("error_code")
            db.session.add(log_entry)
            db.session.commit()

            # 2. WebSocketでNuxtUIにリアルタイム配信（新機能）
            if socketio:
                realtime_data = {
                    "equipment_id": equipment_id,
                    "timestamp": timestamp.isoformat() if timestamp else datetime.utcnow().isoformat(),
                    "production_count": data.get("production_count"),
                    "current": data.get("current"),
                    "temperature": data.get("temperature"),
                    "pressure": data.get("pressure"),
                    "cycle_time": data.get("cycle_time"),
                    "error_code": data.get("error_code"),
                    "status": "normal" if not data.get("error_code") else "error"
                }
                
                # NuxtUIの全モニタリングクライアントに送信
                socketio.emit('plc_data_update', realtime_data, to='monitoring')
                
                # 特定設備のモニタリングクライアントに送信
                socketio.emit('equipment_data_update', realtime_data, to=f'equipment_{equipment_id}')

            return jsonify({
                "message": "Data saved and broadcasted",
                "saved_to_db": True,
                "broadcasted_to_ui": bool(socketio),
                "timestamp": timestamp.isoformat() if timestamp else datetime.utcnow().isoformat()
            }), 200
            
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/logs/<equipment_id>/latest", methods=["GET"])
    def get_latest_data(equipment_id):
        """最新データ取得（初期表示用）"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            latest_log = Log.query.filter_by(equipment_id=equipment.id)\
                                  .order_by(Log.id.desc())\
                                  .first()
            
            if not latest_log:
                return jsonify({"message": "No data found"}), 404

            return jsonify({
                "equipment_id": equipment_id,
                "timestamp": latest_log.timestamp.isoformat(),
                "production_count": latest_log.production_count,
                "current": latest_log.current,
                "temperature": latest_log.temperature,
                "pressure": latest_log.pressure,
                "cycle_time": latest_log.cycle_time,
                "error_code": latest_log.error_code
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/logs/<equipment_id>/history", methods=["GET"])
    def get_history_data(equipment_id):
        """履歴データ取得（グラフ表示用）"""
        try:
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # クエリパラメータで期間指定
            limit = request.args.get('limit', 100, type=int)
            
            logs = Log.query.filter_by(equipment_id=equipment.id)\
                           .order_by(Log.id.desc())\
                           .limit(limit)\
                           .all()

            history_data = []
            for log in logs:
                history_data.append({
                    "timestamp": log.timestamp.isoformat(),
                    "production_count": log.production_count,
                    "current": log.current,
                    "temperature": log.temperature,
                    "pressure": log.pressure,
                    "cycle_time": log.cycle_time,
                    "error_code": log.error_code
                })

            return jsonify({
                "equipment_id": equipment_id,
                "data": history_data,
                "total_records": len(history_data)
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # WebSocket接続管理（SocketIOが利用可能な場合のみ）
    if socketio:
        @socketio.on('join_monitoring')
        def on_join_monitoring(data):
            """NuxtUIからのモニタリング接続"""
            join_room('monitoring')
            equipment_id = data.get('equipment_id')
            if equipment_id:
                join_room(f'equipment_{equipment_id}')
            emit('status', {'msg': 'Connected to monitoring', 'room': 'monitoring'})

        @socketio.on('leave_monitoring')
        def on_leave_monitoring(data):
            """モニタリング画面の切断"""
            leave_room('monitoring')
            equipment_id = data.get('equipment_id')
            if equipment_id:
                leave_room(f'equipment_{equipment_id}')
            emit('status', {'msg': 'Left monitoring room'})

        @socketio.on('connect')
        def on_connect():
            """WebSocket接続確立"""
            emit('status', {'msg': 'Connected to PLC monitoring system'})
            print('NuxtUI client connected')

        @socketio.on('disconnect')
        def on_disconnect():
            """WebSocket接続切断"""
            print('NuxtUI client disconnected')

        @socketio.on('get_realtime_status')
        def on_get_realtime_status(data):
            """リアルタイム状態取得要求"""
            equipment_id = data.get('equipment_id')
            if equipment_id:
                # 最新データを取得してレスポンス
                equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
                if equipment:
                    latest_log = Log.query.filter_by(equipment_id=equipment.id)\
                                  .order_by(Log.id.desc())\
                                  .first()
                    if latest_log:
                        response_data = {
                            "equipment_id": equipment_id,
                            "timestamp": latest_log.timestamp.isoformat(),
                            "production_count": latest_log.production_count,
                            "current": latest_log.current,
                            "temperature": latest_log.temperature,
                            "pressure": latest_log.pressure,
                            "cycle_time": latest_log.cycle_time,
                            "error_code": latest_log.error_code,
                            "status": "normal" if not latest_log.error_code else "error"
                        }
                        emit('realtime_status', response_data) 