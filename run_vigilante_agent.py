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
    import spade # <--- CORREGIDO (era spades)
    from spade.agent import Agent

    # 1. Parchear make_security_layer para DESACTIVAR TLS REQUERIDO
    _original_make_security_layer = aioxmpp.make_security_layer
    
    def permissive_make_security_layer(password, no_verify=True):
        print(f"[RUNNER] aioxmpp.make_security_layer INTERCEPTADO. Obteniendo objeto original...")
        security_layer = _original_make_security_layer(password, no_verify=True)
        print(f"[RUNNER] Capa original: {security_layer}")
        
        # Intentar modificar el atributo tls_required
        try:
            # Opción A: Modificable
            security_layer.tls_required = False
            print("[RUNNER] ✅ tls_required SET TO FALSE (Modificado in-place)")
        except AttributeError:
            # Opción B: Inmutable (NamedTuple/dataclass frozen) - Reconstruir
            print("[RUNNER] ⚠️ Objeto inmutable. Reconstruyendo SecurityLayer...")
            try:
                # Intentamos invocar el constructor de la clase del objeto original
                LayerClass = type(security_layer)
                
                # Extraemos los valores originales
                ssl_factory = getattr(security_layer, 'ssl_context_factory', None)
                cert_verifier = getattr(security_layer, 'certificate_verifier_factory', None)
                sasl_prov = getattr(security_layer, 'sasl_providers', ())
                
                # Reconstruimos forzando tls_required=False
                # Asumimos signature común: (ssl_context_factory, certificate_verifier_factory, tls_required, sasl_providers)
                # Si falla, intentamos kwargs
                try:
                    new_layer = LayerClass(
                        ssl_context_factory=ssl_factory,
                        certificate_verifier_factory=cert_verifier,
                        tls_required=False,
                        sasl_providers=sasl_prov
                    )
                    security_layer = new_layer
                    print(f"[RUNNER] ✅ SecurityLayer RECONSTRUIDO: {security_layer}")
                except TypeError:
                     # Intentar constructor posicinal si kwargs falla (poco probable en aioxmpp reciente)
                     pass

            except Exception as e_recon:
                print(f"[RUNNER] ❌ Falló reconstrucción: {e_recon}")

        return security_layer
    
    aioxmpp.make_security_layer = permissive_make_security_layer
    print("[RUNNER] aioxmpp.make_security_layer PARCHEADO.")

    # 2. Modificar el __init__ del Agente para asegurar verify_security=False por defecto
    _original_agent_init = Agent.__init__
    def agent_init_hook(self, *args, **kwargs):
        if 'verify_security' in kwargs:
            kwargs['verify_security'] = False
        
        _original_agent_init(self, *args, **kwargs)
        
        self.verify_security = False
        print(f"[RUNNER] Agente {self.jid} inicializado con verify_security=False (Force).")

    Agent.__init__ = agent_init_hook
    print("[RUNNER] spade.agent.Agent.__init__ PARCHEADO.")

except ImportError as e:
    print(f"[RUNNER] Advertencia: aioxmpp o spade no importado correctamente: {e}. Parches omitidos.")
except Exception as e:
    print(f"[RUNNER] Error aplicando parches AIOXMPP: {e}")

# ======================================================

from submodulos.agents.monitor import MonitorAgent

async def main():
    print("INICIANDO AGENTES VIGILANTES...")
    
    xmpp_domain = os.getenv('XMPP_DOMAIN', 'sentinelnexus.local')
    xmpp_pass = os.getenv('XMPP_PASSWORD', 'sentinel123')
    
    agents = []

    for i in range(1, 4):
        host = os.getenv(f'PROXMOX_NODE{i}_HOST')
        user = os.getenv(f'PROXMOX_NODE{i}_USER')
        password = os.getenv(f'PROXMOX_NODE{i}_PASSWORD')
        name = os.getenv(f'PROXMOX_NODE{i}_NAME', f'Node{i}')

        if host and user and password:
            print(f"   Configurando Vigilante para: {name} ({host})...")
            
            agent_jid = f"monitor@{xmpp_domain}"
            
            agent = MonitorAgent(agent_jid, xmpp_pass, host, user, password)
            agent.verify_security = False 
            
            agents.append(agent)
            
            try:
                print(f"     Iniciando agente {name}...")
                await agent.start()
                print(f"     Vigilante {i} ({name}) activo y escaneando.")
            except Exception as e:
                print(f"     Error al iniciar Vigilante {i}: {e}")
            
    if not agents:
        print("NO SE ENCONTRARON NODOS PROXMOX EN .ENV")
        return

    print(f"{len(agents)} Vigilantes operando. Presiona CTRL+C para detener.")
    
    while True:
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            break
            
    for agent in agents:
        await agent.stop()
    print("Agentes detenidos.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Detenido por usuario.")
