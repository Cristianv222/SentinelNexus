import time
import asyncio
import slixmpp
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

# ======================================================
# 💉 PARCHE AL CONSTRUCTOR DE SLIXMPP (NECESARIO) 💉
# ======================================================
_original_init = slixmpp.ClientXMPP.__init__

def constructor_parcheado(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    print("🔧 PARCHE: Habilitando auth texto plano...")
    self.plugin['feature_mechanisms'].unencrypted_plain = True

slixmpp.ClientXMPP.__init__ = constructor_parcheado
# ======================================================

class AgenteMonitor(Agent):
    class ComportamientoSaludo(OneShotBehaviour):
        async def run(self):
            print("🤖 MONITOR: ¡Conectado y Operativo!")
            
            msg = Message(to="cerebro@sentinelnexus.local") 
            msg.set_metadata("performative", "inform") 
            msg.body = "Hola Cerebro, conexión exitosa."
            
            await self.send(msg)
            print("✅ ÉXITO: Mensaje enviado al servidor.")
            # Al terminar el comportamiento, paramos el agente
            await self.agent.stop()

    async def setup(self):
        print("🔌 Iniciando agente...")
        b = self.ComportamientoSaludo()
        self.add_behaviour(b)

async def main():
    print("🚀 Iniciando prueba...")
    monitor = AgenteMonitor("monitor@sentinelnexus.local", "sentinel123")
    
    await monitor.start()
    
    # ESPERA CORRECTA: Mientras el agente esté vivo, esperamos
    while monitor.is_alive():
        try:
            await asyncio.sleep(1)
        except KeyboardInterrupt:
            await monitor.stop()
            break
            
    print("👋 Test finalizado correctamente.")

if __name__ == "__main__":
    asyncio.run(main())