# models.py
from db import db
from datetime import datetime

class Equipment(db.Model):
    __tablename__ = 'equipments'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String(50), unique=True, nullable=False)
    manufacturer = db.Column(db.String(50))
    ip = db.Column(db.String(100))
    mac_address = db.Column(db.String(50))  # 追加
    hostname = db.Column(db.String(100))    # 追加
    port = db.Column(db.Integer)
    interval = db.Column(db.Integer)
    status = db.Column(db.String(50), default="正常")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'))  # ← id を参照
    current = db.Column(db.Float)
    temperature = db.Column(db.Float)
    pressure = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)