
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
import slixmpp
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        print("💉 [RUNNER] EJECUTANDO PARCHE TLS NUCLEAR")
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.use_ssl = False
        self.use_tls = False
        self.force_starttls = False
        self.disable_starttls = True
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True
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
