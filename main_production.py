import os
import logging
from prompts import get_prompt_by_mode, PROMPTS

from datetime import datetime, timedelta
from typing import Optional, Generator

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from fastapi import FastAPI, Depends, HTTPException, status, Request, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from jose import JWTError, jwt
from sqlalchemy.orm import Session

import models
import crud
from database import SessionLocal, engine
from models import AdminUser

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Configuración de OpenAI con validación
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY no encontrada en variables de entorno")
    raise ValueError("OPENAI_API_KEY es requerida")

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Configuración con validación
MILO_MODEL_ID = os.getenv("MILO_MODEL_ID", "gpt-3.5-turbo")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
if SECRET_KEY == "supersecretkey":
    logger.warning("⚠️ Usando SECRET_KEY por defecto. Cambia esto en producción!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Milo API", version="1.0")

# Configuración CORS mejorada para producción
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []

# En desarrollo, agregar localhost
if ENVIRONMENT == "development":
    ALLOWED_ORIGINS.extend([
        "http://localhost:8007",
        "http://localhost:3000",
        "http://127.0.0.1:8011",
        "http://127.0.0.1:55627"
    ])

# Eliminar orígenes vacíos
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS if origin.strip()]

if not ALLOWED_ORIGINS:
    logger.warning("⚠️ No hay orígenes CORS configurados!")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Instrumentación opcional en producción
if ENVIRONMENT == "development":
    Instrumentator().instrument(app).expose(app)

# Servir archivos estáticos de forma segura
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except Exception as e:
    logger.error(f"Error montando archivos estáticos: {e}")

from fastapi.templating import Jinja2Templates

try:
    templates = Jinja2Templates(directory="templates")
except Exception as e:
    logger.error(f"Error configurando templates: {e}")
    templates = None

# Model classes
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    password: str

class GenerateRequest(BaseModel):
    prompt: str
    mode: str  # text | audio | links

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    user = crud.get_user(db, username)
    if not user:
        raise exc
    return user

@app.get("/", include_in_schema=False)
async def serve_index():
    if templates:
        template_path = os.path.join("templates", "index.html")
        if os.path.exists(template_path):
            return FileResponse(template_path)
    return {"message": "BeCalm API", "status": "running", "docs": "/docs"}

@app.get("/health", summary="Health Check")
async def health():
    return {
        "status": "running", 
        "message": "Milo API is operational",
        "environment": ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/token", include_in_schema=False)
async def token_get():
    return JSONResponse({"detail": "Use POST /token to authenticate"}, status_code=200)

@app.get("/menu", response_class=HTMLResponse)
async def menu(request: Request):
    if templates:
        return templates.TemplateResponse("menu.html", {"request": request})
    return HTMLResponse("<h1>Menu not available</h1>")

@app.get("/dialogo_sagrado", response_class=HTMLResponse)
async def dialogo_sagrado(request: Request):
    if templates:
        return templates.TemplateResponse("dialogo_sagrado.html", {"request": request})
    return HTMLResponse("<h1>Dialogo Sagrado not available</h1>")

@app.get("/dialogo_conmigo/history")
async def history(days: int = 2, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    msgs = crud.get_messages(db, current_user.id, days)
    return [{"role": m.role, "content": m.content, "timestamp": m.timestamp.isoformat()} for m in msgs]

@app.post("/dialogo_conmigo/message")
async def save_and_generate(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        # Guarda el mensaje del usuario
        crud.create_message(db, user.id, 'user', req.prompt)

        # Usa la lógica de generación de AIAPI
        prompt_to_use = req.prompt
        if req.mode in PROMPTS:
            user_vars = {
                "full_name": user.full_name,
                "username": user.username
            }
            prompt_text = get_prompt_by_mode(req.mode, user_vars, prompt_to_use)
            resp = client.chat.completions.create(
                model=MILO_MODEL_ID,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.7,
                max_tokens=250
            )
            resp_text = resp.choices[0].message.content.strip()
        else:
            resp = client.chat.completions.create(
                model=MILO_MODEL_ID,
                messages=[{"role": "user", "content": prompt_to_use}],
                temperature=0.7,
                max_tokens=250
            )
            resp_text = resp.choices[0].message.content.strip()

        # Guarda la respuesta de la IA
        crud.create_message(db, user.id, 'ai', resp_text)
        return {"text": resp_text}
    except Exception as e:
        logger.error(f"Error en dialogo_conmigo/message: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/diario_vivo", response_class=HTMLResponse)
async def diario_vivo(request: Request):
    if templates:
        return templates.TemplateResponse("diario_vivo.html", {"request": request})
    return HTMLResponse("<h1>Diario Vivo not available</h1>")

@app.get("/mensajes_del_alma", response_class=HTMLResponse)
async def mensajes_del_alma(request: Request):
    if templates:
        return templates.TemplateResponse("mensajes_del_alma.html", {"request": request})
    return HTMLResponse("<h1>Mensajes del Alma not available</h1>")

@app.get("/medita_conmigo", response_class=HTMLResponse)
async def medita_conmigo(request: Request):
    if templates:
        return templates.TemplateResponse("medita_conmigo.html", {"request": request})
    return HTMLResponse("<h1>Medita Conmigo not available</h1>")

@app.get("/mapa_interior", response_class=HTMLResponse)
async def mapa_interior(request: Request):
    if templates:
        return templates.TemplateResponse("mapa_interior.html", {"request": request})
    return HTMLResponse("<h1>Mapa Interior not available</h1>")

@app.get("/ritual_diario", response_class=HTMLResponse)
async def ritual_diario(request: Request):
    if templates:
        return templates.TemplateResponse("ritual_diario.html", {"request": request})
    return HTMLResponse("<h1>Ritual Diario not available</h1>")

@app.get("/silencio_sagrado", response_class=HTMLResponse)
async def silencio_sagrado(request: Request):
    if templates:
        return templates.TemplateResponse("silencio_sagrado.html", {"request": request})
    return HTMLResponse("<h1>Silencio Sagrado not available</h1>")

@app.post("/register", status_code=201)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        if crud.get_user(db, user.username):
            raise HTTPException(status_code=400, detail="Username already registered")
        crud.create_user(db, user.username, user.full_name or "", user.password)
        return {"msg": f"User {user.username} created"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en register: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        user = crud.authenticate_user(db, form_data.username, form_data.password)
        if not user:
            logger.warning(f"Authentication failed for user {form_data.username}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        token = jwt.encode({"sub": user.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en login: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

# ------------------- MENÚ PROTEGIDO CON ROUTER -------------------

menu_router = APIRouter(
    prefix="/menu",
    dependencies=[Depends(get_current_user)],
    tags=["menu"]
)

@menu_router.get("/opcion1")
async def menu_opcion1():
    return {"msg": "Accediste a la opción 1"}

@menu_router.get("/opcion2")
async def menu_opcion2():
    return {"msg": "Accediste a la opción 2"}

@menu_router.get("/opcion3")
async def menu_opcion3():
    return {"msg": "Accediste a la opción 3"}

# Agrega aquí todas las opciones de menú que quieras proteger

app.include_router(menu_router)

# ------------------- FIN MENÚ PROTEGIDO -------------------

@app.post("/meditation/music")
async def get_meditation_music(
    req: GenerateRequest,
    current_user: models.User = Depends(get_current_user)
):
    try:
        # Usar el endpoint de Playlist que ya tienes
        if req.mode == "Playlist":
            tracks = []
            playlist_file = "lista_meditacion.txt"
            if os.path.exists(playlist_file):
                with open(playlist_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= 5: break  # Máximo 5 canciones
                        if line.strip():
                            tracks.append(line.strip())
            if not tracks:
                tracks = [
                    "Ludovico Einaudi - Nuvole Bianche",
                    "Max Richter - On The Nature of Daylight",
                    "Ólafur Arnalds - Near Light"
                ]
            return {"tracks": tracks}
        else:
            # Generar recomendaciones con IA
            prompt_text = f"Recomienda 5 canciones instrumentales relajantes para meditación de {req.prompt}. Lista solo los nombres."
            resp = client.chat.completions.create(
                model=MILO_MODEL_ID,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.7,
                max_tokens=200
            )
            
            # Parsear la respuesta en una lista
            response_text = resp.choices[0].message.content.strip()
            tracks = [track.strip() for track in response_text.split('\n') if track.strip()]
            
            return {"tracks": tracks[:5]}  # Máximo 5 canciones
            
    except Exception as e:
        logger.error(f"Error en meditation/music: {e}")
        # Fallback con canciones predefinidas
        fallback_tracks = [
            "Sonidos del Océano - Meditación Profunda",
            "Bosque Encantado - Música Ambient", 
            "Lluvia Suave - Relajación Total",
            "Campanas Tibetanas - Armonía Interior",
            "Naturaleza Serena - Paz Mental"
        ]
        return {"tracks": fallback_tracks}

@app.post("/v1/generate")
@limiter.limit("5/minute")
async def generate(
    request: Request,
    req: GenerateRequest,
    current_user: models.User = Depends(get_current_user),
    promptstr: Optional[str] = None
):
    try:
        logger.info(f"User {current_user.username} requested mode={req.mode}")
        prompt_to_use = promptstr if promptstr is not None else req.prompt

        if req.mode in PROMPTS:
            user_vars = {
                "full_name": current_user.full_name,
                "username": current_user.username
            }
            prompt_text = get_prompt_by_mode(req.mode, user_vars, prompt_to_use)
            resp = client.chat.completions.create(
                model=MILO_MODEL_ID,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.7,
                max_tokens=250
            )
            return {"text": resp.choices[0].message.content.strip()}

        if req.mode == "text":
            resp = client.chat.completions.create(
                model=MILO_MODEL_ID,
                messages=[{"role": "user", "content": prompt_to_use}],
                temperature=0.7,
                max_tokens=250
            )
            return {"text": resp.choices[0].message.content.strip()}
        elif req.mode == "audio":
            audio_resp = client.audio.speech.create(model="tts-1", input=prompt_to_use, voice="alloy", format="mp3")
            return {"audio_base64": audio_resp.audio}
        elif req.mode == "Playlist":
            tracks = []
            playlist_file = "lista.txt"
            if os.path.exists(playlist_file):
                with open(playlist_file, "r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= 5: break
                        if line.strip():
                            tracks.append(line.strip())
            return {"tracks": tracks}
        else:
            raise HTTPException(status_code=400, detail="Invalid mode")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en v1/generate: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 para producción
    port = int(os.getenv("PORT", "8011"))
    
    logger.info(f"🚀 Starting Milo API at http://{host}:{port}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Allowed Origins: {ALLOWED_ORIGINS}")
    
    uvicorn.run("main:app", host=host, port=port, log_level="info", reload=(ENVIRONMENT == "development"))
