import os
import sys
import asyncio
import json
import logging
import django
from dotenv import load_dotenv

load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

# ======================================================
# 💉 PARCHE DE SEGURIDAD PARA AIOXMPP (Igual que Vigilante)
# ======================================================
print("[RUNNER] INICIANDO PARCHE DE SEGURIDAD PARA CEREBRO (AIOXMPP)...")

try:
    import aioxmpp
    import spade
    from spade.agent import Agent

    # 1. Parchear make_security_layer para DESACTIVAR TLS REQUERIDO
    _original_make_security_layer = aioxmpp.make_security_layer
    
    def permissive_make_security_layer(password, no_verify=True):
        security_layer = _original_make_security_layer(password, no_verify=True)
        
        # Intentar modificar el atributo tls_required
        try:
            # Opción A: Modificable
            security_layer.tls_required = False
        except AttributeError:
            # Opción B: Inmutable - Reconstruir
            try:
                LayerClass = type(security_layer)
                ssl_factory = getattr(security_layer, 'ssl_context_factory', None)
                cert_verifier = getattr(security_layer, 'certificate_verifier_factory', None)
                sasl_prov = getattr(security_layer, 'sasl_providers', ())
                
                new_layer = LayerClass(
                    ssl_context_factory=ssl_factory,
                    certificate_verifier_factory=cert_verifier,
                    tls_required=False,
                    sasl_providers=sasl_prov
                )
                security_layer = new_layer
            except Exception as e_recon:
                print(f"[RUNNER] ❌ Falló reconstrucción: {e_recon}")

        return security_layer
    
    aioxmpp.make_security_layer = permissive_make_security_layer
    print("[RUNNER] aioxmpp.make_security_layer PARCHEADO.")

    # 2. Modificar el __init__ del Agente
    _original_agent_init = Agent.__init__
    def agent_init_hook(self, *args, **kwargs):
        if 'verify_security' in kwargs:
            kwargs['verify_security'] = False
        _original_agent_init(self, *args, **kwargs)
        self.verify_security = False

    Agent.__init__ = agent_init_hook
    print("[RUNNER] spade.agent.Agent.__init__ PARCHEADO.")

except ImportError as e:
    print(f"[RUNNER] FATAL ERROR IMPORTING AIOXMPP/SPADE: {e}")
except Exception as e:
    print(f"[RUNNER] Error patch: {e}")

# ======================================================
# 💉 PARCHE LEGACY (SLIXMPP) - PLAN B
# ======================================================
print("[RUNNER] APLICANDO PARCHE LEGACY (SLIXMPP)...")
try:
    import slixmpp
    
    _original_slix_init = slixmpp.ClientXMPP.__init__
    def permissive_slixmpp_init(self, *args, **kwargs):
        # ELIMINAR argumentos conflictivos de kwargs antes de llamar al original
        kwargs.pop('use_tls', None)
        kwargs.pop('use_ssl', None)
        kwargs.pop('disable_starttls', None)
        kwargs.pop('force_starttls', None)
        
        # Llamar al original limpio
        _original_slix_init(self, *args, **kwargs)
        
        # Override atributos post-init (FORZADO)
        self.use_tls = False
        self.force_starttls = False
        self.disable_starttls = True
        self.verify_ssl = False
        logging.info("[RUNNER] SLIXMPP INIT PATCHED (TLS OFF)")
        
        # Intentar habilitar PLAIN auth en plugins
        try:
             if hasattr(self, 'plugin'):
                self.plugin['feature_mechanisms'].unencrypted_plain = True
        except:
            pass

    slixmpp.ClientXMPP.__init__ = permissive_slixmpp_init
    print("[RUNNER] slixmpp.ClientXMPP.__init__ PARCHEADO.")

except ImportError:
    print("[RUNNER] slixmpp no encontrado (OK si se usa aioxmpp).")

# ======================================================

# ======================================================

from submodulos.agents.cerebro import CerebroAgent

async def main():
    print("Starting CEREBRO (Service Mode)...")
    
    # Use KNOWN GOOD credentials
    jid = os.environ.get('XMPP_JID', "cerebro@sentinelnexus.local")
    password = os.getenv('XMPP_PASSWORD', "sentinel123")
    
    print(f"Logging in as {jid}...")
    agent = CerebroAgent(jid, password)
    agent.verify_security = False
    
    try:
        await agent.start()
        print("Cerebro Service Connected and WAITING for messages...")
        
        # Mantener vivo
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        await agent.stop()
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
