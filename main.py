import os
import logging
from prompts import get_prompt_by_mode

from datetime import datetime, timedelta
from typing import Optional, Generator

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Load config
MILO_MODEL_ID = os.getenv("MILO_MODEL_ID", "gpt-3.5-turbo")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Setup FastAPI
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Milo API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8007",
        "http://168.231.67.221:8007"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
Instrumentator().instrument(app).expose(app)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html
@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join("static", "index.html"))

# Health check
@app.get("/health", summary="Health Check")
async def health():
    return {"status": "running", "message": "Milo API is operational"}

# GET /token fallback
@app.get("/token", include_in_schema=False)
async def token_get():
    return JSONResponse({"detail": "Use POST /token to authenticate"}, status_code=200)

# DB session dependency
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic schemas
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

# Register endpoint
@app.post("/register", status_code=201)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    if crud.get_user(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    crud.create_user(db, user.username, user.full_name or "", user.password)
    return {"msg": f"User {user.username} created"}

# Token issuance endpoint
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"Authentication failed for user {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode({"sub": user.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

# Get current user
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

# Generate or playlist endpoint
@app.post("/v1/generate")
@limiter.limit("5/minute")
async def generate(
    request: Request,
    req: GenerateRequest,
    current_user: models.User = Depends(get_current_user),
    promptstr: Optional[str] = None
):
    logger.info(f"User {current_user.username} requested mode={req.mode}")
    prompt_to_use = promptstr if promptstr is not None else req.prompt

    # Si el modo está en PROMPTS, usa get_prompt_by_mode
    from prompts import PROMPTS  # Importa el diccionario para verificar los modos válidos
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

    # Otros modos especiales
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
        with open("lista.txt", "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 5: break
                if line.strip():
                    tracks.append(line.strip())
        return {"tracks": tracks}
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

# Ejemplo de uso:
if __name__ == "__main__":
    modo = "dialogo_sagrado"
    user_vars = {"nombre": "Juan"}
    extra = "Quiero sentirme en paz."
    prompt = get_prompt_by_mode(modo, user_vars, extra)
    print(prompt)

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8011"))
    print(f"🚀 Starting Milo API at http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, log_level="info")
