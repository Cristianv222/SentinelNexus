import os
import django
import numpy as np
from datetime import timedelta
from django.utils import timezone

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import ProxmoxServer, ServerMetric

def populate():
    print("Iniciando simulación de datos históricos para ServerMetric...")
    servers = ProxmoxServer.objects.all()
    if not servers:
        print("¡Error: No se encontraron servidores Proxmox en la Base de Datos!")
        return
        
    now = timezone.now()
    
    for server in servers:
        print(f"\n-> Generando historial para: {server.name} ({server.hostname})")
        
        # Limpiar registros existentes para este servidor para evitar basura
        ServerMetric.objects.filter(server=server).delete()
        
        # 1. Crear temporalmente los registros (Django auto_now_add los guardará con la fecha actual)
        metrics_to_create = []
        for h in range(168):  # 168 horas = 7 días de datos
            # Crear valor de CPU cíclico diario (pico a las 14:00, valle a las 03:00)
            target_time = now - timedelta(hours=167 - h)
            hour_of_day = target_time.hour
            
            # CPU: Ciclo diario con ruido
            cpu_base = 35.0 + 20.0 * np.sin(2.0 * np.pi * (hour_of_day - 8) / 24.0)
            cpu_noise = np.random.normal(0, 4)
            cpu_val = max(5.0, min(95.0, cpu_base + cpu_noise))
            
            # RAM: Ciclo diario con ruido más estable
            ram_base = 55.0 + 8.0 * np.sin(2.0 * np.pi * (hour_of_day - 10) / 24.0)
            ram_noise = np.random.normal(0, 1.5)
            ram_val = max(10.0, min(98.0, ram_base + ram_noise))
            
            # Disco: Incremental muy lento o estable
            disk_val = 40.0 + (h * 0.01) + np.random.normal(0, 0.2)
            
            metric = ServerMetric(
                server=server,
                node_name=server.node_name or "pve",
                cpu_usage=cpu_val,
                ram_usage=ram_val,
                disk_usage=disk_val,
                uptime=86400 * 10 + h * 3600  # 10 días de uptime base + horas
            )
            metrics_to_create.append(metric)
            
        # Insertar en bloque para alta velocidad
        ServerMetric.objects.bulk_create(metrics_to_create)
        
        # 2. Actualizar las fechas de registro (saltándose la restricción de auto_now_add en la actualización)
        print(f"   Ajustando fechas de registro históricas...")
        created_metrics = ServerMetric.objects.filter(server=server).order_by('id')
        for idx, m in enumerate(created_metrics):
            m.timestamp = now - timedelta(hours=167 - idx)
            m.save()
            
        print(f"   [OK] Historial de 7 días cargado con éxito para {server.name}")
        
    print("\n¡Simulación completada con éxito! Todos los servidores tienen 7 días de historial en BDD.")

if __name__ == "__main__":
    populate()
