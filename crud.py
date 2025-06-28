from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
import models

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
