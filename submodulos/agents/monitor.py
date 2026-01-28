import time
import asyncio
import slixmpp
import json
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from proxmoxer import ProxmoxAPI
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================================================
# 💉 PARCHE DE CONEXIÓN (Idéntico a CerebroAgent)
# ======================================================
if not getattr(slixmpp.ClientXMPP, "_parche_aplicado", False):
    _original_init = slixmpp.ClientXMPP.__init__
    def constructor_parcheado(self, *args, **kwargs):
        print("💉 [MONITOR] Ejecutando constructor parcheado de Slixmpp")
        _original_init(self, *args, **kwargs)
        self.plugin['feature_mechanisms'].unencrypted_plain = True
        self.use_ssl = False
        self.use_tls = False
        self.force_starttls = False
        self.disable_starttls = True
    slixmpp.ClientXMPP.__init__ = constructor_parcheado
    slixmpp.ClientXMPP._parche_aplicado = True

class MonitorAgent(Agent):
    
    def __init__(self, jid, password, proxmox_ip, proxmox_user, proxmox_pass):
        # Igualar constructor a CerebroAgent (sin argumentos extra de seguridad)
        super().__init__(jid, password)
        self.proxmox_ip = proxmox_ip
        self.proxmox_user = proxmox_user
        self.proxmox_pass = proxmox_pass
        
        # --- PARCHE DE INSTANCIA (MODIFICACIÓN DIRECTA) ---
        print(f"🕵️ [MONITOR] INIT COMPLETO. Cliente tipo: {type(self.client)}")
        
        # 1. Eliminar plugin STARTTLS de la instancia
        if hasattr(self, 'client'):
            try:
                if 'feature_starttls' in self.client.plugin:
                    del self.client.plugin['feature_starttls']
                    print("✅ [MONITOR] Plugin feature_starttls ELIMINADO de self.client")
                else:
                    print("⚠️ [MONITOR] feature_starttls no encontrado en plugins")
                    
                # 2. Forzar flags en el cliente (redundancia)
                self.client.use_tls = False
                self.client.use_ssl = False
                self.client.force_starttls = False
                self.client.disable_starttls = True
                
                # 3. Hackear feature mechanisms
                if 'feature_mechanisms' in self.client.plugin:
                    self.client.plugin['feature_mechanisms'].unencrypted_plain = True
                    
            except Exception as e:
                print(f"❌ [MONITOR] Error aplicando parche de instancia: {e}")
        # --------------------------------------------------
        
        # Override de seguridad adicional
        self.use_tls = False
        self.use_ssl = False
        self.force_starttls = False
        self.disable_starttls = True

    class ComportamientoVigilancia(CyclicBehaviour):
        async def run(self):
            ip = self.agent.proxmox_ip
            
            try:
                proxmox = ProxmoxAPI(
                    ip,
                    user=self.agent.proxmox_user,
                    password=self.agent.proxmox_pass,
                    verify_ssl=False,
                    timeout=5 
                )
                
                nodes = proxmox.nodes.get()
                if not nodes:
                    return

                nombre_nodo = nodes[0]['node']
                status = proxmox.nodes(nombre_nodo).status.get()
                
                # Métricas del Nodo
                cpu_uso = status.get('cpu', 0) * 100
                mem_total = status['memory']['total']
                mem_usada = status['memory']['used']
                ram_uso = (mem_usada / mem_total) * 100 if mem_total > 0 else 0
                uptime = status.get('uptime', 0)

                # RECOLECCIÓN DE VMs
                vms_data = []
                try:
                    qemu_vms = proxmox.nodes(nombre_nodo).qemu.get()
                    for vm in qemu_vms:
                        vmid = vm.get('vmid')
                        name = vm.get('name', f'VM-{vmid}')
                        vm_status = vm.get('status', 'unknown')
                        
                        vm_cpu = vm.get('cpu', 0)
                        if vm_cpu is None: vm_cpu = 0
                        vm_cpu = vm_cpu * 100 
                        
                        vm_mem_max = vm.get('maxmem', 1)
                        vm_mem = vm.get('mem', 0)
                        if vm_mem is None: vm_mem = 0
                        vm_ram_pct = (vm_mem / vm_mem_max) * 100 if vm_mem_max > 0 else 0
                        
                        vms_data.append({
                            'name': name,
                            'cpu': vm_cpu,
                            'ram': vm_ram_pct,
                            'status': vm_status
                        })
                except Exception as e:
                    print(f"⚠️ Error VMs {nombre_nodo}: {e}")

                payload = {
                    "node": nombre_nodo,
                    "cpu": cpu_uso,
                    "ram": ram_uso,
                    "uptime": uptime,
                    "vms": vms_data
                }

                json_body = json.dumps(payload)
                
                print(f"✅ ({ip}) ENVIANDO DATOS (Con {len(vms_data)} VMs)")

                msg = Message(to="cerebro@sentinelnexus.local")
                msg.set_metadata("performative", "inform")
                msg.body = json_body
                await self.send(msg)

            except Exception as e:
                print(f"❌ ERROR ({ip}): {e}")
            
            await asyncio.sleep(15)

    async def setup(self):
        print(f"🔌 MONITOR INICIADO PARA: {self.proxmox_ip}")
        
        # --- ULTIMA LINEA DE DEFENSA: Desactivar en tiempo de ejecución ---
        # A veces SPADE/Slixmpp reinicializan plugins al conectar.
        # Aquí forzamos el apagado una vez más.
        if hasattr(self, 'client') and self.client:
             if 'feature_mechanisms' in self.client.plugin:
                 self.client.plugin['feature_mechanisms'].unencrypted_plain = True
             self.client.use_tls = False
             self.client.use_ssl = False
             self.client.force_starttls = False
             self.client.disable_starttls = True
             print(f"🛡️ SAFETY CHECK ({self.jid}): TLS Forced OFF inside setup()")
        
        # También en 'self' por si acaso
        self.use_tls = False
        self.force_starttls = False
        self.disable_starttls = True
        # ------------------------------------------------------------------

        b = self.ComportamientoVigilancia()
        self.add_behaviour(b)