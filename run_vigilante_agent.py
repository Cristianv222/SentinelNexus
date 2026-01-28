
import os
import asyncio
import time
from dotenv import load_dotenv

# Cargar variables de entorno
# Cargar variables de entorno
load_dotenv()

# ======================================================
# 💉 PARCHE NUCLEAR DE INICIO (EJECUTAR ANTES DE TODO)
# ======================================================
import sys
import asyncio
import slixmpp.xmlstream.xmlstream

# Patch: Reemplazar el método start_tls para que no haga NADA
async def fake_start_tls(self):
    print("🛡️ [GOD MODE] start_tls interceptado y anulado.")
    return True

slixmpp.xmlstream.xmlstream.XMLStream.start_tls = fake_start_tls
print("💉 [RUNNER] GOD MODE ACTIVADO: start_tls eliminado.")
sys.stdout.flush()

# (Opcional) Mantener flags por si acaso
slixmpp.ClientXMPP.force_starttls = False
slixmpp.ClientXMPP.disable_starttls = True
# ======================================================

from submodulos.agents.monitor import MonitorAgent

async def main():
    print("🕵️ INICIANDO AGENTES VIGILANTES...")
    
    # Configuración XMPP Base
    xmpp_domain = os.getenv('XMPP_DOMAIN', 'sentinelnexus.local')
    xmpp_pass = os.getenv('XMPP_PASSWORD', 'sentinel123')
    
    agents = []

    # Iterar sobre los 3 nodos posibles configurados en .env
    for i in range(1, 4):
        host = os.getenv(f'PROXMOX_NODE{i}_HOST')
        user = os.getenv(f'PROXMOX_NODE{i}_USER')
        password = os.getenv(f'PROXMOX_NODE{i}_PASSWORD')
        name = os.getenv(f'PROXMOX_NODE{i}_NAME', f'Node{i}')

        if host and user and password:
            print(f"   ↳ Configurando Vigilante para: {name} ({host})...")
            
            # Crear JID único para cada vigilante: vigilante_10.100.100.40@sentinel...
            # Usamos la IP o el numero de nodo para hacerlo único
            jid = f"vigilante_{host}@{xmpp_domain}"
            
            agent = MonitorAgent(jid, xmpp_pass, host, user, password)
            
            # --- PARCHE DE SEGURIDAD TLS (Igual que en Cerebro) ---
            # --- PARCHE DE SEGURIDAD TLS (Acceso Directo al Agente) ---
            agent.use_tls = False
            agent.use_ssl = False
            agent.force_starttls = False
            agent.disable_starttls = True
            # ------------------------------------------------------
            # ------------------------------------------------------

            agents.append(agent)
            
            try:
                await agent.start()
                print(f"     ✅ Vigilante {i} activo y escaneando.")
            except Exception as e:
                print(f"     ❌ Error al iniciar Vigilante {i}: {e}")

    if not agents:
        print("⚠️ NO SE ENCONTRARON NODOS PROXMOX EN .ENV")
        return

    print(f"🚀 {len(agents)} Vigilantes operando. Presiona CTRL+C para detener.")
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Deteniendo Vigilantes...")
        for a in agents:
            await a.stop()

if __name__ == "__main__":
    asyncio.run(main())
