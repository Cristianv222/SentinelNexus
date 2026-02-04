import asyncio
import json
import psutil
import socket
import slixmpp
from spade.agent import Agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from proxmoxer import ProxmoxAPI
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ======================================================
# 💉 CONFIGURACIÓN PERMISIVA DE TLS
# ======================================================
# Ya aplicado en run_vigilante_agent.py, pero aseguramos aquí por si se corre individual
import slixmpp

# No re-aplicamos el parche global si ya existe, pero nos aseguramos que las clases lo tengan


class MonitorAgent(Agent):
    
    def __init__(self, jid, password, proxmox_ip, proxmox_user, proxmox_pass):
        super().__init__(jid, password)
        self.proxmox_ip = proxmox_ip
        self.proxmox_user = proxmox_user
        self.proxmox_pass = proxmox_pass
        
    class ComportamientoVigilancia(CyclicBehaviour):
        async def run(self):
            # Recolección de métricas
            try:
                # Acceder a las credenciales desde el agente
                ip = self.agent.proxmox_ip
                user = self.agent.proxmox_user
                password = self.agent.proxmox_pass
                
                # Conectar a Proxmox (Idealmente esto se haría una vez, pero por robustez lo hacemos aquí o verificamos conexión)
                # Para evitar reconectar cada vez, podríamos guardarlo en self.agent.proxmox_client si no existe
                if not hasattr(self.agent, 'proxmox_client'):
                    print(f"[{ip}] Conectando a Proxmox API...")
                    self.agent.proxmox_client = ProxmoxAPI(ip, user=user, password=password, verify_ssl=False)
                
                proxmox = self.agent.proxmox_client
                
                # Obtener nodos
                try:
                    nodes = proxmox.nodes.get()
                except Exception as ex:
                    print(f"[{ip}] Error de conexion, reintentando login: {ex}")
                    # Reintentar conexión
                    self.agent.proxmox_client = ProxmoxAPI(ip, user=user, password=password, verify_ssl=False)
                    proxmox = self.agent.proxmox_client
                    nodes = proxmox.nodes.get()
                
                if not nodes:
                    print(f"[{ip}] No se encontraron nodos.")
                    return

                # Asumimos monitoreo del nodo donde estamos conectados/apuntando
                # O iteramos sobre todos los nodos que devuelve este host
                for node in nodes:
                    nombre_nodo = node['node']
                    
                    try:
                        status = proxmox.nodes(nombre_nodo).status.get()
                        
                        # Métricas del Nodo
                        cpu_uso = status.get('cpu', 0) * 100
                        mem_total = status.get('memory', {}).get('total', 1)
                        mem_usada = status.get('memory', {}).get('used', 0)
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
                                
                                # Obtener uso de CPU/RAM específico si está corriendo
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
                            print(f"Error VMs {nombre_nodo}: {e}")

                        # Preparar Payload
                        payload = {
                            "node": nombre_nodo,
                            "cpu": cpu_uso,
                            "ram": ram_uso,
                            "uptime": uptime,
                            "vms": vms_data
                        }

                        json_body = json.dumps(payload)
                        
                        print(f"({ip} -> {nombre_nodo}) ENVIANDO DATOS (Con {len(vms_data)} VMs)")
                        
                        # Updated to target the shared vigilante_1 user (Temporary fix)
                        msg = Message(to="cerebro@sentinelnexus.local")
                        msg.set_metadata("performative", "inform")
                        msg.body = json_body
                        await self.send(msg)
                        
                    except Exception as node_metrics_error:
                         print(f"Error obteniendo metricas de nodo {nombre_nodo}: {node_metrics_error}")

            except Exception as e:
                print(f"ERROR GENERAL MONITOR ({self.agent.proxmox_ip}): {e}")
            
            await asyncio.sleep(15)

    async def setup(self):
        print(f"MONITOR INICIADO PARA: {self.proxmox_ip}")
        
        # Configuración explícita de seguridad para este agente
        # Configuración explícita de seguridad (Solo para Slixmpp legacy)
        if hasattr(self, 'client') and self.client:
             try:
                 # Intentamos configurar modo legacy solo si existe el atributo (Slixmpp)
                 if hasattr(self.client, 'use_tls'):
                     self.client.use_tls = False
                     self.client.use_ssl = False
                 
                 # Esta línea rompe aioxmpp porque no tiene .plugin
                 if hasattr(self.client, 'plugin'):
                     self.client.plugin['feature_mechanisms'].unencrypted_plain = True
             except:
                 pass

        b = self.ComportamientoVigilancia()
        self.add_behaviour(b)