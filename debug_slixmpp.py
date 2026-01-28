
import sys
import os
import inspect

# Agrega la ruta del proyecto al path para asegurar que usa el venv correcto si se llama desde ahi
sys.path.append(os.getcwd())

print("🔍 INSPECCIONANDO LIBRERIA SLIXMPP...")
try:
    import slixmpp
    print(f"📂 Slixmpp Path: {slixmpp.__file__}")
    print(f"🔢 Version: {slixmpp.__version__}")
except ImportError:
    print("❌ No se pudo importar slixmpp")
    sys.exit(1)

def print_module_contents(module, name_filter="tls"):
    print(f"\n📦 Contenido de '{module.__name__}':")
    found = False
    for name, obj in inspect.getmembers(module):
        if inspect.ismodule(obj) or inspect.isclass(obj):
            if name_filter in name.lower():
                print(f"   👉 {name} -> {obj}")
                found = True
                # Si es una clase, inspeccionar sus atributos para buscar 'required'
                if inspect.isclass(obj):
                    if hasattr(obj, 'required'):
                         print(f"      📍 {name}.required = {obj.required}")

    if not found:
        print("   (Nada relevante encontrado)")

# 1. Buscar en slixmpp.features
try:
    import slixmpp.features
    print_module_contents(slixmpp.features, "starttls")
    print_module_contents(slixmpp.features, "tls")
except ImportError:
    print("⚠️ slixmpp.features no encontrado")

# 2. Buscar en slixmpp.plugins
try:
    import slixmpp.plugins
    # Listar submodulos comunes
    print("\n🕵️ Buscando plugins XEP relacionados con TLS:")
    for name, obj in inspect.getmembers(slixmpp.plugins):
        if "035" in name or "tls" in name.lower():
             print(f"   👉 {name}")
except ImportError:
    print("⚠️ slixmpp.plugins no encontrado")

# 3. Intento de importación directa (Adivinanza basada en 1.8.5)
print("\n🎯 Pruebas de importación directa:")
imports_to_try = [
    "slixmpp.features.feature_starttls",
    "slixmpp.features.feature_mechanisms",
    "slixmpp.plugins.xep_0035",
    "slixmpp.xmlstream.handler.tls"
]

for path in imports_to_try:
    try:
        __import__(path)
        module = sys.modules[path]
        print(f"   ✅ SUCCESS: {path}")
        print_module_contents(module, "tls")
        print_module_contents(module, "starttls")
    except ImportError:
        print(f"   ❌ FAILED:  {path}")
    except Exception as e:
        print(f"   ❌ ERROR:   {path} - {e}")

print("\n🏁 Inspección finalizada.")
