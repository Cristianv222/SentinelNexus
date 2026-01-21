import time
import asyncio
import slixmpp
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from asgiref.sync import sync_to_async
from submodulos.models import AgentServerMetric, VMMetric, AgentLog, MaquinaVirtual, Nodo
from submodulos.proxmox_service import proxmox_service
from spade.behaviour import CyclicBehaviour, PeriodicBehaviour

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
    @sync_to_async
    def guardar_metrica_servidor(self, nodo, cpu, ram, up):
        AgentServerMetric.objects.create(
            node_name=nodo,
            cpu_usage=cpu,
            ram_usage=ram,
            uptime=up
        )
        
    @sync_to_async
    def guardar_metrica_vm(self, nombre, servidor, cpu, ram, status):
        VMMetric.objects.create(
            vm_name=nombre,
            server_origin=servidor,
            cpu_usage=cpu,
            ram_usage=ram,
            status=status
        )

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
                
                # Intentamos parsear como JSON (Nuevo formato con VMs)
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
                        
                        # Log de alerta si hay carga (Simulación de pensamiento)
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

    async def execute_watchdog_check(self):
        """Lógica de Watchdog desacoplada para ejecución manual o automática"""
        # 1. Obtener VMs críticas
        vms_criticas = await sync_to_async(list)(MaquinaVirtual.objects.filter(is_critical=True))
        
        if not vms_criticas:
            return

        for vm in vms_criticas:
            try:
                # 2. Obtener estado real desde Proxmox (Sincrono, envolver si bloquea mucho)
                # Nota: idealmente proxmox_service debería ser async o usar run_in_executor
                nodo_nombre = await sync_to_async(lambda: vm.nodo.nombre)()
                
                # [UPGRADE] Usar proxmox_manager para soportar múltiples servidores
                # Buscamos la conexión correcta para este nodo
                
                from utils.proxmox_manager import proxmox_manager
                
                # Función auxiliar para ejecutar operaciones síncronas de proxmox en async
                def check_and_recover(vm_obj, node_name):
                    # Estrategia simplificada:
                    # Usar el ID del servidor Proxmox si está disponible en el modelo Nodo -> ProxmoxServer
                    server_id = None
                    try:
                        if vm_obj.nodo.proxmox_server:
                            server_id = str(vm_obj.nodo.proxmox_server.id)
                    except:
                        pass
                    
                    proxmox = None
                    if server_id:
                            proxmox = proxmox_manager.get_connection(server_id)
                    else:
                            # Fallback: Intentar con el default o iterar (Costoso)
                            from submodulos.proxmox_service import proxmox_service
                            proxmox = proxmox_service.proxmox

                    if not proxmox:
                            return "Error: No connection"

                    # Obtener estado actual
                    # API: /nodes/{node}/qemu/{vmid}/status/current
                    try:
                        if vm_obj.vm_type == 'qemu':
                            status_info = proxmox.nodes(node_name).qemu(vm_obj.vmid).status.current.get()
                        else:
                            status_info = proxmox.nodes(node_name).lxc(vm_obj.vmid).status.current.get()
                    except Exception as e:
                        return f"Status Check Error: {e}"

                    estado_actual = status_info.get('status', 'unknown')
                    
                    # Lógica de resurrección
                    if estado_actual == 'stopped':
                        # Intentar iniciar
                        if vm_obj.vm_type == 'qemu':
                            proxmox.nodes(node_name).qemu(vm_obj.vmid).status.start.post()
                        else:
                            proxmox.nodes(node_name).lxc(vm_obj.vmid).status.start.post()
                        return "RESTARTED"
                    
                    return "OK"

                # Ejecutar en hilo aparte para no bloquear el loop async
                resultado = await sync_to_async(check_and_recover)(vm, nodo_nombre)
                
                if resultado == "RESTARTED":
                    await self.log_db(
                        f"🚨 ALERTA: VM Crítica {vm.nombre} detectada APAGADA. 🚑 Protocolo de resurrección iniciado.", 
                        "ACTION", 
                        {"vm": vm.nombre, "node": nodo_nombre}
                    )
                elif str(resultado).startswith("Error"):
                        await self.log_db(f"⚠️ Error verificando VM {vm.nombre}: {resultado}", "WARNING")

            except Exception as e:
                await self.log_db(f"Error en Watchdog para {vm.nombre}: {e}", "WARNING")

    class ComportamientoWatchdog(PeriodicBehaviour):
        async def run(self):
            await self.agent.execute_watchdog_check()

    async def setup(self):
        print("🔌 CEREBRO: Iniciando sistema de almacenamiento...")
        
        # Comportamiento de Escucha (Mensajes XMPP)
        b = self.ComportamientoEscucha()
        self.add_behaviour(b)
        
        # Comportamiento Watchdog (cada 30 segundos)
        w = self.ComportamientoWatchdog(period=30)
        self.add_behaviour(w)