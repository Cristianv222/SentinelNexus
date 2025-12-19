import time
import asyncio
import slixmpp
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from proxmoxer import ProxmoxAPI
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================================================
# 💉 PARCHE DE CONSTRUCTOR
# ======================================================
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True

class MonitorAgent(Agent):
    
    # 🌟 AQUÍ ESTÁ LA MAGIA: Recibimos los datos del servidor al crear el agente
    def __init__(self, jid, password, proxmox_ip, proxmox_user, proxmox_pass):
        super().__init__(jid, password)
        self.proxmox_ip = proxmox_ip
        self.proxmox_user = proxmox_user
        self.proxmox_pass = proxmox_pass

    class ComportamientoVigilancia(CyclicBehaviour):
        async def run(self):
            # Usamos las variables que guardamos en "self.agent"
            ip = self.agent.proxmox_ip
            print(f"👁️ MONITOR ({ip}): Conectando...")
            
            try:
                proxmox = ProxmoxAPI(
                    ip,
                    user=self.agent.proxmox_user,
                    password=self.agent.proxmox_pass,
                    verify_ssl=False,
                    timeout=5 # Timeout corto por si el server está apagado
                )
                
                nodes = proxmox.nodes.get()
                if not nodes:
                    print(f"⚠️ ({ip}) No se encontraron nodos.")
                    return

                nombre_nodo = nodes[0]['node']
                status = proxmox.nodes(nombre_nodo).status.get()
                
                cpu_uso = status.get('cpu', 0) * 100
                mem_total = status['memory']['total']
                mem_usada = status['memory']['used']
                ram_uso = (mem_usada / mem_total) * 100
                uptime = status.get('uptime', 0)

                # Enviamos el mensaje
                reporte = (
                    f"📡 NODO: {nombre_nodo} | "
                    f"🔥 CPU: {cpu_uso:.2f}% | "
                    f"🧠 RAM: {ram_uso:.2f}% | "
                    f"⏱️ UP: {uptime}s"
                )
                
                print(f"✅ ({ip}) REPORTE ENVIADO")

                msg = Message(to="cerebro@sentinelnexus.local")
                msg.set_metadata("performative", "inform")
                msg.body = reporte
                await self.send(msg)

            except Exception as e:
                print(f"❌ ERROR ({ip}): {e}")
            
            # Cada agente espera 15 segundos para no saturar la red todos a la vez
            await asyncio.sleep(15)

    async def setup(self):
        print(f"🔌 MONITOR INICIADO PARA: {self.proxmox_ip}")
        b = self.ComportamientoVigilancia()
        self.add_behaviour(b)