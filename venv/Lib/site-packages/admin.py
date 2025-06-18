import os
import aioredis
from fastapi import FastAPI
from fastapi_admin.app import app as admin_app
from fastapi_admin.providers.login import UsernamePasswordProvider
from fastapi_admin.models import Site
from tortoise.contrib.fastapi import register_tortoise  # o tu adapter SQLAlchemy

# Crea tu instancia principal de FastAPI
app = FastAPI()

# 1) Registra tu ORM (Tortoise + SQLite)
register_tortoise(
    app,
    db_url="sqlite://db.sqlite3",
    modules={"models": ["your_project.models"]},
    generate_schemas=True,
    add_exception_handlers=True,
)

# 2) Monta el admin en /admin
app.mount("/admin", admin_app)

@app.on_event("startup")
async def startup():
    # Crea pool de Redis (requerido por fastapi-admin)
    redis = await aioredis.create_redis_pool(
        os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # Inicializa el dashboard
    await admin_app.init(
        admin_secret=os.getenv("ADMIN_SECRET", "test-secret"),
        redis=redis,
        permission=True,
        site=Site(
            name="Mi Admin",
            login_description="Panel de administración",
            locale="es-ES",
            locale_switcher=True,
            theme_switcher=True,
        ),
        # Proveedor básico de login por usuario/contraseña
        providers=[
            UsernamePasswordProvider(
                admin_model="your_project.models.AdminUser",  # tu modelo de admins
                login_field="username",
                password_field="password_hash",
            )
        ],
    )
