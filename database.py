from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SensorReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    moisture = db.Column(db.Float, nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    valid_reading = db.Column(db.Boolean, default=True)
    pump_status = db.Column(db.Boolean, default=False, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'moisture': self.moisture,
            'temperature': self.temperature,
            'valid_reading': self.valid_reading,
            'pump_status': self.pump_status if self.pump_status is not None else False
        }

class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    water_needed = db.Column(db.Boolean, nullable=False)
    plant_health = db.Column(db.String(50), nullable=False)
    soil_condition = db.Column(db.String(50), nullable=False)
    recommendation = db.Column(db.String(200), nullable=False)
    is_fallback_mode = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'water_needed': self.water_needed,
            'plant_health': self.plant_health,
            'soil_condition': self.soil_condition,
            'recommendation': self.recommendation,
            'is_fallback_mode': self.is_fallback_mode
        }

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    message = db.Column(db.String(200), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False) # e.g., 'Sensor Failure', 'Dry Soil', 'High Temp'
    resolved = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'message': self.message,
            'alert_type': self.alert_type,
            'resolved': self.resolved
        }

class IrrigationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, default=0)
    trigger_type = db.Column(db.String(50), default="Automatic") # "Automatic" or "Manual Override"
    start_moisture = db.Column(db.Float, nullable=True)
    end_moisture = db.Column(db.Float, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else None,
            'end_time': self.end_time.strftime('%Y-%m-%d %H:%M:%S') if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'trigger_type': self.trigger_type,
            'start_moisture': self.start_moisture,
            'end_moisture': self.end_moisture
        }
