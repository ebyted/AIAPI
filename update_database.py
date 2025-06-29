import os
from database import engine
import models
import crud
from database import SessionLocal

print("🗄️ Actualizando base de datos con nuevos modelos...")

# Eliminar archivo de base de datos antigua si existe
if os.path.exists("milo.db"):
    os.remove("milo.db")
    print("✅ Base de datos antigua eliminada")

# Crear todas las tablas con la estructura nueva
models.Base.metadata.create_all(bind=engine)
print("✅ Nuevas tablas creadas con estructura correcta")

# Recrear usuarios
db = SessionLocal()
try:
    # Crear usuarios
    user1 = crud.create_user(db, "ebyted", "ebyted", "arkano")
    print(f"✅ Usuario '{user1.username}' creado con ID: {user1.id}")
    
    user2 = crud.create_user(db, "admin", "Administrador", "admin123")
    print(f"✅ Usuario '{user2.username}' creado con ID: {user2.id}")
    
    print("🎉 Base de datos actualizada completamente")
    
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()