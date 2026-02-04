
import os
import sys
import asyncio
import json
import slixmpp
import django
from dotenv import load_dotenv

load_dotenv()

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

print("[RUNNER] Applying Patch for Production...")

_original_init = slixmpp.ClientXMPP.__init__
def constructor_permissive(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.use_tls = False
    self.use_ssl = False
    self.check_certificate = False
    self.verify_ssl = False
    try:
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.plugin['feature_mechanisms'].config['unencrypted_plain'] = True
        self.plugin['feature_mechanisms'].config['use_mech'] = 'PLAIN'
        print("[RUNNER] PLAIN AUTH ENABLED in __init__")
    except Exception:
        pass

slixmpp.ClientXMPP.__init__ = constructor_permissive

_original_connect = slixmpp.ClientXMPP.connect
def connect_parcheado(self, *args, **kwargs):
    if 'host' in kwargs: del kwargs['host']
    if 'port' in kwargs: del kwargs['port']
    
    # 🩹 FORZAR PARAMETROS EN CONNECT
    kwargs['use_ssl'] = False
    kwargs['disable_starttls'] = True
    
    xmpp_host = os.getenv('XMPP_HOST')
    if xmpp_host:
        kwargs['address'] = (xmpp_host, 5222)
    return _original_connect(self, *args, **kwargs)
slixmpp.ClientXMPP.connect = connect_parcheado

from submodulos.agents.cerebro import CerebroAgent

async def main():
    print("Starting CEREBRO (Service Mode)...")
    
    # Use KNOWN GOOD credentials
    jid = os.environ.get('XMPP_JID', "cerebro@sentinelnexus.local")
    password = os.getenv('XMPP_PASSWORD', "sentinel123")
    
    print(f"Logging in as {jid}...")
    agent = CerebroAgent(jid, password)
    
    try:
        await agent.start()
        print("Cerebro Service Connected!")
        
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        await agent.stop()
    except Exception as e:
        print(f"FATAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
