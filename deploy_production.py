#!/usr/bin/env python3
"""
Script de despliegue para producción
Configura y ejecuta la API BeCalm en el servidor de producción
"""
import os
import subprocess
import sys
from pathlib import Path

def check_environment():
    """Verificar que todas las variables necesarias estén configuradas"""
    required_vars = [
        "OPENAI_API_KEY",
        "SECRET_KEY",
        "DATABASE_URL"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing)}")
        print("🔧 Configura estas variables antes de continuar")
        return False
    
    return True

def main():
    """Función principal de despliegue"""
    print("🚀 BeCalm API - Despliegue de Producción")
    print("=" * 50)
    print("🌐 Servidor de producción: http://168.231.67.221:8011")
    print()
    
    # Cargar variables de entorno
    try:
        from dotenv import load_dotenv
        if Path(".env").exists():
            load_dotenv()
            print("✅ Variables de entorno cargadas desde .env")
        else:
            print("⚠️  Archivo .env no encontrado, usando variables del sistema")
    except ImportError:
        print("⚠️  python-dotenv no instalado, usando variables del sistema")
    
    # Verificar configuración
    if not check_environment():
        print("\n🔧 Para configurar las variables de entorno:")
        print("1. Copia env_production.txt como .env")
        print("2. Edita .env con tus valores reales")
        print("3. Ejecuta este script nuevamente")
        return 1
    
    # Configurar para producción
    os.environ["ENVIRONMENT"] = "production"
    os.environ["HOST"] = "0.0.0.0"  # Escuchar en todas las interfaces
    os.environ["PORT"] = "8011"
    
    # Agregar orígenes de producción a CORS
    current_origins = os.getenv("ALLOWED_ORIGINS", "")
    production_origins = "http://168.231.67.221:8011,https://168.231.67.221:8011"
    
    if current_origins:
        os.environ["ALLOWED_ORIGINS"] = f"{current_origins},{production_origins}"
    else:
        os.environ["ALLOWED_ORIGINS"] = production_origins
    
    print("✅ Configuración de producción aplicada")
    print(f"🌐 HOST: {os.getenv('HOST')}")
    print(f"🔌 PORT: {os.getenv('PORT')}")
    print(f"🌍 ENVIRONMENT: {os.getenv('ENVIRONMENT')}")
    print()
    
    # Ejecutar el servidor
    try:
        print("🚀 Iniciando servidor de producción...")
        print("📝 Logs se mostrarán a continuación")
        print("🛑 Presiona Ctrl+C para detener el servidor")
        print("-" * 50)
        
        # Ejecutar main_production.py
        subprocess.run([sys.executable, "main_production.py"], check=True)
        
    except KeyboardInterrupt:
        print("\n👋 Servidor detenido por el usuario")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error ejecutando el servidor: {e}")
        return 1
    except Exception as e:
        print(f"\n💥 Error inesperado: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
