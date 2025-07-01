import os
import logging
from prompts import get_prompt_by_mode, PROMPTS

from datetime import datetime, timedelta
from typing import Optional, Generator, List, Dict, Any

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
from datetime import date, time
import uuid

import models
import crud
import crud_profile
from database import SessionLocal, engine
from models import AdminUser

# Create database tables
models.Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Configuración de OpenAI con validación
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY no encontrada en variables de entorno")
    raise ValueError("OPENAI_API_KEY es requerida")

client = OpenAI(api_key=OPENAI_API_KEY)

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

# Onboarding Models
class OnboardingStartResponse(BaseModel):
    session_id: str
    message: str

class OnboardingTempleRequest(BaseModel):
    session_id: str
    temple_name: str

class OnboardingEmotionalStateRequest(BaseModel):
    session_id: str
    emotional_state: str

class OnboardingIntentionRequest(BaseModel):
    session_id: str
    intention: str

class OnboardingPersonalDataRequest(BaseModel):
    session_id: str
    full_name: str
    birth_date: str  # YYYY-MM-DD
    birth_place: str
    birth_time: Optional[str] = None  # HH:MM

class OnboardingCompleteRegistrationRequest(BaseModel):
    session_id: str
    email: str
    password: str

class OnboardingStatusResponse(BaseModel):
    is_complete: bool
    missing_fields: List[str]
    progress_percentage: int
    current_step: str
    expires_at: str

class WelcomeMessageResponse(BaseModel):
    welcome_message: str
    session_id: str

class WelcomeMessageRequest(BaseModel):
    session_id: str

# Constantes para opciones predefinidas
EMOTIONAL_STATES = [
    "En paz",
    "Ansioso", 
    "Esperanzado",
    "Confundido",
    "Alegre",
    "Melancólico",
    "Sereno",
    "Inquieto",
    "Agradecido",
    "Nostálgico"
]

INTENTIONS = [
    "Silencio",
    "Guía", 
    "Solo estar un momento",
    "Acompañamiento suave"
]

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def generate_welcome_message(session) -> str:
    """Generar mensaje de bienvenida personalizado con IA"""
    try:
        prompt = f"""Actúa como una guía espiritual amorosa. Genera un mensaje de bienvenida personalizado y emotivo para alguien que acaba de completar su ritual de entrada a su templo interior.

Datos de la persona:
- Nombre: {session.full_name}
- Templo interior: {session.temple_name}
- Estado emocional actual: {session.emotional_state}
- Intención: {session.intention}

El mensaje debe ser:
- Cálido y espiritual
- Máximo 4-5 líneas
- Que reconozca su templo y su estado actual
- Que los invite a entrar a su espacio sagrado

No uses emojis. Habla directo al alma."""

        resp = client.chat.completions.create(
            model=MILO_MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=200
        )
        
        return resp.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generando mensaje de bienvenida: {e}")
        # Mensaje de fallback
        return f"Bienvenido/a {session.full_name} a tu templo {session.temple_name}. Tu espacio sagrado te espera con serenidad. Es tiempo de conectar contigo mismo/a."

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

# ------------------- ONBOARDING ENDPOINTS (SIN AUTENTICACIÓN) -------------------

def create_onboarding_session_fixed(db: Session):
    """Crear sesión de onboarding con session_id único"""
    session_id = str(uuid.uuid4())
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=24)
    session = models.UserOnboardingSession(
        session_id=session_id,
        created_at=now,
        expires_at=expires_at,
        is_completed=False
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@app.post("/onboarding/start", response_model=OnboardingStartResponse, tags=["onboarding"])
async def start_onboarding(db: Session = Depends(get_db)):
    """Iniciar nueva sesión de onboarding"""
    try:
        logger.info("Limpiando sesiones expiradas...")
        crud.cleanup_expired_sessions(db)
        logger.info("Creando nueva sesión de onboarding...")
        # Usa la función corregida
        session = create_onboarding_session_fixed(db)
        logger.info(f"Sesión creada: {session.session_id}")
        return OnboardingStartResponse(
            session_id=session.session_id,
            message="Sesión de onboarding iniciada. Bienvenido a tu espacio sagrado."
        )
    except Exception as e:
        logger.error(f"Error iniciando onboarding: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

@app.post("/onboarding/temple", tags=["onboarding"])
async def save_temple_name(
    request: OnboardingTempleRequest,
    db: Session = Depends(get_db)
):
    """Guardar nombre del templo interior"""
    try:
        session = crud.update_onboarding_session(
            db, 
            request.session_id, 
            temple_name=request.temple_name
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        return {"message": f"Templo '{request.temple_name}' guardado exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando templo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/onboarding/emotional-state", tags=["onboarding"])
async def save_emotional_state(
    request: OnboardingEmotionalStateRequest,
    db: Session = Depends(get_db)
):
    """Guardar estado emocional actual"""
    try:
        if request.emotional_state not in EMOTIONAL_STATES:
            raise HTTPException(
                status_code=400, 
                detail=f"Estado emocional inválido. Opciones: {EMOTIONAL_STATES}"
            )
        
        session = crud.update_onboarding_session(
            db,
            request.session_id,
            emotional_state=request.emotional_state
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        return {"message": f"Estado emocional '{request.emotional_state}' guardado exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando estado emocional: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/onboarding/intention", tags=["onboarding"])
async def save_intention(
    request: OnboardingIntentionRequest,
    db: Session = Depends(get_db)
):
    """Guardar intención de uso de la app"""
    try:
        if request.intention not in INTENTIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Intención inválida. Opciones: {INTENTIONS}"
            )
        
        session = crud.update_onboarding_session(
            db,
            request.session_id,
            intention=request.intention
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        return {"message": f"Intención '{request.intention}' guardada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando intención: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/onboarding/personal-data", tags=["onboarding"])
async def save_personal_data(
    request: OnboardingPersonalDataRequest,
    db: Session = Depends(get_db)
):
    """Guardar datos personales"""
    try:
        # Validar formato de fecha
        try:
            birth_date = datetime.strptime(request.birth_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
        # Validar formato de hora si se proporciona
        birth_time = None
        if request.birth_time:
            try:
                birth_time = datetime.strptime(request.birth_time, "%H:%M").time()
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de hora inválido. Use HH:MM")
        
        session = crud.update_onboarding_session(
            db,
            request.session_id,
            full_name=request.full_name,
            birth_date=birth_date,
            birth_place=request.birth_place,
            birth_time=birth_time
        )
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        return {"message": "Datos personales guardados exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error guardando datos personales: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/onboarding/status/{session_id}", response_model=OnboardingStatusResponse, tags=["onboarding"])
async def get_onboarding_status(session_id: str, db: Session = Depends(get_db)):
    """Verificar estado del onboarding"""
    try:
        session = crud.get_onboarding_session(db, session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        is_complete, missing_fields, progress = crud.is_onboarding_complete(session)
        
        # Determinar paso actual
        if not session.temple_name:
            current_step = "temple_name"
        elif not session.emotional_state:
            current_step = "emotional_state"
        elif not session.intention:
            current_step = "intention"
        elif not session.full_name or not session.birth_date or not session.birth_place:
            current_step = "personal_data"
        elif not is_complete:
            current_step = "review"
        else:
            current_step = "complete"
        
        return OnboardingStatusResponse(
            is_complete=is_complete,
            missing_fields=missing_fields,
            progress_percentage=progress,
            current_step=current_step,
            expires_at=session.expires_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verificando estado: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/onboarding/generate-welcome", tags=["onboarding"])
async def get_or_generate_welcome_message(
    request: WelcomeMessageRequest, 
    db: Session = Depends(get_db)
):
    """
    Obtiene o genera un mensaje de bienvenida personalizado con IA para la sesión de onboarding.
    """
    logger.info(f"Recibida petición para generar mensaje para session_id: {request.session_id}")
    
    if not request.session_id:
        logger.error("La petición llegó con un session_id NULO o VACÍO.")
        raise HTTPException(status_code=400, detail="session_id es requerido.")

    try:
        session = crud.get_onboarding_session(db, request.session_id)
        if not session:
            logger.warning(f"No se encontró sesión para el id: {request.session_id}")
            raise HTTPException(status_code=404, detail="Sesión de onboarding no encontrada o expirada.")

        if session.welcome_message:
            logger.info(f"Devolviendo mensaje existente para la sesión.")
            return {"welcome_message": session.welcome_message}

        logger.info(f"Llamando a la función de IA para generar nuevo mensaje...")
        
        # --- CORRECCIÓN CLAVE: Se elimina 'await' ---
        welcome_message = crud.generate_welcome_message(session)
        
        if not welcome_message:
            logger.error(f"La función de IA no pudo generar un mensaje.")
            raise HTTPException(status_code=500, detail="No se pudo generar el mensaje de bienvenida desde el servicio de IA.")

        logger.info(f"Mensaje generado. Actualizando la sesión en la BD.")
        crud.update_onboarding_session(
            db, 
            session_id=request.session_id, 
            welcome_message=welcome_message
        )

        return {"welcome_message": welcome_message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Excepción no controlada en /generate-welcome: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno del servidor al procesar la solicitud.")

@app.post("/onboarding/complete-registration", status_code=201, tags=["onboarding"])
async def complete_registration(
    request: OnboardingCompleteRegistrationRequest,
    db: Session = Depends(get_db)
):
    """Completar registro con email y contraseña"""
    try:
        session = crud.get_onboarding_session(db, request.session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Sesión no encontrada o expirada")
        
        is_complete, missing_fields, _ = crud.is_onboarding_complete(session)
        if not is_complete:
            raise HTTPException(
                status_code=400, 
                detail=f"Onboarding incompleto. Campos faltantes: {missing_fields}"
            )
        
        # Crear usuario final
        user = crud.transfer_onboarding_to_user(
            db,
            request.session_id,
            request.email,
            request.password
        )
        
        if not user:
            raise HTTPException(status_code=400, detail="Email ya registrado o sesión inválida")
        
        return {
            "message": f"Usuario {user.username} creado exitosamente",
            "user_id": user.id,
            "temple_name": user.temple_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completando registro: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/onboarding/options", tags=["onboarding"])
async def get_onboarding_options():
    """Obtener opciones disponibles para onboarding"""
    return {
        "emotional_states": EMOTIONAL_STATES,
        "intentions": INTENTIONS
    }

# ------------------- FIN ONBOARDING ENDPOINTS -------------------

@app.get("/user/onboarding-status", tags=["user"])
async def get_user_onboarding_status(
    current_user: models.User = Depends(get_current_user)
):
    """Verificar estado de onboarding de usuario autenticado"""
    return {
        "onboarding_completed": current_user.onboarding_completed,
        "temple_name": current_user.temple_name,
        "emotional_state": current_user.emotional_state,
        "intention": current_user.intention,
        "birth_date": current_user.birth_date.isoformat() if current_user.birth_date else None,
        "birth_place": current_user.birth_place,
        "birth_time": current_user.birth_time.isoformat() if current_user.birth_time else None
    }

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

# Agregar después de los modelos Pydantic existentes

class UserProfileResponse(BaseModel):
    id: int
    user_id: int
    avatar_url: Optional[str]
    bio: Optional[str]
    phone: Optional[str]
    timezone: str
    email_notifications: bool
    push_notifications: bool
    meditation_reminders: bool
    created_at: datetime
    updated_at: datetime

class UserProfileUpdate(BaseModel):
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    timezone: Optional[str] = None
    email_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    meditation_reminders: Optional[bool] = None

class UserOnboardingUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[str] = None  # YYYY-MM-DD
    birth_place: Optional[str] = None
    birth_time: Optional[str] = None  # HH:MM
    temple_name: Optional[str] = None
    emotional_state: Optional[str] = None
    intention: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

class HeartRateDataResponse(BaseModel):
    id: int
    heart_rate: int
    recorded_at: datetime
    device_type: str
    activity_type: Optional[str]
    stress_level: Optional[int]

class DashboardStatsResponse(BaseModel):
    period_days: int
    total_events: int
    event_counts: dict[str, int]  # ← Cambiar Dict por dict
    total_meditation_minutes: float
    heart_rate_stats: Optional[dict[str, Any]]  # ← También aquí
    most_used_feature: Optional[str]

class AppEventResponse(BaseModel):
    id: int
    event_type: str
    event_name: str
    duration_minutes: Optional[float]
    details: Optional[str]
    created_at: datetime

# Agregar estos endpoints antes del final del archivo, después de los endpoints de onboarding

# ================= PROFILE ENDPOINTS =================

@app.get("/profile", response_model=UserProfileResponse, tags=["profile"])
async def get_profile(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtener perfil del usuario"""
    try:
        profile = crud_profile.get_user_profile(db, current_user.id)
        
        if not profile:
            # Crear perfil por defecto si no existe
            profile = crud_profile.create_user_profile(db, current_user.id)
        
        return profile
    except Exception as e:
        logger.error(f"Error obteniendo perfil: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.put("/profile", response_model=UserProfileResponse, tags=["profile"])
async def update_profile(
    profile_update: UserProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar perfil del usuario"""
    try:
        update_data = profile_update.dict(exclude_unset=True)
        profile = crud_profile.update_user_profile(db, current_user.id, **update_data)
        return profile
    except Exception as e:
        logger.error(f"Error actualizando perfil: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.put("/profile/onboarding", tags=["profile"])
async def update_onboarding_data(
    onboarding_update: UserOnboardingUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualizar datos del onboarding"""
    try:
        update_data = onboarding_update.dict(exclude_unset=True)
        
        # Convertir fechas si es necesario
        if 'birth_date' in update_data and update_data['birth_date']:
            try:
                update_data['birth_date'] = datetime.strptime(update_data['birth_date'], '%Y-%m-%d').date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD")
        
        if 'birth_time' in update_data and update_data['birth_time']:
            try:
                update_data['birth_time'] = datetime.strptime(update_data['birth_time'], '%H:%M').time()
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de hora inválido. Use HH:MM")
        
        user = crud_profile.update_user_onboarding_data(db, current_user.id, **update_data)
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        return {"message": "Datos de onboarding actualizados exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error actualizando onboarding: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/profile/change-password", tags=["profile"])
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cambiar contraseña del usuario"""
    try:
        # Verificar contraseña actual
        if not crud.authenticate_user(db, current_user.username, password_request.current_password):
            raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
        
        # Cambiar contraseña
        user = crud_profile.change_user_password(db, current_user.id, password_request.new_password)
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        return {"message": "Contraseña cambiada exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cambiando contraseña: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/profile/heart-rate", response_model=List[HeartRateDataResponse], tags=["profile", "dashboard"])
async def get_heart_rate_history(
    days: int = 7,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener historial de ritmo cardíaco"""
    try:
        heart_rate_data = crud_profile.get_heart_rate_history(db, current_user.id, days)
        return heart_rate_data
    except Exception as e:
        logger.error(f"Error obteniendo datos de ritmo cardíaco: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/profile/dashboard", response_model=DashboardStatsResponse, tags=["profile", "dashboard"])
async def get_dashboard_stats_endpoint(
    days: int = 7,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas del dashboard"""
    try:
        stats = crud_profile.get_dashboard_stats(db, current_user.id, days)
        return stats
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas del dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/profile/events", response_model=List[AppEventResponse], tags=["profile", "dashboard"])
async def get_app_events(
    days: int = 30,
    event_type: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtener historial de eventos de la app"""
    try:
        events = crud_profile.get_app_events_history(db, current_user.id, days, event_type)
        return events
    except Exception as e:
        logger.error(f"Error obteniendo eventos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.post("/profile/simulate-data", tags=["profile", "testing"])
async def simulate_user_data(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Simular datos para testing (solo en desarrollo)"""
    if ENVIRONMENT != "development":
        raise HTTPException(status_code=403, detail="Solo disponible en desarrollo")
    
    try:
        # Simular datos de ritmo cardíaco (últimos 7 días)
        hr_count = crud_profile.simulate_heart_rate_data(db, current_user.id, 7)
        
        # Simular eventos de la app (últimos 30 días)
        events_count = crud_profile.simulate_app_events(db, current_user.id, 30)
        
        return {
            "message": "Datos simulados creados exitosamente",
            "heart_rate_records": hr_count,
            "app_events": events_count
        }
    except Exception as e:
        logger.error(f"Error simulando datos: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 para producción
    port = int(os.getenv("PORT", "8011"))
    
    logger.info(f"🚀 Starting Milo API at http://{host}:{port}")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Allowed Origins: {ALLOWED_ORIGINS}")
    
    uvicorn.run("main:app", host=host, port=port, log_level="info", reload=(ENVIRONMENT == "development"))
