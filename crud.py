from sqlalchemy.orm import Session
from passlib.context import CryptContext
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
