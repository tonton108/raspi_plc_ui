# models.py (更新版)
from backend.db import db
from datetime import datetime

class Equipment(db.Model):
    __tablename__ = 'equipments'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String(50), unique=True, nullable=False)
    manufacturer = db.Column(db.String(50))
    series = db.Column(db.String(50))
    ip = db.Column(db.String(100))        # ラズパイのIPアドレス
    plc_ip = db.Column(db.String(100))    # PLCのIPアドレス（新規追加）
    mac_address = db.Column(db.String(50))  # ラズパイのMACアドレス
    hostname = db.Column(db.String(100))    # ラズパイのホスト名
    port = db.Column(db.Integer)             # PLCのポート
    modbus_port = db.Column(db.Integer, default=502)  # キーエンス用Modbusポート
    interval = db.Column(db.Integer)
    status = db.Column(db.String(50), default="正常")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # リレーション
    plc_configs = db.relationship('PLCDataConfig', backref='equipment', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, equipment_id, manufacturer="", series="", ip="", plc_ip="", mac_address="", hostname="", port=0, modbus_port=502, interval=60, status="正常"):
        self.equipment_id = equipment_id
        self.manufacturer = manufacturer
        self.series = series
        self.ip = ip              # ラズパイのIPアドレス
        self.plc_ip = plc_ip      # PLCのIPアドレス
        self.mac_address = mac_address
        self.hostname = hostname
        self.port = port
        self.modbus_port = modbus_port
        self.interval = interval
        self.status = status

class PLCDataConfig(db.Model):
    """PLCデータ項目設定テーブル"""
    __tablename__ = 'plc_data_configs'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'), nullable=False)
    data_type = db.Column(db.String(50), nullable=False)  # production_count, current, temperature, pressure, cycle_time, error_code
    enabled = db.Column(db.Boolean, default=True)
    address = db.Column(db.String(20), nullable=False)    # D100, D101など
    scale_factor = db.Column(db.Integer, default=1)       # 倍率
    plc_data_type = db.Column(db.String(20), default='word')  # bit, word, dword, float32
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # ユニーク制約: 同じ設備の同じデータ型は1つまで
    __table_args__ = (db.UniqueConstraint('equipment_id', 'data_type', name='uq_equipment_data_type'),)
    
    def __init__(self, equipment_id, data_type, enabled=True, address="", scale_factor=1, plc_data_type="word"):
        self.equipment_id = equipment_id
        self.data_type = data_type
        self.enabled = enabled
        self.address = address
        self.scale_factor = scale_factor
        self.plc_data_type = plc_data_type

class Log(db.Model):
    """ログテーブル（全データ項目対応版）"""
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'))
    
    # 既存項目
    current = db.Column(db.Float)
    temperature = db.Column(db.Float)
    pressure = db.Column(db.Float)
    
    # 新規追加項目
    production_count = db.Column(db.Integer)      # 生産数量
    cycle_time = db.Column(db.Float)              # サイクルタイム
    error_code = db.Column(db.Integer)            # エラーコード
    
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# データ型定数
class DataTypes:
    PRODUCTION_COUNT = "production_count"
    CURRENT = "current"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    CYCLE_TIME = "cycle_time"
    ERROR_CODE = "error_code"
    
    @classmethod
    def get_all(cls):
        return [
            cls.PRODUCTION_COUNT,
            cls.CURRENT,
            cls.TEMPERATURE,
            cls.PRESSURE,
            cls.CYCLE_TIME,
            cls.ERROR_CODE
        ]
    
    @classmethod
    def get_display_names(cls):
        return {
            cls.PRODUCTION_COUNT: "生産数量",
            cls.CURRENT: "電流",
            cls.TEMPERATURE: "温度",
            cls.PRESSURE: "圧力",
            cls.CYCLE_TIME: "サイクルタイム",
            cls.ERROR_CODE: "エラーコード"
        }

# PLCデータ型定数
class PLCDataTypes:
    BIT = "bit"
    WORD = "word"
    DWORD = "dword"
    FLOAT32 = "float32"
    
    @classmethod
    def get_all(cls):
        return [cls.BIT, cls.WORD, cls.DWORD, cls.FLOAT32]
    
    @classmethod
    def get_display_names(cls):
        return {
            cls.BIT: "Bit",
            cls.WORD: "Word (16bit)",
            cls.DWORD: "DWord (32bit)",
            cls.FLOAT32: "Float32"
        }

# デフォルト設定を作成するヘルパー関数
def create_default_plc_configs(equipment_id):
    """設備登録時に呼び出してデフォルトのPLC設定を作成"""
    default_configs = [
        {"data_type": DataTypes.PRODUCTION_COUNT, "enabled": False, "address": "D150", "scale_factor": 1, "plc_data_type": "word"},
        {"data_type": DataTypes.CURRENT, "enabled": True, "address": "D100", "scale_factor": 10, "plc_data_type": "word"},
        {"data_type": DataTypes.TEMPERATURE, "enabled": True, "address": "D101", "scale_factor": 10, "plc_data_type": "float32"},
        {"data_type": DataTypes.PRESSURE, "enabled": True, "address": "D102", "scale_factor": 100, "plc_data_type": "word"},
        {"data_type": DataTypes.CYCLE_TIME, "enabled": False, "address": "D200", "scale_factor": 1, "plc_data_type": "dword"},
        {"data_type": DataTypes.ERROR_CODE, "enabled": False, "address": "D300", "scale_factor": 1, "plc_data_type": "word"},
    ]
    
    for config in default_configs:
        plc_config = PLCDataConfig(
            equipment_id=equipment_id,
            data_type=config["data_type"],
            enabled=config["enabled"],
            address=config["address"],
            scale_factor=config["scale_factor"],
            plc_data_type=config["plc_data_type"]
        )
        db.session.add(plc_config)
    
    db.session.commit() 