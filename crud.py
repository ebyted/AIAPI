from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from AIAPI import models
import uuid  # <-- Añadido
import os    # <-- Añadido
from openai import OpenAI # <-- Añadido

# --- Configuración de OpenAI (Añadido) ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MILO_MODEL_ID = os.getenv("MILO_MODEL_ID", "gpt-3.5-turbo")
# -----------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, username: str, full_name: str, password: str):
    hashed = pwd_context.hash(password)
    db_user = models.User(
        username=username,
        full_name=full_name,
        hashed_password=hashed
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    user = get_user(db, username)
    if not user or not pwd_context.verify(password, user.hashed_password):
        return None
    return user

# Message CRUD functions
def get_messages(db: Session, user_id: int, days: int = 7):
    """Get messages for a user from the last N days"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    return db.query(models.Message).filter(
        models.Message.user_id == user_id,
        models.Message.timestamp >= cutoff_date
    ).order_by(models.Message.timestamp.desc()).all()

def create_message(db: Session, user_id: int, role: str, content: str):
    """Create a new message"""
    db_message = models.Message(
        user_id=user_id,
        role=role,
        content=content,
        timestamp=datetime.utcnow()
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

# Onboarding Session CRUD functions
def create_onboarding_session(db: Session):
    """Crear nueva sesión de onboarding (CORREGIDO)"""
    session = models.UserOnboardingSession(
        session_id=str(uuid.uuid4()),
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def get_onboarding_session(db: Session, session_id: str):
    """Obtener sesión de onboarding por ID"""
    session = db.query(models.UserOnboardingSession).filter(
        models.UserOnboardingSession.session_id == session_id
    ).first()
    
    if session and session.is_expired:
        # Sesión expirada, eliminar
        db.delete(session)
        db.commit()
        return None
    
    return session

def update_onboarding_session(db: Session, session_id: str, **kwargs):
    """Actualizar datos de sesión de onboarding"""
    session = get_onboarding_session(db, session_id)
    if not session:
        return None
    
    for key, value in kwargs.items():
        if hasattr(session, key):
            setattr(session, key, value)
    
    db.commit()
    db.refresh(session)
    return session

def complete_onboarding_session(db: Session, session_id: str):
    """Marcar sesión como completa"""
    session = get_onboarding_session(db, session_id)
    if not session:
        return None
    
    # Verificar si todos los campos requeridos están presentes
    required_fields = [
        session.full_name,
        session.birth_date,
        session.birth_place,
        session.temple_name,
        session.emotional_state,
        session.intention
    ]
    
    if all(required_fields):
        session.is_complete = True
        session.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
    
    return session

def transfer_onboarding_to_user(db: Session, session_id: str, email: str, password: str):
    """Transferir datos de onboarding a un nuevo usuario"""
    session = get_onboarding_session(db, session_id)
    if not session or not session.is_complete:
        return None
    
    # Verificar que el email no exista
    existing_user = get_user(db, email)
    if existing_user:
        return None
    
    # Crear usuario con datos del onboarding
    hashed = pwd_context.hash(password)
    user = models.User(
        username=email,  # Email como username
        full_name=session.full_name,
        hashed_password=hashed,
        birth_date=session.birth_date,
        birth_place=session.birth_place,
        birth_time=session.birth_time,
        temple_name=session.temple_name,
        emotional_state=session.emotional_state,
        intention=session.intention,
        onboarding_completed=True
    )
    
    db.add(user)
    
    # Eliminar sesión de onboarding
    db.delete(session)
    
    db.commit()
    db.refresh(user)
    return user

def is_onboarding_complete(session):
    """Verificar si el onboarding está completo"""
    required_fields = [
        ('full_name', session.full_name),
        ('birth_date', session.birth_date),
        ('birth_place', session.birth_place),
        ('temple_name', session.temple_name),
        ('emotional_state', session.emotional_state),
        ('intention', session.intention)
    ]
    
    missing = [field for field, value in required_fields if not value]
    progress = ((len(required_fields) - len(missing)) / len(required_fields)) * 100
    
    return len(missing) == 0, missing, int(progress)

def cleanup_expired_sessions(db: Session):
    """Limpiar sesiones expiradas"""
    expired_sessions = db.query(models.UserOnboardingSession).filter(
        models.UserOnboardingSession.expires_at < datetime.utcnow()
    ).all()
    
    for session in expired_sessions:
        db.delete(session)
    
    db.commit()
    return len(expired_sessions)

# --- Función de IA (Añadido al final) ---
def generate_welcome_message(session: models.UserOnboardingSession) -> str:
    """
    Llama a la API de OpenAI para generar un mensaje de bienvenida personalizado.
    """
    prompt = (
        f"Eres Milo, un guía espiritual sereno y compasivo. "
        f"Escribe un mensaje de bienvenida corto (2-3 frases) para una persona llamada {session.full_name or 'alguien especial'}. "
        f"Actualmente se siente '{session.emotional_state or 'en un estado de reflexión'}' y su intención al usar la app es '{session.intention or 'encontrar paz'}'. "
        f"El mensaje debe ser cálido, inspirador y reconocer sus sentimientos e intenciones sin ser demasiado directo. "
        f"Haz que se sienta visto/a y bienvenido/a a este espacio sagrado. No incluyas saludos como 'Hola' o 'Bienvenido/a'."
    )

    try:
        completion = client.chat.completions.create(
            model=MILO_MODEL_ID,
            messages=[
                {"role": "system", "content": "Eres un guía espiritual llamado Milo. Tus respuestas son serenas, breves y profundas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error al llamar a OpenAI: {e}")
        return f"Bienvenido/a a tu espacio sagrado, {session.full_name or 'viajero/a'}. Que aquí encuentres la serenidad y la guía que buscas."
