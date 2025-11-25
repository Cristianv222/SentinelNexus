#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import django
from django.conf import settings

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from django.db import connection
from django.core.management import execute_from_command_line

def test_database_connection():
    """Prueba la conexión a la base de datos y muestra información de debug"""
    
    print("=== INFORMACIÓN DE DEBUG DE BASE DE DATOS ===")
    
    # Mostrar configuración de la base de datos
    db_config = settings.DATABASES['default']
    print("\n1. Configuración de la base de datos:")
    for key, value in db_config.items():
        if key == 'PASSWORD':
            print(f"   {key}: {'*' * len(str(value))}")
        else:
            print(f"   {key}: {value}")
    
    # Mostrar variables de entorno relacionadas con DB
    print("\n2. Variables de entorno de base de datos:")
    db_vars = ['DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT']
    for var in db_vars:
        value = os.getenv(var, 'No definida')
        if 'PASSWORD' in var and value != 'No definida':
            value = '*' * len(value)
        print(f"   {var}: {value}")
    
    # Información del sistema
    print(f"\n3. Información del sistema:")
    print(f"   Python version: {sys.version}")
    print(f"   Django version: {django.get_version()}")
    print(f"   Encoding por defecto: {sys.getdefaultencoding()}")
    print(f"   File system encoding: {sys.getfilesystemencoding()}")
    
    # Intentar conexión
    print(f"\n4. Intentando conexión a la base de datos...")
    try:
        with connection.cursor() as cursor:
            # Verificar que la conexión funciona
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"   ✅ Conexión exitosa! Resultado: {result}")
            
            # Información de la base de datos
            try:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                print(f"   PostgreSQL version: {version}")
            except Exception as e:
                print(f"   Error obteniendo versión: {e}")
                
            try:
                cursor.execute("SHOW client_encoding")
                encoding = cursor.fetchone()[0]
                print(f"   Client encoding: {encoding}")
            except Exception as e:
                print(f"   Error obteniendo encoding: {e}")
                
    except Exception as e:
        print(f"   ❌ Error de conexión: {e}")
        print(f"   Tipo de error: {type(e).__name__}")
        
        # Información adicional del error
        if hasattr(e, 'args') and e.args:
            print(f"   Detalles del error: {e.args}")
            
        # Verificar si es un error de encoding
        if 'UnicodeDecodeError' in str(type(e)) or 'utf-8' in str(e):
            print(f"\n   🔍 DETECTADO ERROR DE ENCODING:")
            print(f"   - Este es un error de codificación UTF-8")
            print(f"   - Verifica que no haya caracteres especiales en las credenciales")
            print(f"   - Asegúrate de que el archivo .env esté guardado en UTF-8")

if __name__ == "__main__":
    test_database_connection()