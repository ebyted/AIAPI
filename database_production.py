import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL of the database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./milo.db")

# Configuración específica según el tipo de BD
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Cambiar a True solo para debug
    )
elif DATABASE_URL.startswith("postgresql"):
    # PostgreSQL configuration (recomendado para producción)
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=0,
        pool_pre_ping=True,
        echo=False
    )
else:
    # Configuración genérica
    engine = create_engine(
        DATABASE_URL,
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Test connection
def test_connection():
    try:
        with engine.connect() as connection:
            print("✅ Database connection successful")
            return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    test_connection()
