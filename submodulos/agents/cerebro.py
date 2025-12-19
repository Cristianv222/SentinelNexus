import time
import asyncio
import slixmpp
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
# Importamos las herramientas para guardar en BD
from asgiref.sync import sync_to_async
from submodulos.models import ServerMetric
import re

# ======================================================
# 💉 PARCHE DE CONEXIÓN (Necesario para tu servidor local)
# ======================================================
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True
# ======================================================

class CerebroAgent(Agent):
    class ComportamientoEscucha(CyclicBehaviour):
        
        # Función auxiliar para guardar en BD (puente Async -> Sync)
        @sync_to_async
        def guardar_metrica(self, nodo, cpu, ram, up):
            ServerMetric.objects.create(
                node_name=nodo,
                cpu_usage=cpu,
                ram_usage=ram,
                uptime=up
            )

        async def run(self):
            print("🧠 CEREBRO: Esperando datos...")
            # Esperamos mensaje (timeout 10s)
            msg = await self.receive(timeout=10)
            
            if msg and msg.body:
                texto = msg.body
                # Ejemplo de lo que llega: 
                # "📡 NODO: prx2 | 🔥 CPU: 0.16% | 🧠 RAM: 4.52% | ⏱️ UP: 461666s"
                
                try:
                    # Usamos Regex para extraer los numeritos del texto
                    match_nodo = re.search(r"NODO: (\w+)", texto)
                    match_cpu = re.search(r"CPU: ([\d\.]+)%", texto)
                    match_ram = re.search(r"RAM: ([\d\.]+)%", texto)
                    match_up = re.search(r"UP: (\d+)s", texto)

                    if match_nodo and match_cpu and match_ram and match_up:
                        nodo = match_nodo.group(1)
                        cpu = float(match_cpu.group(1))
                        ram = float(match_ram.group(1))
                        up = int(match_up.group(1))

                        # Guardamos en la Base de Datos
                        await self.guardar_metrica(nodo, cpu, ram, up)
                        print(f"💾 GUARDADO EN BD: {nodo} -> CPU: {cpu}% | RAM: {ram}%")
                    else:
                        print(f"⚠️ Formato desconocido: {texto}")

                except Exception as e:
                    print(f"❌ Error procesando: {e}")

    async def setup(self):
        print("🔌 CEREBRO: Iniciando sistema de almacenamiento...")
        b = self.ComportamientoEscucha()
        self.add_behaviour(b)