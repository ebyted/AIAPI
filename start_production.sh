#!/bin/bash
# Script de inicio rápido para producción

echo "🚀 BeCalm API - Inicio Rápido de Producción"
echo "=========================================="
echo "🌐 Servidor: http://168.231.67.221:8011"
echo ""

# Verificar si existe el archivo .env
if [ ! -f ".env" ]; then
    echo "⚠️  Archivo .env no encontrado"
    echo "📋 Copiando configuración de producción..."
    cp env_production.txt .env
    echo "✅ Archivo .env creado desde env_production.txt"
    echo "🔧 EDITA el archivo .env con tus valores reales antes de continuar"
    echo ""
    echo "Variables importantes a configurar:"
    echo "  - OPENAI_API_KEY"
    echo "  - SECRET_KEY"
    echo "  - DATABASE_URL (opcional, usa SQLite por defecto)"
    echo ""
    read -p "¿Has configurado el archivo .env? (y/N): " confirm
    if [[ $confirm != [yY] ]]; then
        echo "❌ Configura .env primero y ejecuta el script nuevamente"
        exit 1
    fi
fi

# Cargar variables de entorno
export $(grep -v '^#' .env | xargs)

# Configurar para producción
export ENVIRONMENT=production
export HOST=0.0.0.0
export PORT=8011
export ALLOWED_ORIGINS="http://168.231.67.221:8011,https://168.231.67.221:8011"

echo "✅ Configuración cargada"
echo "🌐 HOST: $HOST"
echo "🔌 PORT: $PORT"
echo "🌍 ENVIRONMENT: $ENVIRONMENT"
echo ""

# Instalar dependencias si es necesario
if [ ! -d "venv" ]; then
    echo "📦 Creando entorno virtual..."
    python3 -m venv venv
fi

echo "📦 Activando entorno virtual e instalando dependencias..."
source venv/bin/activate
pip install -r requirements_production.txt

echo ""
echo "🚀 Iniciando servidor de producción..."
echo "📝 Logs se mostrarán a continuación"
echo "🛑 Presiona Ctrl+C para detener"
echo "----------------------------------------"

# Ejecutar el servidor
python main_production.py
