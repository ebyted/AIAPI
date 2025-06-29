from database import SessionLocal, engine
import models, crud

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # create_user(db, username, full_name, password)
    user = crud.create_user(db, "ebyted", "ebyted", "arkano")
    print("Created:", user.username, user.id)
    
    # Crear usuario admin adicional
    admin_user = crud.create_user(db, "admin", "Administrador", "admin123")
    print("Created:", admin_user.username, admin_user.id)
    
    print("✅ Usuarios creados exitosamente")
    
finally:
    db.close()