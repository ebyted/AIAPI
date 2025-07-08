from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import List, Optional
from AIAPI import models
import AIAPI.crud as crud
import json
import random

# ============= USER PROFILE CRUD =============

def get_user_profile(db: Session, user_id: int):
    """Obtener perfil del usuario"""
    return db.query(models.UserProfile).filter(models.UserProfile.user_id == user_id).first()

def create_user_profile(db: Session, user_id: int, **kwargs):
    """Crear perfil del usuario"""
    db_profile = models.UserProfile(user_id=user_id, **kwargs)
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

def update_user_profile(db: Session, user_id: int, **kwargs):
    """Actualizar perfil del usuario"""
    db_profile = get_user_profile(db, user_id)
    if not db_profile:
        return create_user_profile(db, user_id, **kwargs)
    
    for key, value in kwargs.items():
        if hasattr(db_profile, key):
            setattr(db_profile, key, value)
    
    db_profile.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_profile)
    return db_profile

# ============= USER DATA CRUD =============

def update_user_onboarding_data(db: Session, user_id: int, **kwargs):
    """Actualizar datos de onboarding del usuario"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    
    # Campos editables del onboarding
    editable_fields = [
        'full_name', 'birth_date', 'birth_place', 'birth_time',
        'temple_name', 'emotional_state', 'intention'
    ]
    
    for key, value in kwargs.items():
        if key in editable_fields and hasattr(user, key):
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

def change_user_password(db: Session, user_id: int, new_password: str):
    """Cambiar contraseña del usuario"""
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return None
    
    user.hashed_password = pwd_context.hash(new_password)
    db.commit()
    db.refresh(user)
    return user

# ============= HEART RATE DATA CRUD =============

def create_heart_rate_data(db: Session, user_id: int, heart_rate: int, **kwargs):
    """Crear registro de ritmo cardíaco"""
    db_hr = models.HeartRateData(
        user_id=user_id,
        heart_rate=heart_rate,
        **kwargs
    )
    db.add(db_hr)
    db.commit()
    db.refresh(db_hr)
    return db_hr

def get_heart_rate_history(db: Session, user_id: int, days: int = 7):
    """Obtener historial de ritmo cardíaco"""
    start_date = datetime.utcnow() - timedelta(days=days)
    return db.query(models.HeartRateData).filter(
        models.HeartRateData.user_id == user_id,
        models.HeartRateData.recorded_at >= start_date
    ).order_by(desc(models.HeartRateData.recorded_at)).all()

def get_heart_rate_stats(db: Session, user_id: int, days: int = 7):
    """Obtener estadísticas de ritmo cardíaco"""
    heart_rates = get_heart_rate_history(db, user_id, days)
    
    if not heart_rates:
        return None
    
    hr_values = [hr.heart_rate for hr in heart_rates]
    
    return {
        "average": round(sum(hr_values) / len(hr_values), 1),
        "min": min(hr_values),
        "max": max(hr_values),
        "current": hr_values[0] if hr_values else None,
        "total_readings": len(hr_values)
    }

# ============= APP EVENTS CRUD =============

def create_app_event(db: Session, user_id: int, event_type: str, event_name: str, **kwargs):
    """Crear evento de la app"""
    db_event = models.AppEvent(
        user_id=user_id,
        event_type=event_type,
        event_name=event_name,
        **kwargs
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

def get_app_events_history(db: Session, user_id: int, days: int = 30, event_type: str = None):
    """Obtener historial de eventos"""
    start_date = datetime.utcnow() - timedelta(days=days)
    query = db.query(models.AppEvent).filter(
        models.AppEvent.user_id == user_id,
        models.AppEvent.created_at >= start_date
    )
    
    if event_type:
        query = query.filter(models.AppEvent.event_type == event_type)
    
    return query.order_by(desc(models.AppEvent.created_at)).all()

def get_dashboard_stats(db: Session, user_id: int, days: int = 7):
    """Obtener estadísticas del dashboard"""
    events = get_app_events_history(db, user_id, days)
    hr_stats = get_heart_rate_stats(db, user_id, days)
    
    # Contar eventos por tipo
    event_counts = {}
    total_meditation_time = 0
    
    for event in events:
        event_type = event.event_type
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        
        if event_type == "meditation_session" and event.duration_minutes:
            total_meditation_time += event.duration_minutes
    
    return {
        "period_days": days,
        "total_events": len(events),
        "event_counts": event_counts,
        "total_meditation_minutes": round(total_meditation_time, 1),
        "heart_rate_stats": hr_stats,
        "most_used_feature": max(event_counts, key=event_counts.get) if event_counts else None
    }

# ============= FUNCIONES DE SIMULACIÓN =============

def simulate_heart_rate_data(db: Session, user_id: int, days: int = 7):
    """Simular datos de ritmo cardíaco para testing"""
    base_hr = random.randint(60, 80)  # BPM base
    created_count = 0
    
    for i in range(days * 24):  # Una lectura por hora
        timestamp = datetime.utcnow() - timedelta(hours=i)
        
        # Simular variaciones naturales
        if 6 <= timestamp.hour <= 22:  # Día activo
            hr = base_hr + random.randint(-5, 15)
            activity = random.choice(["rest", "light_activity", "meditation", "exercise"])
        else:  # Noche (sueño)
            hr = base_hr + random.randint(-10, 0)
            activity = "sleep"
        
        create_heart_rate_data(
            db, user_id, hr,
            activity_type=activity,
            stress_level=random.randint(1, 5),
            recorded_at=timestamp
        )
        created_count += 1
    
    return created_count

def simulate_app_events(db: Session, user_id: int, days: int = 30):
    """Simular eventos de la app para testing"""
    event_types = [
        ("meditation_session", "Meditación Guiada"),
        ("dialog", "Diálogo Sagrado"),
        ("diary_entry", "Entrada de Diario"),
        ("silence_session", "Silencio Sagrado"),
        ("inner_map", "Exploración del Mapa Interior")
    ]
    
    created_count = 0
    for i in range(days * 3):  # ~3 eventos por día
        timestamp = datetime.utcnow() - timedelta(days=random.randint(0, days))
        event_type, event_name = random.choice(event_types)
        
        duration = None
        if event_type in ["meditation_session", "silence_session"]:
            duration = random.randint(5, 30)  # 5-30 minutos
        
        create_app_event(
            db, user_id, event_type, event_name,
            duration_minutes=duration,
            details=json.dumps({"simulated": True}),
            created_at=timestamp
        )
        created_count += 1
    
    return created_count