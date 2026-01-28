
import os
import django
import time
import asyncio


# 1. Configurar entorno Django (CRUCIAL para acceder a la BD)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

# 2. Importar el Agente después de configurar Django
from submodulos.agents.cerebro import CerebroAgent

async def main():
    print("🧠 Inicializando CEREBRO SENTINEL...")
    
    # Credenciales XMPP (Desde variables de entorno o .env)
    jid = os.environ.get('XMPP_JID', "cerebro@sentinelnexus.local")
    password = os.environ.get('XMPP_PASSWORD', "sentinel123")
    
    agent = CerebroAgent(jid, password)
    
    try:
        await agent.start()
        print("✅ Cerebro conectado y operando.")
        print("👀 Watchdog vigilando VMs críticas cada 30s...")
        print("📊 Esperando métricas de nodos...")
        print("Presiona CTRL+C para detener.")
        
        # Mantener el script corriendo
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo CEREBRO...")
        await agent.stop()
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")

if __name__ == "__main__":
    asyncio.run(main())
