from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Time, Text, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)  # Será el email
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)
    
    # Datos del onboarding
    birth_date = Column(Date, nullable=True)
    birth_place = Column(String, nullable=True)
    birth_time = Column(Time, nullable=True)
    temple_name = Column(String, nullable=True)
    emotional_state = Column(String, nullable=True)
    intention = Column(String, nullable=True)
    onboarding_completed = Column(Boolean, default=False)
    
    # Relación con mensajes
    messages = relationship("Message", back_populates="user")
    # Relación con perfil
    profile = relationship("UserProfile", back_populates="user", uselist=False)

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)  # 'user' or 'ai'
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="messages")

class UserOnboardingSession(Base):
    __tablename__ = "user_onboarding_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    
    # Datos del onboarding
    temple_name = Column(String, nullable=True)
    emotional_state = Column(String, nullable=True)
    intention = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    birth_place = Column(String, nullable=True)
    birth_time = Column(Time, nullable=True)
    
    # Agregar este campo
    welcome_message = Column(Text, nullable=True)
    
    # Control de sesión
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    is_completed = Column(Boolean, default=False)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Datos adicionales del perfil
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    timezone = Column(String, default="America/Mexico_City")
    
    # Configuraciones de notificaciones
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    meditation_reminders = Column(Boolean, default=True)
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con User
    user = relationship("User", back_populates="profile")

class HeartRateData(Base):
    __tablename__ = "heart_rate_data"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Datos del ritmo cardíaco
    heart_rate = Column(Integer)  # BPM
    recorded_at = Column(DateTime, default=datetime.utcnow)
    device_type = Column(String, default="smartwatch")  # smartwatch, manual, etc.
    
    # Contexto
    activity_type = Column(String, nullable=True)  # meditation, exercise, rest, etc.
    stress_level = Column(Integer, nullable=True)  # 1-10 scale
    
    # Relación
    user = relationship("User")

class AppEvent(Base):
    __tablename__ = "app_events"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Datos del evento
    event_type = Column(String)  # meditation_session, dialog, diary_entry, etc.
    event_name = Column(String)
    duration_minutes = Column(Float, nullable=True)
    details = Column(Text, nullable=True)  # JSON string con detalles adicionales
    
    # Metadatos
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relación
    user = relationship("User")


