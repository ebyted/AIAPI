# Milo API

API REST para interactuar con el GPT espiritual "Milo".

## Requisitos

- Docker y Docker Compose (opcional)
- Python 3.11+

## Instalación local

1. Copia `.env.example` a `.env` y completa las variables.
2. Instala dependencias:
   ```bash
   pip install -r requirements.txt
   ```
3. Arranca el servidor:
   ```bash
   uvicorn main:app --reload --port 8000
   ```

## Uso

- **Obtener token**:
  ```bash
  curl -X POST http://localhost:8000/token -d "username=alice&password=fakehashedsecret"
  ```

- **Generar texto**:
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
       -d '{"prompt":"Hola","mode":"text"}' \
       http://localhost:8000/v1/generate
  ```

- **Generar audio**:
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
       -d '{"prompt":"Saluda","mode":"audio"}' \
       http://localhost:8000/v1/generate
  ```

- **Obtener enlaces**:
  ```bash
  curl -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
       -d '{"prompt":"Temas espirituales","mode":"links"}' \
       http://localhost:8000/v1/generate
  ```

## Despliegue con Docker

```bash
docker-compose up --build
```
