from celery import shared_task
from .models import Server, ServerMetric, LocalMetric  # Importar todos los modelos necesarios
import time
from proxmoxer import ProxmoxAPI
import psutil
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