# src/models/ecs/data_schemas.py
from pydantic import BaseModel, Field
from typing import List
from src.models.ecs.taxonomy import DataKey

# Сыро!

# --- 1. Material Schemas ---

class PhysicsData(BaseModel):
    """Данные для atoms: scale, density"""
    # Используем alias, чтобы в JSON ключи были стандартизированы (val_mass_kg), 
    # но в коде мы обращались удобно (data.mass)
    mass: float = Field(alias=DataKey.MASS, default=1.0)
    volume: float = Field(alias=DataKey.VOLUME, default=1.0)
    density: float = Field(alias=DataKey.DENSITY, default=1000.0)

class KineticData(BaseModel):
    """Данные для atoms: kinetics"""
    velocity: List[float] = Field(alias=DataKey.VELOCITY, default_factory=lambda: [0.0, 0.0, 0.0]) # x y z

class ThermalData(BaseModel):
    """Данные для atoms: thermal"""
    temperature: float = Field(alias=DataKey.TEMPERATURE, default=20.0) # 20°C

# --- 2. Vitality Schemas ---

class HealthData(BaseModel):
    """Данные для atoms: resilience"""
    current: float = Field(alias=DataKey.HEALTH_CURRENT, default=100.0)
    max_val: float = Field(alias=DataKey.HEALTH_MAX, default=100.0)

class SensoryData(BaseModel):
    """Данные для atoms: perception"""
    range_m: float = Field(alias=DataKey.SENSORY_RANGE, default=20.0)
    stealth_detection: float = 0.0 # Специфичное поле, можно без алиаса если оно редкое

# --- 3. Cognitive / Info Schemas ---

class InformationData(BaseModel):
    """Данные для atoms: information"""
    accuracy: float = Field(alias=DataKey.ACCURACY, default=1.0, ge=0.0, le=1.0)
    is_secret: bool = False
    topic_vector: List[float] = Field(default_factory=list) # О чем эта информация?
    