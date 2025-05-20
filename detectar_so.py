import os
import django
import sys
from django.utils import timezone

# Configura el entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

# Importar modelos y servicios
from submodulos.models import SistemaOperativo, MaquinaVirtual, Nodo, ProxmoxServer
from submodulos import proxmox_service  # Asumiendo que aquí está tu lógica de Proxmox

print("Iniciando detección de sistemas operativos en VMs...")

# Crear un sistema operativo por defecto
sistema_op, created = SistemaOperativo.objects.get_or_create(
    nombre='Linux',
    version='Generic',
    tipo='Linux',
    arquitectura='x86_64',
    defaults={'activo': True}
)

if created:
    print(f"Sistema operativo creado: {sistema_op}")
else:
    print(f"Usando sistema operativo existente: {sistema_op}")

# Buscar todas las máquinas virtuales sin sistema operativo
vms_sin_so = MaquinaVirtual.objects.filter(sistema_operativo__isnull=True)
print(f"VMs sin sistema operativo: {vms_sin_so.count()}")

# Ver si también hay VMs específicas para actualizar
vmids_especificos = [112, 113, 114]
vms_especificas = MaquinaVirtual.objects.filter(vmid__in=vmids_especificos)
print(f"VMs específicas encontradas: {vms_especificas.count()}")

# Actualizar todas las VMs que necesiten sistema operativo
vms_a_actualizar = (vms_sin_so | vms_especificas).distinct()
vms_actualizadas = 0

for vm in vms_a_actualizar:
    try:
        print(f"Actualizando VM: {vm.nombre} (ID: {vm.vmid})")
        
        # Aquí podrías intentar detectar el SO real usando proxmox_service
        # Por ahora, solo asignamos el SO por defecto
        vm.sistema_operativo = sistema_op
        vm.save(update_fields=['sistema_operativo'])
        
        vms_actualizadas += 1
        print(f"VM actualizada exitosamente")
    except Exception as e:
        print(f"Error al actualizar VM {vm.vmid}: {str(e)}")

print(f"\nTotal de VMs actualizadas: {vms_actualizadas}")

# Verificar si aún hay VMs sin sistema operativo
vms_sin_so_final = MaquinaVirtual.objects.filter(sistema_operativo__isnull=True)
if vms_sin_so_final.exists():
    print(f"ADVERTENCIA: Aún hay {vms_sin_so_final.count()} VMs sin sistema operativo")
else:
    print("Éxito: Todas las VMs tienen sistema operativo asignado")