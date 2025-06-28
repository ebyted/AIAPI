# 🚀 BeCalm API - Despliegue en Producción

## 📋 Información del Servidor

**URL de Producción:** http://168.231.67.221:8011
**Puerto:** 8011
**Ambiente:** production

## ⚡ Inicio Rápido

### Opción 1: Script Automático (Recomendado)

**Windows (PowerShell):**
```powershell
.\start_production.ps1
```

**Linux/Mac:**
```bash
chmod +x start_production.sh
./start_production.sh
```

### Opción 2: Manual

1. **Configurar variables de entorno:**
```bash
cp env_production.txt .env
# Editar .env con tus valores reales
```

2. **Instalar dependencias:**
```bash
pip install -r requirements_production.txt
```

3. **Ejecutar servidor:**
```bash
python main_production.py
```

## 🔧 Configuración de Producción

### Variables de Entorno Requeridas

Edita el archivo `.env` con estos valores:

```env
# OpenAI
OPENAI_API_KEY=tu_openai_api_key_aqui

# Aplicación
ENVIRONMENT=production
SECRET_KEY=tu_secret_key_super_seguro_aqui_minimo_32_caracteres

# Base de datos
DATABASE_URL=sqlite:///./milo.db
# O para PostgreSQL: postgresql://user:password@localhost/dbname

# Servidor
HOST=0.0.0.0
PORT=8011

# CORS
ALLOWED_ORIGINS=http://168.231.67.221:8011,https://168.231.67.221:8011
```

### Base de Datos

**Desarrollo/Testing:** SQLite (por defecto)
```env
DATABASE_URL=sqlite:///./milo.db
```

**Producción (Recomendado):** PostgreSQL
```env
DATABASE_URL=postgresql://usuario:contraseña@localhost/becalm
```

## 🐳 Despliegue con Docker

### Construir y ejecutar

```bash
# Construir imagen
docker build -f Dockerfile_production -t becalm-api .

# Ejecutar contenedor
docker run -p 8011:8011 \
  -e OPENAI_API_KEY=tu_key \
  -e SECRET_KEY=tu_secret \
  becalm-api
```

### Docker Compose

```bash
# Configurar variables en .env primero
docker-compose -f docker-compose.production.yml up -d
```

## 🔍 Verificación

### Endpoints de Salud

```bash
# Verificar que el servidor esté funcionando
curl http://168.231.67.221:8011/health

# Documentación automática
http://168.231.67.221:8011/docs
```

### Script de Verificación

```bash
python check_production.py
```

## 📊 Monitoreo

La API incluye:
- ✅ **Health Check:** `/health`
- 📈 **Métricas:** `/metrics` (Prometheus)
- 📝 **Documentación:** `/docs`
- 🔄 **Rate Limiting:** Configurado automáticamente

## 🛡️ Seguridad

### Configuraciones Importantes

1. **SECRET_KEY:** Usa una clave segura de al menos 32 caracteres
2. **CORS:** Solo orígenes confiables en `ALLOWED_ORIGINS`
3. **Database:** PostgreSQL recomendado para producción
4. **HTTPS:** Configura un proxy reverso (nginx/apache) para HTTPS

### Proxy Reverso (Nginx)

```nginx
server {
    listen 80;
    server_name 168.231.67.221;

    location / {
        proxy_pass http://127.0.0.1:8011;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🐛 Solución de Problemas

### Logs

```bash
# Ver logs en tiempo real
python main_production.py

# Con Docker
docker logs -f container_name
```

### Problemas Comunes

1. **Puerto 8011 ocupado:**
```bash
# Windows
netstat -ano | findstr :8011
taskkill /PID <PID> /F

# Linux
sudo lsof -i :8011
sudo kill -9 <PID>
```

2. **Variables de entorno no cargadas:**
   - Verifica que `.env` existe y tiene las variables correctas
   - Usa `python check_production.py` para diagnosticar

3. **Error de base de datos:**
   - Verifica `DATABASE_URL`
   - Para PostgreSQL, asegúrate de que el servidor esté ejecutándose

## 📞 Soporte

Para problemas de despliegue:
1. Ejecuta `python check_production.py`
2. Revisa los logs del servidor
3. Verifica la configuración de red y firewall
