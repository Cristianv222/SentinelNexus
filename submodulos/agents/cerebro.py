import time
import asyncio
import slixmpp
import json
import re
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour
from asgiref.sync import sync_to_async
from submodulos.models import ServerMetric, VMMetric, AgentLog, MaquinaVirtual, Nodo, VMPrediction, ProxmoxServer
from submodulos.logic.forecasting import train_and_predict_server, train_and_predict_vm
from submodulos.proxmox_service import proxmox_service
from django.utils import timezone
from datetime import timedelta

# ======================================================
# 💉 PARCHE DE CONEXIÓN
# ======================================================
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.use_ssl = False
        self.use_tls = False
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True

class CerebroAgent(Agent):
    @sync_to_async
    def guardar_metrica_servidor(self, nodo_nombre, cpu, ram, up):
        try:
            # Buscar el servidor Proxmox asociado a este nodo
            # Prioridad 1: Coincidencia exacta de nombre de nodo
            server = ProxmoxServer.objects.filter(node_name=nodo_nombre).first()
            
            # Prioridad 2: Buscar si el hostname contiene el nombre del nodo
            if not server:
                server = ProxmoxServer.objects.filter(hostname__icontains=nodo_nombre).first()
            
            # Fallback: Usar el primer servidor activo (útil para entornos dev/single node)
            if not server:
                server = ProxmoxServer.objects.filter(is_active=True).first()
                if server:
                    print(f"⚠️ Servidor para nodo {nodo_nombre} no encontrado explícitamente. Asignando a {server.name}")

            if server:
                ServerMetric.objects.create(
                    server=server,
                    cpu_usage=cpu,
                    ram_usage=ram,
                    uptime=up,
                    disk_usage=0
                )
            else:
                print(f"❌ ERROR CRÍTICO: No hay servidores Proxmox registrados en DB. No se puede guardar métrica de {nodo_nombre}")
        except Exception as e:
            print(f"❌ Error guardando métrica de servidor: {e}")
        
    @sync_to_async
    def guardar_metrica_vm(self, nombre, servidor, cpu, ram, status):
        # 1. Guardar Métrica Real
        VMMetric.objects.create(
            vm_name=nombre,
            server_origin=servidor,
            cpu_usage=cpu,
            ram_usage=ram,
            status=status
        )
        
        # 2. DETECCIÓN DE ANOMALÍAS (SARIMA)
        try:
            # Buscar VM en DB para obtener ID
            vm_obj = MaquinaVirtual.objects.filter(nombre=nombre).first()
            if vm_obj:
                # Buscar predicción para la hora actual
                now = timezone.now()
                start_range = now - timedelta(minutes=30)
                end_range = now + timedelta(minutes=30)
                
                prediction = VMPrediction.objects.filter(
                    vm=vm_obj, 
                    timestamp__range=(start_range, end_range)
                ).first()
                
                if prediction:
                    # Si difiere más del 20% absoluto
                    umbrale_cpu = 20.0 
                    diff_cpu = abs(prediction.predicted_cpu_usage - cpu)
                    
                    if diff_cpu > umbrale_cpu:
                        msg = f"⚠️ ANOMALÍA DETECTADA en {nombre}: CPU Real {cpu}% vs Predicho {prediction.predicted_cpu_usage:.2f}%"
                        print(msg)
                        # Registrar anomalía como warning tambien
                        AgentLog.objects.create(
                            agent_name="Cerebro",
                            level="WARNING",
                            message=msg,
                            details={"cpu_real": cpu, "cpu_pred": prediction.predicted_cpu_usage}
                        )
        except Exception as e:
            print(f"Error en detección de anomalías: {e}")

    @sync_to_async
    def log_db(self, msg, level='INFO', details=None):
        AgentLog.objects.create(
            agent_name="Cerebro",
            level=level,
            message=msg,
            details=details
        )
        print(f"[{level}] {msg}")

    class ComportamientoEscucha(CyclicBehaviour):
        async def run(self):
            print("🧠 CEREBRO: Esperando datos...")
            msg = await self.receive(timeout=10)
            
            if msg and msg.body:
                texto = msg.body
                
                # Intentamos parsear como JSON
                try:
                    data = json.loads(texto)
                    
                    if "node" in data and "vms" in data:
                        nodo = data["node"]
                        
                        # Guardar Nodo
                        await self.agent.guardar_metrica_servidor(
                            nodo, 
                            float(data["cpu"]), 
                            float(data["ram"]), 
                            int(data["uptime"])
                        )
                        print(f"💾 NODO GUARDADO: {nodo}")
                        
                        # Guardar VMs
                        vms = data["vms"]
                        count = 0
                        high_load_vms = []

                        for vm in vms:
                            await self.agent.guardar_metrica_vm(
                                vm["name"],
                                nodo,
                                float(vm["cpu"]),
                                float(vm["ram"]),
                                vm["status"]
                            )
                            count += 1
                            if float(vm["ram"]) > 90.0:
                                high_load_vms.append(vm["name"])
                        
                        # Log simple de resumen
                        await self.agent.log_db(f"Procesado reporte de {nodo}: {count} VMs", "INFO", {"node": nodo, "vm_count": count})
                        
                        # Log de alerta si hay carga
                        if high_load_vms:
                             await self.agent.log_db(f"⚠️ Alta carga de RAM detectada en: {', '.join(high_load_vms)}", "WARNING", {"vms": high_load_vms})

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

                        await self.agent.guardar_metrica_servidor(nodo, cpu, ram, up)
                        print(f"💾 GUARDADO EN BD (Texto): {nodo}")
                    else:
                        print(f"⚠️ Formato desconocido: {texto}")

                except Exception as e:
                    print(f"❌ Error procesando: {e}")

    class ComportamientoWatchdog(PeriodicBehaviour):
        async def run(self):
            # 1. Obtener VMs críticas
            vms_criticas = await sync_to_async(list)(MaquinaVirtual.objects.filter(is_critical=True))
            
            if not vms_criticas:
                return

            for vm in vms_criticas:
                try:
                    # 2. Obtener estado real desde Proxmox
                    nodo_nombre = await sync_to_async(lambda: vm.nodo.nombre)()
                    
                    # Simulación de recuperación (Simplificada como en origin/main)
                    # En la realidad requeriría proxmox_manager configurado
                    
                    # Por ahora usamos el servicio básico si coincide el default
                    from submodulos.proxmox_service import proxmox_service
                    proxmox = proxmox_service.proxmox

                    if not proxmox:
                         return 

                    # Función auxiliar síncrona
                    def check_and_recover(vm_obj, node_name):
                        try:
                            if vm_obj.vm_type == 'qemu':
                                status_info = proxmox.nodes(node_name).qemu(vm_obj.vmid).status.current.get()
                            else:
                                status_info = proxmox.nodes(node_name).lxc(vm_obj.vmid).status.current.get()
                        except Exception as e:
                            return f"Status Check Error: {e}"

                        estado_actual = status_info.get('status', 'unknown')
                        
                        if estado_actual == 'stopped':
                            # Intentar iniciar
                            try:
                                if vm_obj.vm_type == 'qemu':
                                    proxmox.nodes(node_name).qemu(vm_obj.vmid).status.start.post()
                                else:
                                    proxmox.nodes(node_name).lxc(vm_obj.vmid).status.start.post()
                                return "RESTARTED"
                            except:
                                return "FAILED_RESTART"
                        
                        return "OK"

                    # Ejecutar en hilo aparte
                    resultado = await sync_to_async(check_and_recover)(vm, nodo_nombre)
                    
                    if resultado == "RESTARTED":
                        await self.agent.log_db(
                            f"🚨 ALERTA: VM Crítica {vm.nombre} detectada APAGADA. 🚑 Protocolo de resurrección iniciado.", 
                            "ACTION", 
                            {"vm": vm.nombre, "node": nodo_nombre}
                        )
                    elif str(resultado).startswith("Error"):
                         await self.agent.log_db(f"⚠️ Error verificando VM {vm.nombre}: {resultado}", "WARNING")

                except Exception as e:
                    await self.agent.log_db(f"Error en Watchdog para {vm.nombre}: {e}", "WARNING")

    class ComportamientoPrediccion(PeriodicBehaviour):
        async def run(self):
            print("🔮 CEREBRO: Iniciando ciclo de predicción SARIMA...")
            try:
                # 1. Predicciones de Servidores
                # Usamos sync_to_async para operaciones de BD bloqueantes
                servidores = await sync_to_async(list)(ProxmoxServer.objects.filter(is_active=True))
                
                for server in servidores:
                    print(f"   ↳ Prediciendo para servidor: {server.name}")
                    # Ejecutar entrenamiento en hilo aparte para no bloquear el loop
                    await sync_to_async(train_and_predict_server)(server.id)
                
                # 2. Predicciones de VMs (Anomalías)
                # Solo predecimos para VMs monitoreadas para ahorrar recursos
                vms = await sync_to_async(list)(MaquinaVirtual.objects.filter(is_monitored=True))
                
                for vm in vms:
                    # Opcional: Solo predecir si tiene suficientes datos (se maneja en logic)
                    await sync_to_async(train_and_predict_vm)(vm.vm_id)

                await self.agent.log_db("Ciclo de predicción completado", "INFO")
                print("✨ CEREBRO: Predicciones generadas exitosamente.")

            except Exception as e:
                print(f"❌ Error en ciclo de predicción: {e}")
                await self.agent.log_db(f"Error en predicción: {e}", "WARNING")

    async def setup(self):
        print("🔌 CEREBRO: Iniciando sistema de almacenamiento...")
        
        # Comportamiento de Escucha (Mensajes XMPP)
        b = self.ComportamientoEscucha()
        self.add_behaviour(b)
        
        # Comportamiento Watchdog (cada 30 segundos)
        w = self.ComportamientoWatchdog(period=30)
        self.add_behaviour(w)

        # Comportamiento Predicción (cada 1 hora = 3600s)
        # Inicia inmediatamente al arrancar y luego repite
        p = self.ComportamientoPrediccion(period=3600)
        self.add_behaviour(p)