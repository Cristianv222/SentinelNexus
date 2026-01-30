from celery import shared_task
from .models import Server, ServerMetric, LocalMetric  # Importar todos los modelos necesarios
import time
from proxmoxer import ProxmoxAPI
import psutil
import logging

from celery import shared_task
from django.utils import timezone
from datetime import timedelta, datetime
import logging

# Configurar logging
logger = logging.getLogger(__name__)

@shared_task
def monitor_proxmox_servers():
    """Tarea para monitorear servidores Proxmox y guardar métricas en la base de datos"""
    logger.info("Iniciando monitoreo de servidores Proxmox")
    servers = Server.objects.filter(active=True)
    
    if not servers.exists():
        logger.warning("No hay servidores activos para monitorear")
        return "No hay servidores activos para monitorear"
    
    results = []
    
    for server in servers:
        try:
            logger.info(f"Conectando a servidor: {server.name} ({server.host})")
            # Conectar a Proxmox
            proxmox = ProxmoxAPI(
                server.host,
                user=server.username,
                password=server.password,
                verify_ssl=False
            )
            
            # Obtener métricas del nodo
            node_status = proxmox.nodes(server.node).status.get()
            
            # Guardar métricas en la base de datos
            metric = ServerMetric.objects.create(
                server=server,
                cpu_usage=node_status['cpu'],
                memory_usage=node_status['memory']['used'] / node_status['memory']['total'] * 100,
                disk_usage=node_status['rootfs']['used'] / node_status['rootfs']['total'] * 100,
                uptime=node_status['uptime']
            )
            
            logger.info(f"Métricas guardadas para {server.name} con ID: {metric.id}")
            results.append(f"Servidor {server.name}: métricas guardadas correctamente")
        except Exception as e:
            logger.error(f"Error al monitorear servidor {server.name}: {str(e)}", exc_info=True)
            results.append(f"Error al monitorear servidor {server.name}: {str(e)}")
    
    return results

@shared_task
def collect_local_metrics():
    """Tarea para recopilar métricas locales del sistema"""
    try:
        logger.info("Recopilando métricas locales del sistema")
        # Recopilar métricas locales usando psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        logger.info(f"Métricas obtenidas - CPU: {cpu_percent}%, Memoria: {memory.percent}%, Disco: {disk.percent}%")
        
        # Guardar en la base de datos
        metric = LocalMetric.objects.create(
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent
        )
        
        logger.info(f"Métricas locales guardadas con ID: {metric.id}")
        return f"Métricas locales guardadas correctamente - CPU: {cpu_percent}%, Memoria: {memory.percent}%, Disco: {disk.percent}%"
    except Exception as e:
        logger.error(f"Error al recopilar métricas locales: {str(e)}", exc_info=True)
        return f"Error al recopilar métricas locales: {str(e)}"

# Añadimos la tarea faltante que Celery está intentando ejecutar
@shared_task
def collect_local_metrics_hybrid():
    """Tarea para recopilar métricas híbridas locales y remotas"""
    try:
        logger.info("Recopilando métricas híbridas")
        # Recopilar métricas locales
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Guardar en la base de datos
        metric = LocalMetric.objects.create(
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent
        )
        
        logger.info(f"Métricas híbridas guardadas con ID: {metric.id}")
        return "Métricas híbridas guardadas correctamente"
    except Exception as e:
        logger.error(f"Error al recopilar métricas híbridas: {str(e)}", exc_info=True)
        return f"Error al recopilar métricas híbridas: {str(e)}"
    
@shared_task
def monitor_all_proxmox_servers():
    """Monitorea todos los servidores Proxmox configurados"""
    from utils.proxmox_manager import proxmox_manager
    from submodulos.models import ServerMetric, ProxmoxServer
    
    results = []
    
    # Obtener todos los nodos configurados
    active_nodes = proxmox_manager.get_all_nodes()
    
    for node_key, node_config in active_nodes.items():
        try:
            # Conectar al servidor
            proxmox = proxmox_manager.get_connection(node_key)
            nodes = proxmox.nodes.get()
            
            # Obtener o crear el registro del servidor en BD
            server, created = ProxmoxServer.objects.get_or_create(
                hostname=node_config['host'],
                defaults={
                    'name': node_config.get('name', node_key),
                    'username': node_config['user'],
                    'password': node_config['password'],
                    'verify_ssl': node_config.get('verify_ssl', False),
                    'is_active': True
                }
            )
            
            for node in nodes:
                node_name = node['node']
                node_status = proxmox.nodes(node_name).status.get()
                
                # Guardar métricas del NODO
                ServerMetric.objects.create(
                    server=server,
                    cpu_usage=node_status.get('cpu', 0) * 100,
                    ram_usage=(node_status['memory']['used'] / node_status['memory']['total']) * 100,
                    disk_usage=(node_status['rootfs']['used'] / node_status['rootfs']['total']) * 100,
                    uptime=node_status.get('uptime', 0),
                    # status field removed as it does not exist in ServerMetric model
                )
                
                # --- NUEVO: Recolectar métricas de las VMs en este nodo ---
                try:
                    # 1. Qeme/KVM
                    for vm in proxmox.nodes(node_name).qemu.get():
                        if vm.get('status') == 'running':
                            _save_vm_metric(vm, node_name, 'qemu')
                    
                    # 2. LXC Containers
                    for ct in proxmox.nodes(node_name).lxc.get():
                         if ct.get('status') == 'running':
                            _save_vm_metric(ct, node_name, 'lxc')
                            
                except Exception as vm_e:
                    logger.error(f"Error recolectando VMs en {node_name}: {vm_e}")

                results.append(f"✓ {node_config['name']} - {node_name}")
                
        except Exception as e:
            logger.error(f"Error monitoreando {node_key}: {str(e)}")
            results.append(f"✗ {node_config.get('name', node_key)}: {str(e)}")
    
    return f"Monitoreo completado: {', '.join(results)}"

def _save_vm_metric(vm_data, node_name, vm_type):
    """Auxiliar para guardar métricas de VM/CT"""
    from submodulos.models import MaquinaVirtual, VMMetric
    
    # Usamos VMMetric (el modelo simple compatible con lo que pidió el usuario)
    # y buscamos/creamos la VM solo referencialmente por nombre
    try:
        # Calcular porcentajes
        max_cpu = vm_data.get('cpus', 1)
        current_cpu = vm_data.get('cpu', 0) # usually normalized 0-1 or 0-cpus
        # Proxmox manda 'cpu' como 0.5 (50% de 1 core) o similar.
        # Para display simple 0-100%:
        cpu_pct = current_cpu * 100
        
        max_mem = vm_data.get('maxmem', 1)
        cur_mem = vm_data.get('mem', 0)
        ram_pct = (cur_mem / max_mem) * 100 if max_mem > 0 else 0
        
        VMMetric.objects.create(
            vm_name=vm_data.get('name', f"VM-{vm_data.get('vmid')}"),
            server_origin=node_name,
            cpu_usage=cpu_pct,
            ram_usage=ram_pct,
            status=vm_data.get('status', 'unknown')
        )
    except Exception as e:
        logger.error(f"Error guardando metric VM {vm_data.get('vmid')}: {e}")