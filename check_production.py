#!/usr/bin/env python3
"""
Script de verificación para diagnosticar problemas en producción
"""
import os
import sys
from pathlib import Path

# Cargar variables de entorno del archivo .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv no instalado, usando variables de entorno del sistema")

def check_environment():
    """Verificar variables de entorno críticas"""
    print("🔍 Verificando variables de entorno...")
    
    required_vars = [
        "OPENAI_API_KEY",
        "SECRET_KEY",
        "DATABASE_URL"
    ]
    
    optional_vars = [
        "ENVIRONMENT",
        "ALLOWED_ORIGINS", 
        "HOST",
        "PORT"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            print(f"❌ {var}: NO CONFIGURADA")
        else:
            print(f"✅ {var}: Configurada")
    
    for var in optional_vars:
        value = os.getenv(var, "No configurada")
        print(f"ℹ️  {var}: {value}")
    
    if missing:
        print(f"\n❌ Variables faltantes: {', '.join(missing)}")
        return False
    return True

def check_files():
    """Verificar archivos necesarios"""
    print("\n📁 Verificando archivos...")
    
    required_files = [
        "main_production.py",
        "models.py", 
        "crud.py",
        "database.py",
        "prompts.py"
    ]
    
    optional_files = [
        "lista_meditacion.txt",
        "lista.txt",
        ".env"
    ]
    
    required_dirs = [
        "templates",
        "static"
    ]
    
    missing = []
    
    for file in required_files:
        if Path(file).exists():
            print(f"✅ {file}: Existe")
        else:
            missing.append(file)
            print(f"❌ {file}: NO EXISTE")
    
    for file in optional_files:
        if Path(file).exists():
            print(f"✅ {file}: Existe")
        else:
            print(f"⚠️  {file}: No existe (opcional)")
    
    for dir in required_dirs:
        if Path(dir).exists():
            print(f"✅ {dir}/: Existe")
        else:
            missing.append(dir)
            print(f"❌ {dir}/: NO EXISTE")
    
    if missing:
        print(f"\n❌ Archivos/directorios faltantes: {', '.join(missing)}")
        return False
    return True

def check_dependencies():
    """Verificar dependencias Python"""
    print("\n📦 Verificando dependencias...")
    
    dependencies = [
        "fastapi",
        "uvicorn", 
        "openai",
        "sqlalchemy",
        "jose",
        "passlib",
        "slowapi",
        "prometheus_fastapi_instrumentator"
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"✅ {dep}: Instalado")
        except ImportError:
            missing.append(dep)
            print(f"❌ {dep}: NO INSTALADO")
    
    if missing:
        print(f"\n❌ Dependencias faltantes: {', '.join(missing)}")
        print("Ejecuta: pip install -r requirements_production.txt")
        return False
    return True

def check_database():
    """Verificar conexión a base de datos"""
    print("\n🗄️  Verificando base de datos...")
    
    try:
        from database import test_connection
        if test_connection():
            print("✅ Conexión a base de datos: OK")
            return True
        else:
            print("❌ Conexión a base de datos: FALLO")
            return False
    except Exception as e:
        print(f"❌ Error verificando base de datos: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 BeCalm API - Verificación de Producción")
    print("=" * 50)
    
    checks = [
        ("Variables de entorno", check_environment),
        ("Archivos", check_files), 
        ("Dependencias", check_dependencies),
        ("Base de datos", check_database)
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Error en {name}: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("📊 RESUMEN:")
    
    all_good = all(results)
    if all_good:
        print("✅ Todas las verificaciones pasaron!")
        print("🚀 La aplicación debería funcionar en producción")
    else:
        print("❌ Algunas verificaciones fallaron")
        print("🔧 Revisa los errores arriba antes de desplegar")
    
    return 0 if all_good else 1

if __name__ == "__main__":
    sys.exit(main())
