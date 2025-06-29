from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Date, Time
from sqlalchemy.orm import relationship, Session
from database import Base
from datetime import datetime, timedelta, timezone
import uuid

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

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_superuser = Column(Boolean, default=True)

class Message(Base):
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role = Column(String, nullable=False)      # 'user' o 'ai'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Relación con usuario
    user = relationship("User", back_populates="messages")

class UserOnboardingSession(Base):
    __tablename__ = "user_onboarding_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)
    
    # Datos del onboarding
    full_name = Column(String, nullable=True)
    birth_date = Column(Date, nullable=True)
    birth_place = Column(String, nullable=True)
    birth_time = Column(Time, nullable=True)  # Opcional
    temple_name = Column(String, nullable=True)
    emotional_state = Column(String, nullable=True)
    intention = Column(String, nullable=True)
    
    # Control
    is_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=False)  # 24 horas después de created_at
    
    # Mensaje de bienvenida generado
    welcome_message = Column(Text, nullable=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.session_id:
            self.session_id = str(uuid.uuid4())
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(hours=24)
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


