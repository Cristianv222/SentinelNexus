from celery import shared_task
from .models import Server  # Ajusta según tu modelo
import time
from proxmoxer import ProxmoxAPI
import psutil

@shared_task
def monitor_proxmox_servers():
    """Tarea para monitorear servidores Proxmox y guardar métricas en la base de datos"""
    servers = Server.objects.filter(active=True)
    results = []
    
    for server in servers:
        try:
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
            from .models import ServerMetric
            metric = ServerMetric.objects.create(
                server=server,
                cpu_usage=node_status['cpu'],
                memory_usage=node_status['memory']['used'] / node_status['memory']['total'] * 100,
                disk_usage=node_status['rootfs']['used'] / node_status['rootfs']['total'] * 100,
                uptime=node_status['uptime']
            )
            results.append(f"Servidor {server.name}: métricas guardadas correctamente")
        except Exception as e:
            results.append(f"Error al monitorear servidor {server.name}: {str(e)}")
    
    return results

@shared_task
def collect_local_metrics():
    """Tarea para recopilar métricas locales del sistema"""
    try:
        # Recopilar métricas locales usando psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Guardar en la base de datos
        from .models import LocalMetric
        metric = LocalMetric.objects.create(
            cpu_usage=cpu_percent,
            memory_usage=memory.percent,
            disk_usage=disk.percent
        )
        return "Métricas locales guardadas correctamente"
    except Exception as e:
        return f"Error al recopilar métricas locales: {str(e)}"