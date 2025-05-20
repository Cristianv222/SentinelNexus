import os
import django

# Configura el entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

# Importa los modelos
from django.db import models
from submodulos.models import Nodo, ProxmoxServer

# Busca o crea el servidor Proxmox
proxmox_server, created_server = ProxmoxServer.objects.get_or_create(
    name='prx2',
    defaults={
        'hostname': 'prx2',
        'username': 'root',  # Ajusta esto
        'password': 'secure_password',  # Ajusta esto
        'is_active': True
    }
)

if created_server:
    print(f"Servidor Proxmox creado: {proxmox_server.name}")
else:
    print(f"Usando servidor Proxmox existente: {proxmox_server.name}")

# Busca o crea el nodo
nodo, created_node = Nodo.objects.get_or_create(
    nombre='prx2',
    defaults={
        'proxmox_server': proxmox_server,
        'hostname': 'prx2',
        'ip_address': '127.0.0.1',  # Ajusta a la IP real
        'estado': 'activo'
    }
)

if created_node:
    print(f"Nodo creado: {nodo.nombre}")
else:
    print(f"Nodo existente: {nodo.nombre}")

# Verifica si hay VMs que necesitan actualizarse
from submodulos.models import MaquinaVirtual
vms_sin_nodo = MaquinaVirtual.objects.filter(vmid__in=[112, 113, 114])
vms_actualizadas = 0

for vm in vms_sin_nodo:
    if vm.nodo_id != nodo.nodo_id:
        vm.nodo = nodo
        vm.save()
        vms_actualizadas += 1
        print(f"VM actualizada: {vm.nombre} (ID: {vm.vmid})")

print(f"Total de VMs actualizadas: {vms_actualizadas}")