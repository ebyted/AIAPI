from database import SessionLocal, engine
import models, crud

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    # create_user(db, username, full_name, password)
    user = crud.create_user(db, "caleb", "caleb", "arkano")
    print("Created:", user.username, user.id)
finally:
    db.close()