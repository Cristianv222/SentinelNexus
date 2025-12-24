import os
import django
import sys

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import VMMetric, ServerMetric

def verificar_datos():
    print(f"--- Verificando Base de Datos ---")
    
    server_count = ServerMetric.objects.count()
    vm_count = VMMetric.objects.count()
    
    print(f"[METRICAS SERVIDOR] Total registros: {server_count}")
    print("Últimos 3 registros:")
    for sm in ServerMetric.objects.order_by('-created_at')[:3]:
        print(f" - {sm}")

    print(f"\n[METRICAS VMs] Total registros: {vm_count}")
    print("Últimos 5 registros:")
    for vm in VMMetric.objects.order_by('-created_at')[:5]:
        print(f" - {vm}")

if __name__ == '__main__':
    verificar_datos()
