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

## Onboarding de usuario (sin login)

El flujo de onboarding guía al usuario por varias pantallas para recopilar información personal y de intención. Al finalizar, se crea automáticamente un usuario con correo y contraseña temporal.

- El flujo visual está en `/templates/onboarding/` y usa estilos modernos.
- Cada paso guarda datos en el backend vía endpoints `/onboarding/*`.
- El usuario NO necesita registrarse manualmente.
- Al finalizar, se muestra un mensaje de bienvenida y los datos de acceso.

## Dashboard administrativo

- Acceso solo para administradores vía `/admin/dashboard-view` (HTML) o `/admin/dashboard` (API).
- Muestra métricas globales: usuarios, sesiones de onboarding, recientes.
- Plantilla visual en `templates/dashboard.html`.

## Estructura de carpetas

- `templates/` — Plantillas HTML (heredan de `base.html`)
- `static/css/` — Estilos CSS globales y específicos
- `main.py` — Entrypoint FastAPI
- `models.py`, `crud.py` — Lógica de datos

## Pruebas

Ejecuta:
```bash
pytest
```

## Notas
- El flujo completo está documentado en los comentarios clave de cada archivo.
- Para desarrollo, usa `.env` y `requirements.txt`. Para producción, usa los archivos *_production*.
