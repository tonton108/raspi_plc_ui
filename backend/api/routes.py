from flask import request, jsonify, current_app
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import or_, text
from backend.db import db
from backend.db.models import Equipment, PLCDataConfig, Log
from datetime import datetime

def register_routes(app, socketio=None):
    print(f"🚀 [DEBUG] ===== APIルート登録開始 =====")
    print(f"🚀 [DEBUG] Flask app: {app}")
    print(f"🚀 [DEBUG] SocketIO: {socketio}")
    
    @app.route("/api/register", methods=["POST"])
    def api_register():
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        equipment_id = data.get("equipment_id")
        mac_address = data.get("mac_address")
        cpu_serial_number = data.get("cpu_serial_number")

        if not equipment_id or not mac_address:
            return jsonify({"error": "equipment_id and mac_address are required"}), 400

        # 既存レコード検索（cpu_serial_number > mac_address > equipment_id の優先順）
        search_conditions = []
        if cpu_serial_number:
            search_conditions.append(getattr(Equipment, "cpu_serial_number") == cpu_serial_number)
        search_conditions.extend([
            getattr(Equipment, "mac_address") == mac_address,
            getattr(Equipment, "equipment_id") == equipment_id
        ])
        
        equipment = Equipment.query.filter(or_(*search_conditions)).first()

        if equipment:
            # 既存設備の更新
            equipment.equipment_id = equipment_id
            equipment.manufacturer = data.get("manufacturer")
            equipment.series = data.get("series")
            equipment.ip = data.get("ip")
            equipment.plc_ip = data.get("plc_ip")
            equipment.mac_address = mac_address
            equipment.cpu_serial_number = cpu_serial_number  # CPUシリアル番号を更新
            equipment.hostname = data.get("hostname")
            equipment.port = data.get("port")
            equipment.modbus_port = data.get("modbus_port", 502)
            equipment.interval = data.get("interval")
            equipment.status = "登録済み"
        else:
            # 新規作成
            equipment = Equipment(
                equipment_id=equipment_id,
                manufacturer=data.get("manufacturer"),
                series=data.get("series"),
                ip=data.get("ip"),
                plc_ip=data.get("plc_ip"),
                mac_address=mac_address,
                cpu_serial_number=cpu_serial_number,  # CPUシリアル番号を追加
                hostname=data.get("hostname"),
                port=data.get("port"),
                modbus_port=data.get("modbus_port", 502),
                interval=data.get("interval"),
                status="登録済み"
            )
            db.session.add(equipment)

        try:
            db.session.commit()
            return jsonify({
                "message": "登録完了", 
                "cpu_serial_number": cpu_serial_number,
                "equipment_id": equipment_id
            }), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment", methods=["GET"])
    def get_all_equipment():
        """全設備一覧を取得"""
        try:
            equipments = Equipment.query.all()
            equipment_list = []
            for equipment in equipments:
                equipment_list.append({
                    "id": equipment.id,
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
                    "mac_address": equipment.mac_address,
                    "cpu_serial_number": getattr(equipment, "cpu_serial_number", ""),  # CPUシリアル番号を追加
                    "updated_at": equipment.updated_at.isoformat() if equipment.updated_at else None
                })
            return jsonify(equipment_list), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

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
                "hostname": equipment.hostname,
                "mac_address": equipment.mac_address,
                "cpu_serial_number": getattr(equipment, "cpu_serial_number", "")  # CPUシリアル番号を追加
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
                "mac_address": equipment.mac_address,
                "cpu_serial_number": getattr(equipment, "cpu_serial_number", "")  # CPUシリアル番号を追加
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/<equipment_id>", methods=["PUT"])
    def save_equipment_config(equipment_id):
        """設備基本設定を保存"""
        print(f"🔧 [DEBUG] ===== save_equipment_config 開始 =====")
        print(f"🔧 [DEBUG] URL equipment_id: {equipment_id}")
        print(f"🔧 [DEBUG] リクエストメソッド: PUT")
        
        try:
            data = request.get_json()
            print(f"🔧 [DEBUG] 受信データ: {data}")
            
            if not data:
                print("❌ [DEBUG] データが空です")
                return jsonify({"error": "Invalid JSON"}), 400

            # データベース内の全設備IDを確認
            print(f"🔍 [DEBUG] データベース内の既存設備を確認中...")
            try:
                all_equipment = Equipment.query.all()
                existing_ids = [eq.equipment_id for eq in all_equipment]
                existing_cpus = [getattr(eq, 'cpu_serial_number', 'N/A') for eq in all_equipment]
                print(f"🔍 [DEBUG] 既存設備ID一覧: {existing_ids}")
                print(f"🔍 [DEBUG] 既存CPUシリアル番号一覧: {existing_cpus}")
            except Exception as db_check_error:
                print(f"⚠️ [DEBUG] データベース確認エラー: {db_check_error}")

            # CPUシリアル番号で既存設備を検索（不変識別子による確実な特定）
            cpu_serial_number = data.get("cpu_serial_number")
            print(f"🔍 [DEBUG] 受信したCPUシリアル番号: '{cpu_serial_number}'")
            
            equipment = None
            
            if cpu_serial_number:
                print(f"🔍 [DEBUG] CPUシリアル番号 '{cpu_serial_number}' で設備を検索中...")
                # CPUシリアル番号で既存設備を検索（最優先）
                equipment = Equipment.query.filter_by(cpu_serial_number=cpu_serial_number).first()
                
                if equipment:
                    print(f"✅ [DEBUG] CPUシリアル番号で既存設備を発見!")
                    print(f"    既存設備ID: '{equipment.equipment_id}'")
                    print(f"    新設備ID: '{equipment_id}'")
                    print(f"    CPUシリアル番号: '{cpu_serial_number}'")
                    # 設備IDを新しい値に更新（設備IDは可変）
                    equipment.equipment_id = equipment_id
                    print(f"🔄 [DEBUG] 設備IDを更新しました: '{equipment.equipment_id}' → '{equipment_id}'")
                else:
                    print(f"❌ [DEBUG] CPUシリアル番号 '{cpu_serial_number}' に対応する設備が見つかりません")
                    print(f"🔄 [DEBUG] 新規作成を準備します: {equipment_id}")
            else:
                print(f"⚠️ [DEBUG] CPUシリアル番号が未提供です (None or empty)")
                print(f"🔄 [DEBUG] CPUシリアル番号なしで新規作成を準備します: {equipment_id}")
            
            # 既存設備が見つからない場合は新規作成
            if not equipment:
                print(f"🔄 [DEBUG] 新規設備を作成します: {equipment_id}")
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
                print(f"🔄 [DEBUG] 新規設備をセッションに追加しました")
            
            # 設備情報を更新（既存設備・新規設備共通）
            print(f"🔄 [DEBUG] 設備情報を更新中...")
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
            print(f"🔄 [DEBUG] 設備情報更新完了")

            print(f"💾 [DEBUG] データベースコミット実行中...")
            db.session.commit()
            print(f"✅ [DEBUG] 設備設定保存成功: {equipment_id}")
            print(f"🔧 [DEBUG] ===== save_equipment_config 正常終了 =====")
            return jsonify({"message": "Equipment config saved"}), 200
            
        except Exception as e:
            print(f"❌ [DEBUG] 設備設定保存エラー: {str(e)}")
            print(f"❌ [DEBUG] エラー詳細: {repr(e)}")
            import traceback
            print(f"❌ [DEBUG] スタックトレース: {traceback.format_exc()}")
            print(f"🔧 [DEBUG] ===== save_equipment_config エラー終了 =====")
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/equipment/search", methods=["GET"])
    def search_equipment():
        """デバイス情報（CPUシリアル番号、MACアドレス、IPアドレス）で設備を検索"""
        try:
            cpu_serial_number = request.args.get("cpu_serial_number")
            mac_address = request.args.get("mac_address")
            ip_address = request.args.get("ip_address")      # ← ラズパイのIPアドレス

            if not cpu_serial_number and not mac_address and not ip_address:
                return jsonify({"error": "cpu_serial_number, mac_address, or ip_address is required"}), 400

            # 検索条件の優先順位: cpu_serial_number > mac_address > ip_address
            equipment = None
            if cpu_serial_number:
                equipment = Equipment.query.filter_by(cpu_serial_number=cpu_serial_number).first()
            
            if not equipment and mac_address:
                equipment = Equipment.query.filter_by(mac_address=mac_address).first()
            
            if not equipment and ip_address:
                equipment = Equipment.query.filter_by(ip=ip_address).first()

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
                "mac_address": equipment.mac_address,
                "cpu_serial_number": getattr(equipment, "cpu_serial_number", "")  # CPUシリアル番号を追加
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
            print(f"🔧 [DEBUG] PUT /api/equipment/{equipment_id}/plc_configs 受信データ: {data}")
            
            if not isinstance(data, list):
                print(f"❌ [DEBUG] PLCデータ形式エラー: リストではない")
                return jsonify({"error": "Expected list of configurations"}), 400

            # 直接SQLで設備IDから内部IDを取得
            try:
                equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
                if equipment:
                    equipment_internal_id = equipment.id
                    print(f"✅ [DEBUG] SQLAlchemyで設備発見: internal_id={equipment_internal_id}")
                else:
                    print(f"🔄 [DEBUG] SQLAlchemyで設備が見つからない、直接SQLで検索")
                    result = db.session.execute(text("SELECT id FROM equipments WHERE equipment_id = :eq_id"), {"eq_id": equipment_id})
                    equipment_row = result.fetchone()
                    if equipment_row:
                        equipment_internal_id = equipment_row[0]
                        print(f"🔍 [DEBUG] 直接SQLで設備発見: internal_id={equipment_internal_id}")
                    else:
                        print(f"❌ [DEBUG] 設備が見つかりません: {equipment_id}")
                        return jsonify({"error": "Equipment not found"}), 404
            except Exception as eq_error:
                print(f"🔄 [DEBUG] 設備検索エラー、直接SQLで対応: {eq_error}")
                result = db.session.execute(text("SELECT id FROM equipments WHERE equipment_id = :eq_id"), {"eq_id": equipment_id})
                equipment_row = result.fetchone()
                if equipment_row:
                    equipment_internal_id = equipment_row[0]
                    print(f"🔍 [DEBUG] 直接SQLで設備発見: internal_id={equipment_internal_id}")
                else:
                    print(f"❌ [DEBUG] 設備が見つかりません: {equipment_id}")
                    return jsonify({"error": "Equipment not found"}), 404

            # 直接SQLでPLC設定を削除
            print(f"🔄 [DEBUG] 既存PLCデータ設定を削除: equipment_id={equipment_internal_id}")
            db.session.execute(text("DELETE FROM plc_data_configs WHERE equipment_id = :eq_id"), {"eq_id": equipment_internal_id})

            # 直接SQLで新しい設定を追加
            print(f"🔄 [DEBUG] 新しいPLCデータ設定を追加: {len(data)}件")
            for config_data in data:
                insert_data = {
                    "equipment_id": equipment_internal_id,
                    "data_type": config_data.get("data_type"),
                    "enabled": config_data.get("enabled", False),
                    "address": config_data.get("address", ""),
                    "scale_factor": config_data.get("scale_factor", 1),
                    "plc_data_type": config_data.get("plc_data_type", "word")
                }
                
                # NULL値を除外
                filtered_data = {k: v for k, v in insert_data.items() if v is not None}
                
                columns = ", ".join(filtered_data.keys())
                placeholders = ", ".join([f":{k}" for k in filtered_data.keys()])
                sql = f"INSERT INTO plc_data_configs ({columns}) VALUES ({placeholders})"
                
                print(f"🔄 [DEBUG] PLCデータ設定追加: {config_data.get('data_type')} -> {config_data.get('address')}")
                db.session.execute(text(sql), filtered_data)

            db.session.commit()
            print(f"✅ [DEBUG] PLCデータ設定保存成功: {equipment_id}")
            return jsonify({"message": "PLC configs saved (SQL fallback)"}), 200
        except Exception as e:
            print(f"❌ [DEBUG] PLCデータ設定保存エラー: {str(e)}")
            print(f"❌ [DEBUG] エラー詳細: {repr(e)}")
            import traceback
            print(f"❌ [DEBUG] スタックトレース: {traceback.format_exc()}")
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

            # ✅ データ受信ログを追加
            print(f"📥 PLCデータ受信: 設備ID={equipment_id}, タイムスタンプ={data.get('timestamp')}")
            print(f"   生産数={data.get('production_count')}, 電流={data.get('current')}A, 温度={data.get('temperature')}℃")

            # 設備の存在確認
            equipment = Equipment.query.filter_by(equipment_id=equipment_id).first()
            if not equipment:
                return jsonify({"error": "Equipment not found"}), 404

            # タイムスタンプの処理
            timestamp = data.get("timestamp")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            elif timestamp is None:
                timestamp = datetime.utcnow()

            # 簡潔なDB操作（greenlet回避）
            try:
                log_entry = Log()
                log_entry.equipment_id = equipment.id
                log_entry.timestamp = timestamp
                log_entry.production_count = data.get("production_count")
                log_entry.current = data.get("current")
                log_entry.temperature = data.get("temperature")
                log_entry.pressure = data.get("pressure")
                log_entry.cycle_time = data.get("cycle_time")
                log_entry.error_code = data.get("error_code")
                
                # 通常のSQLAlchemyセッション管理
                db.session.add(log_entry)
                db.session.commit()
                
                print(f"💾 DB保存完了: ログID={log_entry.id}")
                
            except Exception as db_error:
                db.session.rollback()
                print(f"❌ DB保存エラー: {db_error}")
                return jsonify({"error": f"Database error: {str(db_error)}"}), 500

            # WebSocketでNuxtUIにリアルタイム配信
            if socketio:
                realtime_data = {
                    "equipment_id": equipment_id,
                    "timestamp": timestamp.isoformat(),
                    "production_count": data.get("production_count"),
                    "current": data.get("current"),
                    "temperature": data.get("temperature"),
                    "pressure": data.get("pressure"),
                    "cycle_time": data.get("cycle_time"),
                    "error_code": data.get("error_code"),
                    "status": "normal" if not data.get("error_code") else "error"
                }
                
                # WebSocket送信を別のtry-catchで囲む
                try:
                    # NuxtUIの全モニタリングクライアントに送信
                    socketio.emit('plc_data_update', realtime_data, to='monitoring')
                    
                    # 特定設備のモニタリングクライアントに送信
                    socketio.emit('equipment_data_update', realtime_data, to=f'equipment_{equipment_id}')
                    
                    print(f"📡 WebSocket送信完了: monitoring + equipment_{equipment_id}")
                except Exception as ws_error:
                    print(f"⚠️ WebSocket送信エラー (処理継続): {ws_error}")

            return jsonify({
                "message": "Data saved and broadcasted",
                "saved_to_db": True,
                "broadcasted_to_ui": bool(socketio),
                "timestamp": timestamp.isoformat()
            }), 200
            
        except Exception as e:
            print(f"❌ PLCデータ処理エラー: {e}")
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
            try:
                with current_app.app_context():  # current_appを使用
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
            except Exception as e:
                print(f"❌ get_realtime_status エラー: {e}")
                emit('error', {'msg': 'Failed to get status'})
    
    # APIルート登録完了ログ
    print(f"🚀 [DEBUG] ===== APIルート登録完了 =====")
    print(f"🚀 [DEBUG] 登録されたルート:")
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/'):
            print(f"    {rule.methods} {rule.rule}")
    print(f"🚀 [DEBUG] ==========================") 