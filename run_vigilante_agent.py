import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ======================================================
# 💉 PARCHE DE SEGURIDAD PARA AIOXMPP (SPADE 3.3.x)
# ======================================================
print("[RUNNER] INICIANDO PARCHE DE SEGURIDAD PARA AIOXMPP...")

try:
    import aioxmpp
    import spades
    from spade.agent import Agent

    # 1. Parchear make_security_layer para debilitar seguridad TLS
    # Spade llama a esto internamente: aioxmpp.make_security_layer(password, no_verify=not verify_security)
    # Nosotros interceptamos para asegurar que el resultado sea permisivo o PLAIN.
    
    _original_make_security_layer = aioxmpp.make_security_layer
    
    def permissive_make_security_layer(password, no_verify=True):
        print(f"[RUNNER] aioxmpp.make_security_layer INTERCEPTADO. Password: ***, no_verify={no_verify} -> FORZANDO True")
        # Forzamos no_verify=True para ignorar certificados self-signed o malos
        return _original_make_security_layer(password, no_verify=True)
    
    aioxmpp.make_security_layer = permissive_make_security_layer
    print("[RUNNER] aioxmpp.make_security_layer PARCHEADO.")

    # 2. Modificar el __init__ del Agente para asegurar verify_security=False por defecto
    _original_agent_init = Agent.__init__
    def agent_init_hook(self, *args, **kwargs):
        # Asegurar que verify_security sea False en los argumentos si estamos inicializando
        # Spade 3.3 __init__(self, jid, password, verify_security=False)
        # Si kwargs tiene verify_security, forzar False
        if 'verify_security' in kwargs:
            kwargs['verify_security'] = False
        
        _original_agent_init(self, *args, **kwargs)
        
        # Refuerzo post-init
        self.verify_security = False
        print(f"[RUNNER] Agente {self.jid} inicializado con verify_security=False (Force).")

    Agent.__init__ = agent_init_hook
    print("[RUNNER] spade.agent.Agent.__init__ PARCHEADO.")

except ImportError:
    print("[RUNNER] Advertencia: aioxmpp o spade no importado correctamente al inicio. Intentando continuar...")
except Exception as e:
    print(f"[RUNNER] Error aplicando parches AIOXMPP: {e}")

# ======================================================
# INTENTO DE PARCHE LEGACY (SLIXMPP) POR SI ACASO
# ======================================================
try:
    import slixmpp
    # Parche simple para Slixmpp por si el servidor tuviera una mezcla rara
    def permissive_slixmpp_init(self, *args, **kwargs):
        kwargs['use_tls'] = False
        kwargs['use_ssl'] = False
        kwargs['disable_starttls'] = True
        kwargs['force_starttls'] = False
        if hasattr(slixmpp.ClientXMPP, '_original_init_backup'):
            slixmpp.ClientXMPP._original_init_backup(self, *args, **kwargs)
        else:
             # Fallback peligroso si no guardamos el original, pero asumimos que no se llamará si es aioxmpp
             pass
        self.use_tls = False
        self.force_starttls = False
    
    if hasattr(slixmpp, 'ClientXMPP'):
         slixmpp.ClientXMPP._original_init_backup = slixmpp.ClientXMPP.__init__
         slixmpp.ClientXMPP.__init__ = permissive_slixmpp_init
         print("[RUNNER] Slixmpp init parcheado (Legacy Fallback).")
except:
    pass

# ======================================================

from submodulos.agents.monitor import MonitorAgent

async def main():
    print("INICIANDO AGENTES VIGILANTES...")
    
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
            print(f"   Configurando Vigilante para: {name} ({host})...")
            
            agent_jid = f"monitor@{xmpp_domain}"
            
            agent = MonitorAgent(agent_jid, xmpp_pass, host, user, password)
            
            # REFUERZO FINAL
            agent.verify_security = False 
            
            agents.append(agent)
            
            try:
                print(f"     Iniciando agente {name}...")
                await agent.start()
                print(f"     Vigilante {i} ({name}) activo y escaneando.")
            except Exception as e:
                print(f"     Error al iniciar Vigilante {i}: {e}")
                # Imprimir traceback si es posible para debug
                import traceback
                traceback.print_exc()
            
    if not agents:
        print("NO SE ENCONTRARON NODOS PROXMOX EN .ENV")
        return

    print(f"{len(agents)} Vigilantes operando. Presiona CTRL+C para detener.")
    
    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            break
            
    # Parar agentes al salir
    for agent in agents:
        await agent.stop()
    print("Agentes detenidos.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Detenido por usuario.")
