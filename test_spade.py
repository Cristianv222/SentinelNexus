
import asyncio
import time
import slixmpp
import logging
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

# Configuración de log
logging.basicConfig(level=logging.DEBUG)

# 💉 APLICAR PARCHE DIRECTAMENTE AQUÍ TAMBIÉN
# Para asegurar que el test use la misma lógica permisiva
_original_init = slixmpp.ClientXMPP.__init__
def constructor_parcheado(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    print("🔧 PARCHE: Habilitando auth texto plano...")
    try:
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.plugin['feature_mechanisms'].config['unencrypted_plain'] = True
        self.plugin['feature_mechanisms'].config['use_mech'] = 'PLAIN'
    except Exception:
        pass
    self.use_tls = False
    self.use_ssl = False
    self.check_certificate = False
    self.verify_ssl = False

slixmpp.ClientXMPP.__init__ = constructor_parcheado

_original_connect = slixmpp.ClientXMPP.connect
def connect_parcheado(self, *args, **kwargs):
    # hardcode IP for test and remove incompatible spade args
    if 'host' in kwargs: del kwargs['host']
    if 'port' in kwargs: del kwargs['port']
    
    # Ajusta esto si tu IP de Prosody es diferente
    kwargs['address'] = ('10.100.100.41', 5222)
    return _original_connect(self, *args, **kwargs)
slixmpp.ClientXMPP.connect = connect_parcheado


class AgenteMonitor(Agent):
    class EnviarMensaje(OneShotBehaviour):
        async def run(self):
            print("📤 Enviando mensaje de prueba...")
            msg = Message(to="cerebro@sentinelnexus.local")  # Asegúrate que este usuario exista
            msg.set_metadata("performative", "inform")
            msg.body = "Hola Cerebro, soy el Monitor (TEST)"

            await self.send(msg)
            print("✅ Mensaje enviado!")
            
            # Esperar un poco antes de morir para ver si hay logs de envío
            await asyncio.sleep(2)
            await self.agent.stop()

    async def setup(self):
        print("Agente Monitor INICIADO")
        b = self.EnviarMensaje()
        self.add_behaviour(b)

async def main():
    print("🚀 Iniciando prueba...")
    # Asegúrate de usar credenciales válidas
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
