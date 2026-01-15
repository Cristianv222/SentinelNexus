import time
import asyncio
import slixmpp
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from asgiref.sync import sync_to_async
from submodulos.models import ServerMetric, VMMetric
import re

# ======================================================
# 💉 PARCHE DE CONEXIÓN
# ======================================================
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True

class CerebroAgent(Agent):
    class ComportamientoEscucha(CyclicBehaviour):
        
        @sync_to_async
        def guardar_metrica_servidor(self, nodo, cpu, ram, up):
            ServerMetric.objects.create(
                node_name=nodo,
                cpu_usage=cpu,
                ram_usage=ram,
                uptime=up
            )
            
        @sync_to_async
        def guardar_metrica_vm(self, nombre, servidor, cpu, ram, status):
            # Guardar Métrica Real
            VMMetric.objects.create(
                vm_name=nombre,
                server_origin=servidor,
                cpu_usage=cpu,
                ram_usage=ram,
                status=status
            )
            
            # --- DETECCIÓN DE ANOMALÍAS ---
            from submodulos.models import VMPrediction, MaquinaVirtual
            from django.utils import timezone
            from datetime import timedelta
            
            try:
                # Buscar VM en DB para obtener ID (necesario para buscar predicción)
                # Nota: Esto asume que la VM ya existe o se puede buscar por nombre/server
                # Para simplificar, intentamos buscar por nombre
                vm_obj = MaquinaVirtual.objects.filter(nombre=nombre).first()
                if vm_obj:
                    # Buscar predicción para la hora actual (margen de error de la hora)
                    now = timezone.now()
                    # Redondear a la hora más cercana o buscar en rango
                    start_range = now - timedelta(minutes=30)
                    end_range = now + timedelta(minutes=30)
                    
                    prediction = VMPrediction.objects.filter(
                        vm=vm_obj, 
                        timestamp__range=(start_range, end_range)
                    ).first()
                    
                    if prediction:
                        # Umbrales (Hardcoded por ahora, podrían ser configurables)
                        # Si difiere más del 20% absoluto
                        umbrale_cpu = 20.0 
                        diff_cpu = abs(prediction.predicted_cpu_usage - cpu)
                        
                        if diff_cpu > umbrale_cpu:
                            print(f"⚠️ ANOMALÍA DETECTADA en {nombre}: CPU Real {cpu}% vs Predicho {prediction.predicted_cpu_usage:.2f}%")
                            # Aquí se podría disparar una alerta XMPP o guardar eventos
            except Exception as e:
                print(f"Error en detección de anomalías: {e}")

        async def run(self):
            print("🧠 CEREBRO: Esperando datos...")
            msg = await self.receive(timeout=10)
            
            if msg and msg.body:
                texto = msg.body
                
                # Intentamos parsear como JSON (Nuevo formato con VMs)
                try:
                    data = json.loads(texto)
                    
                    if "node" in data and "vms" in data:
                        nodo = data["node"]
                        
                        # Guardar Nodo
                        await self.guardar_metrica_servidor(
                            nodo, 
                            float(data["cpu"]), 
                            float(data["ram"]), 
                            int(data["uptime"])
                        )
                        print(f"💾 NODO GUARDADO: {nodo}")
                        
                        # Guardar VMs
                        vms = data["vms"]
                        count = 0
                        for vm in vms:
                            await self.guardar_metrica_vm(
                                vm["name"],
                                nodo,
                                float(vm["cpu"]),
                                float(vm["ram"]),
                                vm["status"]
                            )
                            count += 1
                        
                        print(f"   ↳ 💾 {count} MÉTRICAS DE VM GUARDADAS")
                        return 

                except json.JSONDecodeError:
                    pass 

                # Fallback: Lógica antigua (Texto plano)
                try:
                    match_nodo = re.search(r"NODO: (\w+)", texto)
                    match_cpu = re.search(r"CPU: ([\d\.]+)%", texto)
                    match_ram = re.search(r"RAM: ([\d\.]+)%", texto)
                    match_up = re.search(r"UP: (\d+)s", texto)

                    if match_nodo and match_cpu and match_ram and match_up:
                        nodo = match_nodo.group(1)
                        cpu = float(match_cpu.group(1))
                        ram = float(match_ram.group(1))
                        up = int(match_up.group(1))

                        await self.guardar_metrica_servidor(nodo, cpu, ram, up)
                        print(f"💾 GUARDADO EN BD (Texto): {nodo}")
                    else:
                        print(f"⚠️ Formato desconocido: {texto}")

                except Exception as e:
                    print(f"❌ Error procesando: {e}")

    async def setup(self):
        print("🔌 CEREBRO: Iniciando sistema de almacenamiento...")
        b = self.ComportamientoEscucha()
        self.add_behaviour(b)