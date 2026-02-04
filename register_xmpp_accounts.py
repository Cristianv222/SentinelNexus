
import logging
import slixmpp
import os
import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()

# Enable extensive logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

class RegisterClient(slixmpp.ClientXMPP):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        # Force insecure settings (PLAIN)
        self.use_tls = False
        self.use_ssl = False
        self.check_certificate = False
        self.verify_ssl = False
        self.force_starttls = False
        
        # Enable PLAIN auth explicitly
        try:
             self.plugin['feature_mechanisms'].unencrypted_plain = True
             self.plugin['feature_mechanisms'].config['unencrypted_plain'] = True
             self.plugin['feature_mechanisms'].config['use_mech'] = 'PLAIN'
        except Exception:
             pass

        self.add_event_handler("session_start", self.start)
        self.add_event_handler("register", self.register)
        self.add_event_handler("disconnected", self.on_disconnected)
        self.add_event_handler("failed_auth", self.on_failed)
        
        self.register_plugin('xep_0030') # Service Discovery
        self.register_plugin('xep_0004') # Data Forms
        self.register_plugin('xep_0066') # Out-of-band Data
        self.register_plugin('xep_0077') # In-band Registration
        
        self.finished = asyncio.Future()

    async def start(self, event):
        self.send_presence()
        self.disconnect()

    async def register(self, iq):
        resp = self.Iq()
        resp['type'] = 'set'
        resp['register']['username'] = self.boundjid.user
        resp['register']['password'] = self.password
        
        try:
            await resp.send()
            logging.info(f"Account created for {self.boundjid}!")
        except slixmpp.iq.IqError as e:
            if e.iq['error']['code'] == '409':
                 logging.info(f"Account {self.boundjid} already exists.")
            else:
                 logging.error(f"Could not register account {self.boundjid}: {e.iq['error']}")
        except slixmpp.iq.IqTimeout:
            logging.error("No response from server.")
            
        self.disconnect()
        
    def on_disconnected(self, event):
        if not self.finished.done():
            self.finished.set_result(True)

    def on_failed(self, event):
        logging.error("Auth failed (likely during registration flow).")
        # In registration flow, auth fail before register event is weird, but we handle it
        self.disconnect()

async def register_account(jid, password, host):
    logging.info(f"Attempting to register: {jid}")
    xmpp = RegisterClient(jid, password)
    # Register=True triggers the registration flow special handling in Slixmpp
    xmpp.connect(address=(host, 5222), use_ssl=False, disable_starttls=True)
    
    # Wait for completion via future
    await xmpp.finished

async def main():
    xmpp_host = os.getenv('XMPP_HOST')
    xmpp_domain = os.getenv('XMPP_DOMAIN', 'sentinelnexus.local')
    password = os.getenv('XMPP_PASSWORD')
    
    if not password:
         print("Error: XMPP_PASSWORD not found in .env")
         return

    # 1. Register Cerebro Agent (Receiver)
    cerebro_jid = f"vigilante_1@{xmpp_domain}"
    await register_account(cerebro_jid, password, xmpp_host)
    
    # 2. Register Vigilante Agents (Senders)
    for i in range(1, 4):
        node_host = os.getenv(f'PROXMOX_NODE{i}_HOST')
        if node_host:
             vigilante_jid = f"vigilante_{node_host}@{xmpp_domain}"
             await register_account(vigilante_jid, password, xmpp_host)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
