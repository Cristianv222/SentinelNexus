import time
from datetime import datetime
from proxmoxer import ProxmoxAPI
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from .models import (
    ProxmoxServer, Nodo, SistemaOperativo, MaquinaVirtual,
    TipoRecurso, RecursoFisico, AsignacionRecursosInicial
)

class ProxmoxSynchronizer:
    def __init__(self, proxmox_server_id=None):
        """
        Inicializa el sincronizador con un servidor Proxmox específico o utiliza
        la configuración global si no se proporciona uno.
        """
        if proxmox_server_id:
            try:
                server = ProxmoxServer.objects.get(id=proxmox_server_id)
                self.proxmox = ProxmoxAPI(
                    server.hostname,
                    user=server.username,
                    password=server.password,
                    verify_ssl=server.verify_ssl
                )
                self.server = server
            except ProxmoxServer.DoesNotExist:
                raise ValueError(f"Servidor Proxmox con ID {proxmox_server_id} no encontrado")
        else:
            # Usar configuración global de settings.py
            self.proxmox = ProxmoxAPI(
                settings.PROXMOX['host'],
                user=settings.PROXMOX['user'],
                password=settings.PROXMOX['password'],
                verify_ssl=settings.PROXMOX['verify_ssl']
            )
            # Crear o actualizar el registro del servidor en la base de datos
            self.server, created = ProxmoxServer.objects.update_or_create(
                hostname=settings.PROXMOX['host'],
                defaults={
                    'name': f"Proxmox-{settings.PROXMOX['host']}",
                    'username': settings.PROXMOX['user'],
                    'password': settings.PROXMOX['password'],  # Considera encriptar esto
                    'verify_ssl': settings.PROXMOX['verify_ssl'],
                    'is_active': True
                }
            )

    @transaction.atomic
    def sync_all(self):
        """
        Sincroniza todos los datos: nodos, recursos y máquinas virtuales.
        Usa una transacción para garantizar la integridad de los datos.
        """
        # 1. IMPORTANTE: Primero creamos los tipos de recursos
        self.sync_resource_types()
        
        # 2. Luego los nodos
        self.sync_nodes()
        
        # 3. Finalmente las máquinas
        self.sync_vms()
        
        return {
            'status': 'success',
            'message': 'Sincronización completada correctamente'
        }

    def sync_nodes(self):
        """
        Sincroniza información de nodos desde Proxmox.
        """
        nodes = self.proxmox.nodes.get()
        for node_data in nodes:
            # Obtener información detallada del nodo
            node_detail = self.proxmox.nodes(node_data['node']).status.get()
            
            # Crear o actualizar el nodo en la base de datos
            node, created = Nodo.objects.update_or_create(
                nombre=node_data['node'],
                proxmox_server=self.server,
                defaults={
                    'hostname': node_data['node'],
                    'ip_address': node_detail.get('ip', '0.0.0.0'),  # Obtener IP real si está disponible
                    'estado': 'activo' if node_data['status'] == 'online' else 'inactivo',
                    'tipo_hardware': node_detail.get('cpuinfo', {}).get('model', 'Desconocido')
                }
            )
            
            # Sincronizar recursos del nodo
            self.sync_node_resources(node, node_detail)

    def sync_resource_types(self):
        """
        Asegura que existan los tipos de recursos básicos en la base de datos.
        """
        resource_types = [
            {'nombre': 'CPU', 'unidad_medida': 'Cores', 'descripcion': 'Procesador'},
            {'nombre': 'RAM', 'unidad_medida': 'MB', 'descripcion': 'Memoria RAM'},
            {'nombre': 'Almacenamiento', 'unidad_medida': 'GB', 'descripcion': 'Espacio de disco'}
        ]
        
        for rt in resource_types:
            TipoRecurso.objects.get_or_create(
                nombre=rt['nombre'],
                defaults={
                    'unidad_medida': rt['unidad_medida'],
                    'descripcion': rt['descripcion']
                }
            )

    def sync_node_resources(self, node, node_detail):
        """
        Sincroniza los recursos físicos de un nodo específico.
        """
        # Obtener tipos de recursos
        cpu_type = TipoRecurso.objects.get(nombre='CPU')
        ram_type = TipoRecurso.objects.get(nombre='RAM')
        storage_type = TipoRecurso.objects.get(nombre='Almacenamiento')
        
        # Sincronizar CPU
        cpu_cores = node_detail.get('cpuinfo', {}).get('cpus', 0)
        RecursoFisico.objects.update_or_create(
            nodo=node,
            tipo_recurso=cpu_type,
            defaults={
                'nombre': f"CPU-{node.nombre}",
                'capacidad_total': cpu_cores,
                'capacidad_disponible': cpu_cores - node_detail.get('cpu', 0),
                'estado': 'activo'
            }
        )
        
        # Sincronizar RAM (convertir de bytes a MB)
        total_ram = node_detail.get('memory', {}).get('total', 0) / (1024 * 1024)
        used_ram = node_detail.get('memory', {}).get('used', 0) / (1024 * 1024)
        RecursoFisico.objects.update_or_create(
            nodo=node,
            tipo_recurso=ram_type,
            defaults={
                'nombre': f"RAM-{node.nombre}",
                'capacidad_total': total_ram,
                'capacidad_disponible': total_ram - used_ram,
                'estado': 'activo'
            }
        )
        
        # Sincronizar almacenamiento (obtener de storages)
        try:
            storages = self.proxmox.nodes(node.nombre).storage.get()
            total_storage = 0
            available_storage = 0
            
            for storage in storages:
                if storage.get('active', 0) == 1:
                    total_storage += storage.get('total', 0) / (1024 * 1024 * 1024)  # Convertir a GB
                    available_storage += storage.get('avail', 0) / (1024 * 1024 * 1024)
            
            RecursoFisico.objects.update_or_create(
                nodo=node,
                tipo_recurso=storage_type,
                defaults={
                    'nombre': f"Storage-{node.nombre}",
                    'capacidad_total': total_storage,
                    'capacidad_disponible': available_storage,
                    'estado': 'activo'
                }
            )
        except Exception as e:
            print(f"Error al sincronizar almacenamiento para nodo {node.nombre}: {str(e)}")

    def sync_vms(self):
        """
        Sincroniza todas las máquinas virtuales de todos los nodos.
        """
        # Sincronizar sistemas operativos comunes primero
        self.sync_common_os()
        
        # Obtener todos los nodos
        nodes = self.proxmox.nodes.get()
        
        for node_data in nodes:
            node_name = node_data['node']
            try:
                node = Nodo.objects.get(nombre=node_name, proxmox_server=self.server)
                
                # Obtener todas las VMs (QEMU/KVM)
                try:
                    qemu_vms = self.proxmox.nodes(node_name).qemu.get()
                    for vm in qemu_vms:
                        self.process_vm(node, vm, 'qemu')
                except Exception as e:
                    print(f"Error al obtener VMs QEMU en nodo {node_name}: {str(e)}")
                
                # Obtener todos los contenedores LXC
                try:
                    lxc_containers = self.proxmox.nodes(node_name).lxc.get()
                    for container in lxc_containers:
                        self.process_vm(node, container, 'lxc')
                except Exception as e:
                    print(f"Error al obtener contenedores LXC en nodo {node_name}: {str(e)}")
                    
            except Nodo.DoesNotExist:
                print(f"Nodo {node_name} no encontrado en la base de datos.")

    def sync_common_os(self):
        """
        Asegura que existan los sistemas operativos comunes en la base de datos.
        """
        common_os = [
            {'nombre': 'Debian', 'version': '11', 'tipo': 'Linux', 'arquitectura': 'x86_64'},
            {'nombre': 'Ubuntu', 'version': '22.04', 'tipo': 'Linux', 'arquitectura': 'x86_64'},
            {'nombre': 'CentOS', 'version': '8', 'tipo': 'Linux', 'arquitectura': 'x86_64'},
            {'nombre': 'Windows', 'version': '10', 'tipo': 'Windows', 'arquitectura': 'x86_64'},
            {'nombre': 'Windows', 'version': 'Server 2019', 'tipo': 'Windows', 'arquitectura': 'x86_64'},
            {'nombre': 'Unknown', 'version': 'Unknown', 'tipo': 'Unknown', 'arquitectura': 'x86_64'},
        ]
        
        for os_data in common_os:
            SistemaOperativo.objects.get_or_create(
                nombre=os_data['nombre'],
                version=os_data['version'],
                arquitectura=os_data['arquitectura'],
                defaults={
                    'tipo': os_data['tipo'],
                    'activo': True
                }
            )

    def process_vm(self, node, vm_data, vm_type):
        """
        Procesa una máquina virtual o contenedor y lo sincroniza con la base de datos.
        """
        vmid = vm_data.get('vmid')
        name = vm_data.get('name', f"VM-{vmid}")
        status = vm_data.get('status', 'unknown')
        
        # Determinar el sistema operativo basado en la descripción o tipo
        os_type = self.determine_os(vm_data)
        
        # Crear o actualizar la máquina virtual
        vm, created = MaquinaVirtual.objects.update_or_create(
            nodo=node,
            vmid=vmid,
            defaults={
                'nombre': name,
                'hostname': name,
                'sistema_operativo': os_type,
                'vm_type': vm_type,
                'estado': status,
                'is_monitored': True,
                'last_checked': timezone.now()
            }
        )
        
        # Si es una VM nueva o queremos actualizar recursos, asignarle recursos
        # NOTA: Quitamos el "if created" para que actualice recursos si cambiaron
        self.assign_initial_resources(node, vm, vm_data, vm_type)
        
        return vm

    def determine_os(self, vm_data):
        """
        Determina el sistema operativo basado en los datos de la VM.
        """
        # Intentar deducir del campo 'ostype' o 'template'
        os_info = vm_data.get('ostype', '') or vm_data.get('template', '')
        
        # Mapeo simple basado en palabras clave
        if 'win' in os_info.lower():
            if 'server' in os_info.lower():
                return SistemaOperativo.objects.get(nombre='Windows', version='Server 2019')
            return SistemaOperativo.objects.get(nombre='Windows', version='10')
        elif 'ubuntu' in os_info.lower():
            return SistemaOperativo.objects.get(nombre='Ubuntu', version='22.04')
        elif 'debian' in os_info.lower():
            return SistemaOperativo.objects.get(nombre='Debian', version='11')
        elif 'cent' in os_info.lower():
            return SistemaOperativo.objects.get(nombre='CentOS', version='8')
        
        # Sistema operativo desconocido por defecto
        return SistemaOperativo.objects.get(nombre='Unknown', version='Unknown')

    def assign_initial_resources(self, node, vm, vm_data, vm_type):
        """
        Asigna recursos iniciales a una máquina virtual recién creada.
        """
        try:
            # Obtener recursos del nodo
            cpu_resource = RecursoFisico.objects.get(nodo=node, tipo_recurso__nombre='CPU')
            ram_resource = RecursoFisico.objects.get(nodo=node, tipo_recurso__nombre='RAM')
            storage_resource = RecursoFisico.objects.get(nodo=node, tipo_recurso__nombre='Almacenamiento')
            
            # Obtener detalles de la VM para asignar recursos precisos
            if vm_type == 'qemu':
                vm_config = self.proxmox.nodes(node.nombre).qemu(vm.vmid).config.get()
                
                # Asignar CPU
                cpu_cores = vm_config.get('sockets', 1) * vm_config.get('cores', 1)
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=cpu_resource,
                    cantidad_asignada=cpu_cores
                )
                
                # Asignar RAM (convertir a MB)
                ram_mb = vm_config.get('memory', 512)
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=ram_resource,
                    cantidad_asignada=ram_mb
                )
                
                # Asignar almacenamiento (estimado)
                storage_gb = 20  # Valor por defecto
                for key, value in vm_config.items():
                    if key.startswith('scsi') or key.startswith('virtio') or key.startswith('ide'):
                        if 'size' in value:
                            # Convertir de formato Proxmox (ej: 32G) a GB
                            size_str = value.split('size=')[1].split(',')[0]
                            if 'G' in size_str:
                                storage_gb += float(size_str.replace('G', ''))
                            elif 'T' in size_str:
                                storage_gb += float(size_str.replace('T', '')) * 1024
                
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=storage_resource,
                    cantidad_asignada=storage_gb
                )
            
            # Proceso para LXC (CORREGIDO PARA LEER CADENAS DE TEXTO)
            elif vm_type == 'lxc':
                lxc_config = self.proxmox.nodes(node.nombre).lxc(vm.vmid).config.get()
                
                # Asignar CPU
                cpu_cores = lxc_config.get('cores', 1)
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=cpu_resource,
                    cantidad_asignada=cpu_cores
                )
                
                # Asignar RAM (convertir a MB)
                ram_mb = lxc_config.get('memory', 512)
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=ram_resource,
                    cantidad_asignada=ram_mb
                )
                
                # --- CORRECCION DISCO LXC ---
                rootfs_data = lxc_config.get('rootfs', '')
                storage_gb = 8  # Valor por defecto

                # Caso 1: Proxmox devuelve texto (ej: "local-lvm:vm-100-disk-0,size=8G")
                if isinstance(rootfs_data, str):
                    parts = rootfs_data.split(',')
                    for part in parts:
                        if part.strip().startswith('size='):
                            val_str = part.split('=')[1]
                            if 'G' in val_str:
                                storage_gb = float(val_str.replace('G', ''))
                            elif 'T' in val_str:
                                storage_gb = float(val_str.replace('T', '')) * 1024
                            break
                
                # Caso 2: Proxmox devuelve diccionario (raro, pero posible)
                elif isinstance(rootfs_data, dict):
                    val_str = rootfs_data.get('size', '8G')
                    if isinstance(val_str, str):
                        if 'G' in val_str:
                            storage_gb = float(val_str.replace('G', ''))
                # -----------------------------
                
                AsignacionRecursosInicial.objects.create(
                    maquina_virtual=vm,
                    recurso=storage_resource,
                    cantidad_asignada=storage_gb
                )
        
        except Exception as e:
            print(f"Error al asignar recursos iniciales para VM {vm.nombre}: {str(e)}")

# Función para usar en vistas o comandos
def sync_proxmox_data(server_id=None):
    """
    Función para sincronizar datos de Proxmox desde vistas o comandos.
    """
    try:
        synchronizer = ProxmoxSynchronizer(server_id)
        result = synchronizer.sync_all()
        return result
    except Exception as e:
        return {
            'status': 'error',
            'message': f"Error al sincronizar datos: {str(e)}"
        }