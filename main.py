import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Generator

import openai
from openai import OpenAI
# Instantiate new OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
MILO_MODEL_ID = os.getenv("MILO_MODEL_ID", "gpt-3.5-turbo")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# Initialize FastAPI, rate limiter and metrics
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Milo API", version="1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
Instrumentator().instrument(app).expose(app)

# Mount static directory under /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html at root
@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join("static", "index.html"))

# Health check endpoint
@app.get("/health", summary="Health Check")
async def health():
    return {"status": "running", "message": "Milo API is operational"}

# Optional: catch GET on /token to prevent 405
@app.get("/token", include_in_schema=False)
async def token_get():
    return JSONResponse({"detail": "Use POST /token to authenticate"}, status_code=200)

# Dependency for DB session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    full_name: Optional[str] = None
    password: str

class GenerateRequest(BaseModel):
    prompt: str
    mode: str  # "text" | "audio" | "links"

# User registration endpoint
@app.post("/register", status_code=201)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    if crud.get_user(db, user.username):
        raise HTTPException(status_code=400, detail="Username already registered")
    crud.create_user(db, user.username, user.full_name or "", user.password)
    return {"msg": f"User {user.username} created"}

# Token endpoint (POST)
@app.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"Authentication failed for user {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token = jwt.encode({"sub": user.username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

# Dependency to get current user
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user(db, username)
    if not user:
        raise credentials_exception
    return user

# GPT generate endpoint using openai v1 interface
@app.post("/v1/generate")
@limiter.limit("5/minute")
async def generate(
    request: Request,
    req: GenerateRequest,
    current_user: models.User = Depends(get_current_user)
):
    logger.info(f"User {current_user.username} requested mode={req.mode}")
    if req.mode == "text":
        response = client.chat.completions.create(
            model=MILO_MODEL_ID,
            messages=[{"role": "user", "content": req.prompt}],
            temperature=0.7,
            max_tokens=250
        )
        return {"text": response.choices[0].message.content.strip()}
    elif req.mode == "audio":
        audio_resp = client.audio.speech.create(
            model="tts-1", input=req.prompt, voice="alloy", format="mp3"
        )
        return {"audio_base64": audio_resp.audio}
    elif req.mode == "links":
        response = openai.ChatCompletion.create(
            model=MILO_MODEL_ID,
            messages=[
                {"role": "system", "content": "Devuelve hasta 5 enlaces https válidos relacionados con el siguiente tema."},
                {"role": "user", "content": req.prompt}
            ],
            temperature=0
        )
        return {"links": response.choices[0].message.content.strip().split()}
    else:
        raise HTTPException(status_code=400, detail="Invalid mode")

# Run with: python main.py
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting Milo API at http://{host}:{port}")
    uvicorn.run("main:app", host=host, port=port, log_level="info")
