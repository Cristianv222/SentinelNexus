from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from proxmoxer import ProxmoxAPI, AuthenticationError
import json
import logging
import time
import random
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_proxmox_connection():
    """
    Establece una conexión con el servidor Proxmox.
    """
    try:
        # Asegúrate de que el usuario tenga el formato correcto
        if '@' not in settings.PROXMOX['user']:
            # Si el usuario no tiene un realm, agregar @pam por defecto
            user = f"{settings.PROXMOX['user']}@pam"
        else:
            user = settings.PROXMOX['user']
        
        # Especificar el puerto correcto (generalmente 8006)
        host = settings.PROXMOX['host']
        if ':' not in host:
            host = f"{host}:8006"
            
        logger.info(f"Intentando conectar con Proxmox: {host} como {user}")
        
        proxmox = ProxmoxAPI(
            host,
            user=user,
            password=settings.PROXMOX['password'],
            verify_ssl=settings.PROXMOX['verify_ssl'],
            timeout=30  # Aumentar el timeout para evitar problemas de conexión
        )
        
        # Probar la conexión haciendo una solicitud simple
        proxmox.version.get()
        
        logger.info("Conexión exitosa con Proxmox")
        return proxmox
    
    except AuthenticationError as e:
        logger.error(f"Error de autenticación: {str(e)}")
        raise AuthenticationError(f"Error de autenticación: Usuario o contraseña incorrectos para {user}")
    except Exception as e:
        logger.error(f"Error al conectar con Proxmox: {str(e)}")
        raise Exception(f"Error al conectar con Proxmox en {host}: {str(e)}")

@login_required
def dashboard(request):
    """
    Dashboard principal que muestra una visión general de los nodos y VMs
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Obtener todos los nodos
        try:
            nodes = proxmox.nodes.get()
        except Exception as e:
            logger.error(f"Error al obtener los nodos: {str(e)}")
            messages.error(request, f"Error al obtener los nodos: {str(e)}")
            return render(request, 'dashboard.html', {
                'connection_error': True,
                'error_message': str(e),
                'nodes': [],
                'vms': [],
                'running_vms': 0
            })
        
        # Obtener todas las VMs
        vms = []
        for node in nodes:
            node_name = node['node']
            
            # Obtener información detallada del nodo
            try:
                node_status = proxmox.nodes(node_name).status.get()
                node['cpu'] = node_status.get('cpu', 0) * 100  # Convertir a porcentaje
                node['mem'] = node_status.get('memory', {}).get('used', 0) / node_status.get('memory', {}).get('total', 1) * 100
                node['disk_used'] = round(node_status.get('rootfs', {}).get('used', 0) / (1024 ** 3), 2)  # GB
                node['disk_total'] = round(node_status.get('rootfs', {}).get('total', 1) / (1024 ** 3), 2)  # GB
                
                # Simular tiempo de respuesta (en producción, esto sería un ping real)
                node['ping'] = 15  # ms
            except Exception as e:
                logger.warning(f"Error al obtener detalles del nodo {node_name}: {str(e)}")
                node['cpu'] = 0
                node['mem'] = 0
                node['disk_used'] = 0
                node['disk_total'] = 0
                node['ping'] = 'N/A'
                node['status'] = 'offline'
            
            # Obtener VMs (QEMU)
            try:
                qemu_vms = proxmox.nodes(node_name).qemu.get()
                for vm in qemu_vms:
                    vm['node'] = node_name
                    vm['type'] = 'qemu'
                    
                    # Obtener métricas adicionales si la VM está en ejecución
                    if vm.get('status') == 'running':
                        try:
                            vm_status = proxmox.nodes(node_name).qemu(vm['vmid']).status.current.get()
                            
                            vm['cpu'] = vm_status.get('cpu', 0) * 100
                            vm['mem'] = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
                            vm['mem_used'] = round(vm_status.get('mem', 0) / (1024 ** 2), 2)  # MB
                            vm['mem_total'] = round(vm_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
                            vm['disk_read'] = round(vm_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
                            vm['disk_write'] = round(vm_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
                            vm['net_in'] = round(vm_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
                            vm['net_out'] = round(vm_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
                            vm['ping'] = 10  # ms (simulado)
                            
                            # Cálculos de uso de disco
                            try:
                                # Intenta obtener datos de RRD para estadísticas
                                disk_info = proxmox.nodes(node_name).qemu(vm['vmid']).rrddata.get(timeframe='hour')
                                if disk_info and len(disk_info) > 0:
                                    last_data = disk_info[-1]
                                    vm['disk_used'] = round(last_data.get('disk', 0) / (1024 ** 3), 2)  # GB
                                else:
                                    vm['disk_used'] = 0
                            except Exception as disk_error:
                                logger.warning(f"Error al obtener datos de disco para VM {vm['vmid']}: {str(disk_error)}")
                                vm['disk_used'] = 0
                            
                            # Asignar un valor por defecto para el total del disco
                            vm['disk_total'] = 10  # GB (valor por defecto)
                            
                            # Intenta obtener el tamaño del disco desde la configuración
                            try:
                                vm_config = proxmox.nodes(node_name).qemu(vm['vmid']).config.get()
                                
                                for key, value in vm_config.items():
                                    if isinstance(value, str) and 'size=' in value:
                                        try:
                                            size_str = value.split('size=')[1].split(',')[0]
                                            if 'G' in size_str:
                                                vm['disk_total'] = float(size_str.replace('G', ''))
                                            elif 'M' in size_str:
                                                vm['disk_total'] = float(size_str.replace('M', '')) / 1024
                                            break
                                        except (ValueError, IndexError) as e:
                                            logger.warning(f"Error al parsear tamaño de disco: {str(e)}")
                            except Exception as config_error:
                                logger.warning(f"Error al obtener configuración para VM {vm['vmid']}: {str(config_error)}")
                            
                        except Exception as vm_error:
                            logger.warning(f"Error al obtener métricas de VM {vm['vmid']}: {str(vm_error)}")
                            vm['cpu'] = 0
                            vm['mem'] = 0
                            vm['mem_used'] = 0
                            vm['mem_total'] = 0
                            vm['disk_read'] = 0
                            vm['disk_write'] = 0
                            vm['net_in'] = 0
                            vm['net_out'] = 0
                            vm['ping'] = 'N/A'
                            vm['disk_used'] = 0
                            vm['disk_total'] = 0
                    else:
                        # Valores por defecto para VMs apagadas
                        vm['cpu'] = 0
                        vm['mem'] = 0
                        vm['mem_used'] = 0
                        vm['mem_total'] = 0
                        vm['disk_read'] = 0
                        vm['disk_write'] = 0
                        vm['net_in'] = 0
                        vm['net_out'] = 0
                        vm['ping'] = 'N/A'
                        vm['disk_used'] = 0
                        vm['disk_total'] = 0
                    
                    vms.append(vm)
            except Exception as e:
                logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
            
            # Obtener LXC containers
            try:
                lxc_containers = proxmox.nodes(node_name).lxc.get()
                for container in lxc_containers:
                    container['node'] = node_name
                    container['type'] = 'lxc'
                    
                    # Obtener métricas adicionales si el contenedor está en ejecución
                    if container.get('status') == 'running':
                        try:
                            container_status = proxmox.nodes(node_name).lxc(container['vmid']).status.current.get()
                            
                            container['cpu'] = container_status.get('cpu', 0) * 100
                            container['mem'] = container_status.get('mem', 0) / container_status.get('maxmem', 1) * 100
                            container['mem_used'] = round(container_status.get('mem', 0) / (1024 ** 2), 2)  # MB
                            container['mem_total'] = round(container_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
                            container['disk_read'] = round(container_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
                            container['disk_write'] = round(container_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
                            container['net_in'] = round(container_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
                            container['net_out'] = round(container_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
                            container['ping'] = 8  # ms (simulado)
                            
                            # Calcular uso de disco
                            container['disk_used'] = round(container_status.get('disk', 0) / (1024 ** 3), 2)  # GB
                            container['disk_total'] = round(container_status.get('maxdisk', 0) / (1024 ** 3), 2)  # GB
                            if container['disk_total'] <= 0:
                                container['disk_total'] = 10  # Valor por defecto si no hay información
                            
                        except Exception as e:
                            logger.warning(f"Error al obtener métricas de LXC {container['vmid']}: {str(e)}")
                            container['cpu'] = 0
                            container['mem'] = 0
                            container['mem_used'] = 0
                            container['mem_total'] = 0
                            container['disk_read'] = 0
                            container['disk_write'] = 0
                            container['net_in'] = 0
                            container['net_out'] = 0
                            container['ping'] = 'N/A'
                            container['disk_used'] = 0
                            container['disk_total'] = 0
                    else:
                        # Valores por defecto para contenedores apagados
                        container['cpu'] = 0
                        container['mem'] = 0
                        container['mem_used'] = 0
                        container['mem_total'] = 0
                        container['disk_read'] = 0
                        container['disk_write'] = 0
                        container['net_in'] = 0
                        container['net_out'] = 0
                        container['ping'] = 'N/A'
                        container['disk_used'] = 0
                        container['disk_total'] = 0
                    
                    vms.append(container)
            except Exception as e:
                logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
                
        # Obtener resumen del cluster
        cluster_status = None
        try:
            cluster_status = proxmox.cluster.status.get()
        except Exception as e:
            # Si no es un cluster, simplemente pasamos
            logger.info(f"No se pudo obtener información del cluster: {str(e)}")
        
        # Calcular VMs en ejecución
        running_vms = sum(1 for vm in vms if vm.get('status') == 'running')
            
        return render(request, 'dashboard.html', {
            'nodes': nodes,
            'vms': vms,
            'running_vms': running_vms,
            'cluster_status': cluster_status
        })
    
    except AuthenticationError as e:
        messages.error(request, str(e))
        messages.warning(request, "Verifica que las credenciales de Proxmox sean correctas en la configuración")
        return render(request, 'dashboard.html', {
            'connection_error': True,
            'error_message': str(e),
            'auth_error': True,
            'PROXMOX_HOST': settings.PROXMOX.get('host', ''),
            'PROXMOX_USER': settings.PROXMOX.get('user', '')
        })
    
    except Exception as e:
        messages.error(request, f"Error al conectar con Proxmox: {str(e)}")
        return render(request, 'dashboard.html', {
            'connection_error': True,
            'error_message': str(e),
            'PROXMOX_HOST': settings.PROXMOX.get('host', ''),
            'PROXMOX_USER': settings.PROXMOX.get('user', '')
        })

@login_required
def node_detail(request, node_name):
    """
    Muestra los detalles de un nodo específico.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Obtener información del nodo
        try:
            node_status = proxmox.nodes(node_name).status.get()
        except Exception as e:
            messages.error(request, f"Error al obtener detalles del nodo: {str(e)}")
            return redirect('dashboard')
        
        # Obtener VMs en este nodo
        qemu_vms = []
        try:
            qemu_vms = proxmox.nodes(node_name).qemu.get()
            for vm in qemu_vms:
                vm['type'] = 'qemu'
        except Exception as e:
            logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
        
        # Obtener contenedores LXC en este nodo
        lxc_containers = []
        try:
            lxc_containers = proxmox.nodes(node_name).lxc.get()
            for container in lxc_containers:
                container['type'] = 'lxc'
        except Exception as e:
            logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
        
        # Combinar VMs y contenedores
        vms = qemu_vms + lxc_containers
        
        # Obtener información del almacenamiento
        storage_info = []
        try:
            storage_info = proxmox.nodes(node_name).storage.get()
        except Exception as e:
            logger.warning(f"Error al obtener información de almacenamiento: {str(e)}")
        
        # Obtener información de la red
        network_info = []
        try:
            network_info = proxmox.nodes(node_name).network.get()
        except Exception as e:
            logger.warning(f"Error al obtener información de red: {str(e)}")
        
        return render(request, 'node_detail.html', {
            'node_name': node_name,
            'node_status': node_status,
            'vms': vms,
            'storage_info': storage_info,
            'network_info': network_info
        })
    except Exception as e:
        messages.error(request, f"Error al obtener detalles del nodo: {str(e)}")
        return redirect('dashboard')

@login_required
def vm_detail(request, node_name, vmid, vm_type=None):
    """
    Muestra los detalles de una máquina virtual o contenedor específico.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Si no se proporciona vm_type, detectarlo automáticamente
        if vm_type is None:
            detected = False
            try:
                # Intentar como QEMU VM
                proxmox.nodes(node_name).qemu(vmid).status.current.get()
                vm_type = 'qemu'
                detected = True
            except Exception as qemu_err:
                logger.debug(f"La VM {vmid} no es tipo QEMU: {str(qemu_err)}")
                try:
                    # Intentar como LXC container
                    proxmox.nodes(node_name).lxc(vmid).status.current.get()
                    vm_type = 'lxc'
                    detected = True
                except Exception as lxc_err:
                    logger.error(f"No se pudo detectar el tipo de VM para {vmid}: {str(lxc_err)}")
            
            if not detected:
                messages.error(request, f"No se pudo detectar el tipo de VM para ID {vmid}")
                return redirect('dashboard')
        
        # Obtener estado actual
        vm_status = {}
        vm_config = {}
        try:
            if vm_type == 'qemu':
                vm_status = proxmox.nodes(node_name).qemu(vmid).status.current.get()
                vm_config = proxmox.nodes(node_name).qemu(vmid).config.get()
            else:  # 'lxc'
                vm_status = proxmox.nodes(node_name).lxc(vmid).status.current.get()
                vm_config = proxmox.nodes(node_name).lxc(vmid).config.get()
        except Exception as e:
            messages.error(request, f"Error al obtener detalles de la VM: {str(e)}")
            return redirect('dashboard')
        
        # Obtener historial de tareas
        tasks = []
        try:
            tasks = proxmox.nodes(node_name).tasks.get(
                vmid=vmid,
                limit=10,
                start=0
            )
        except Exception as e:
            logger.warning(f"Error al obtener historial de tareas: {str(e)}")
        
        return render(request, 'vm_detail.html', {
            'node_name': node_name,
            'vmid': vmid,
            'vm_type': vm_type,
            'vm_status': vm_status,
            'vm_config': vm_config,
            'tasks': tasks
        })
    except Exception as e:
        messages.error(request, f"Error al obtener detalles de la VM: {str(e)}")
        return redirect('dashboard')

@login_required
def vm_action(request, node_name, vmid, action, vm_type=None):
    """
    Realiza una acción en una máquina virtual o contenedor.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Si no se proporciona vm_type, detectarlo automáticamente
        if vm_type is None:
            detected = False
            try:
                # Intentar como QEMU VM
                proxmox.nodes(node_name).qemu(vmid).status.current.get()
                vm_type = 'qemu'
                detected = True
            except:
                try:
                    # Intentar como LXC container
                    proxmox.nodes(node_name).lxc(vmid).status.current.get()
                    vm_type = 'lxc'
                    detected = True
                except:
                    pass
            
            if not detected:
                messages.error(request, f"No se pudo detectar el tipo de VM para ID {vmid}")
                return redirect('dashboard')
        
        result = None
        # Ejecutar la acción correspondiente
        try:
            if vm_type == 'qemu':
                if action == 'start':
                    result = proxmox.nodes(node_name).qemu(vmid).status.start.post()
                elif action == 'stop':
                    result = proxmox.nodes(node_name).qemu(vmid).status.stop.post()
                elif action == 'shutdown':
                    result = proxmox.nodes(node_name).qemu(vmid).status.shutdown.post()
                elif action == 'reset':
                    result = proxmox.nodes(node_name).qemu(vmid).status.reset.post()
                elif action == 'suspend':
                    result = proxmox.nodes(node_name).qemu(vmid).status.suspend.post()
                elif action == 'resume':
                    result = proxmox.nodes(node_name).qemu(vmid).status.resume.post()
            else:  # 'lxc'
                if action == 'start':
                    result = proxmox.nodes(node_name).lxc(vmid).status.start.post()
                elif action == 'stop':
                    result = proxmox.nodes(node_name).lxc(vmid).status.stop.post()
                elif action == 'shutdown':
                    result = proxmox.nodes(node_name).lxc(vmid).status.shutdown.post()
        except Exception as action_error:
            messages.error(request, f"Error al ejecutar la acción '{action}': {str(action_error)}")
            
            # Si es una petición AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': f"Error al ejecutar '{action}': {str(action_error)}"
                })
            
            if vm_type:
                return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
            else:
                return redirect('dashboard')
        
        # Verificar el resultado
        if result is None:
            messages.error(request, f"Acción '{action}' no soportada para {vm_type}")
        else:
            messages.success(request, f"Acción '{action}' iniciada correctamente. UPID: {result}")
        
        # Si es una petición AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': result is not None,
                'message': f"Acción '{action}' iniciada correctamente" if result else f"Acción '{action}' no soportada",
                'upid': result
            })
        
        # Redirigir a la página de detalles
        if vm_type:
            return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
        else:
            return redirect('vm_detail', node_name=node_name, vmid=vmid)
    
    except Exception as e:
        error_message = f"Error al ejecutar '{action}': {str(e)}"
        messages.error(request, error_message)
        
        # Si es una petición AJAX, devolver JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': error_message
            })
        
        # Redirigir a la página de detalles o al dashboard
        if vm_type:
            return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
        else:
            return redirect('dashboard')

# API endpoints
@login_required
def api_get_nodes(request):
    """
    API endpoint para obtener información de todos los nodos.
    """
    try:
        proxmox = get_proxmox_connection()
        
        nodes = proxmox.nodes.get()
        
        # Añadir información adicional a cada nodo
        for node in nodes:
            node_name = node['node']
            try:
                status = proxmox.nodes(node_name).status.get()
                node['cpu'] = status.get('cpu', 0) * 100  # Convertir a porcentaje
                node['memory'] = {
                    'total': status.get('memory', {}).get('total', 0),
                    'used': status.get('memory', {}).get('used', 0),
                    'free': status.get('memory', {}).get('free', 0)
                }
                node['uptime'] = status.get('uptime', 0)
            except Exception as e:
                logger.warning(f"Error al obtener estado del nodo {node_name}: {str(e)}")
                # Asigna valores por defecto si hay error
                node['cpu'] = 0
                node['memory'] = {'total': 0, 'used': 0, 'free': 0}
                node['uptime'] = 0
                
        return JsonResponse({
            'success': True,
            'data': nodes
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def api_get_vms(request):
    """
    API endpoint para obtener información de todas las VMs.
    """
    try:
        proxmox = get_proxmox_connection()
        node_filter = request.GET.get('node')
        
        nodes = proxmox.nodes.get()
        vms = []
        
        for node in nodes:
            node_name = node['node']
            
            # Si hay un filtro de nodo y este nodo no coincide, saltar
            if node_filter and node_name != node_filter:
                continue
                
            # Obtener VMs (QEMU)
            try:
                qemu_vms = proxmox.nodes(node_name).qemu.get()
                for vm in qemu_vms:
                    vm['node'] = node_name
                    vm['type'] = 'qemu'
                    vms.append(vm)
            except Exception as e:
                logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
            
            # Obtener contenedores LXC
            try:
                lxc_containers = proxmox.nodes(node_name).lxc.get()
                for container in lxc_containers:
                    container['node'] = node_name
                    container['type'] = 'lxc'
                    vms.append(container)
            except Exception as e:
                logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
                
        return JsonResponse({
            'success': True,
            'data': vms
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def api_vm_status(request, node_name, vmid):
    """
    API endpoint para obtener el estado de una VM.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Intentar determinar el tipo de VM
        vm_type = None
        vm_status = None
        
        try:
            vm_status = proxmox.nodes(node_name).qemu(vmid).status.current.get()
            vm_type = 'qemu'
        except Exception:
            try:
                vm_status = proxmox.nodes(node_name).lxc(vmid).status.current.get()
                vm_type = 'lxc'
            except Exception:
                return JsonResponse({
                    'success': False,
                    'message': f"No se encontró VM con ID {vmid} en el nodo {node_name}"
                })
        
        if not vm_status:
            return JsonResponse({
                'success': False,
                'message': f"No se pudo obtener el estado de la VM {vmid}"
            })
            
        # Añadir información de tipo
        vm_status['type'] = vm_type
            
        return JsonResponse({
            'success': True,
            'data': vm_status
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    
@login_required
def server_list(request):
    """
    Muestra una lista de los servidores Proxmox configurados.
    """
    try:
        # Puedes obtener los servidores desde la base de datos o desde la configuración
        proxmox = get_proxmox_connection()
        nodes = proxmox.nodes.get()
        
        return render(request, 'server_list.html', {
            'nodes': nodes
        })
    except Exception as e:
        messages.error(request, f"Error al conectar con Proxmox: {str(e)}")
        return render(request, 'server_list.html', {
            'connection_error': True,
            'error_message': str(e)
        })

@login_required
def api_vm_metrics(request, node_name, vmid):
    """
    API endpoint para obtener métricas en tiempo real de una VM o contenedor.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Intentar determinar el tipo de VM
        vm_type = None
        try:
            proxmox.nodes(node_name).qemu(vmid).status.current.get()
            vm_type = 'qemu'
        except:
            try:
                proxmox.nodes(node_name).lxc(vmid).status.current.get()
                vm_type = 'lxc'
            except:
                return JsonResponse({
                    'success': False,
                    'message': f"No se encontró VM con ID {vmid} en el nodo {node_name}"
                })
        
        # Obtener métricas actuales
        if vm_type == 'qemu':
            vm_status = proxmox.nodes(node_name).qemu(vmid).status.current.get()
            
            # Calcular métricas
            cpu = vm_status.get('cpu', 0) * 100  # Convertir a porcentaje
            mem = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
            mem_used = round(vm_status.get('mem', 0) / (1024 ** 2), 2)  # MB
            mem_total = round(vm_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
            disk_read = round(vm_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
            disk_write = round(vm_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
            net_in = round(vm_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
            net_out = round(vm_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
            
            # Obtener datos del disco
            try:
                disk_info = proxmox.nodes(node_name).qemu(vmid).rrddata.get(timeframe='hour')
                if disk_info:
                    last_data = disk_info[-1]
                    disk_used = round(last_data.get('disk', 0) / (1024 ** 3), 2)  # GB
                else:
                    disk_used = 0
            except:
                disk_used = 0
                
            # Obtener historial de CPU y memoria para gráficas
            try:
                rrd_data = proxmox.nodes(node_name).qemu(vmid).rrddata.get(
                    timeframe='hour',
                    cf='AVERAGE'
                )
                
                cpu_history = []
                mem_history = []
                disk_history = []
                net_history = []
                timestamps = []
                
                for point in rrd_data:
                    time_val = point.get('time', 0)
                    timestamps.append(time_val)
                    cpu_history.append(point.get('cpu', 0) * 100)
                    mem_val = 0
                    if 'mem' in point and 'maxmem' in point and point['maxmem'] > 0:
                        mem_val = (point['mem'] / point['maxmem']) * 100
                    mem_history.append(mem_val)
                    disk_history.append(point.get('disk', 0) / (1024 ** 3))
                    
                    net_val = 0
                    if 'netin' in point and 'netout' in point:
                        net_val = (point['netin'] + point['netout']) / (1024 ** 2)
                    net_history.append(net_val)
            except Exception as e:
                logger.warning(f"Error al obtener datos RRD: {str(e)}")
                cpu_history = []
                mem_history = []
                disk_history = []
                net_history = []
                timestamps = []
                
        else:  # 'lxc'
            vm_status = proxmox.nodes(node_name).lxc(vmid).status.current.get()
            
            # Calcular métricas
            cpu = vm_status.get('cpu', 0) * 100  # Convertir a porcentaje
            mem = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
            mem_used = round(vm_status.get('mem', 0) / (1024 ** 2), 2)  # MB
            mem_total = round(vm_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
            disk_read = round(vm_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
            disk_write = round(vm_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
            net_in = round(vm_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
            net_out = round(vm_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
            disk_used = round(vm_status.get('disk', 0) / (1024 ** 3), 2)  # GB
            
            # Obtener historial para gráficas
            try:
                rrd_data = proxmox.nodes(node_name).lxc(vmid).rrddata.get(
                    timeframe='hour',
                    cf='AVERAGE'
                )
                
                cpu_history = []
                mem_history = []
                disk_history = []
                net_history = []
                timestamps = []
                
                for point in rrd_data:
                    time_val = point.get('time', 0)
                    timestamps.append(time_val)
                    cpu_history.append(point.get('cpu', 0) * 100)
                    mem_val = 0
                    if 'mem' in point and 'maxmem' in point and point['maxmem'] > 0:
                        mem_val = (point['mem'] / point['maxmem']) * 100
                    mem_history.append(mem_val)
                    disk_history.append(point.get('disk', 0) / (1024 ** 3))
                    
                    net_val = 0
                    if 'netin' in point and 'netout' in point:
                        net_val = (point['netin'] + point['netout']) / (1024 ** 2)
                    net_history.append(net_val)
            except Exception as e:
                logger.warning(f"Error al obtener datos RRD: {str(e)}")
                cpu_history = []
                mem_history = []
                disk_history = []
                net_history = []
                timestamps = []
        
        return JsonResponse({
            'success': True,
            'data': {
                'type': vm_type,
                'status': vm_status.get('status', 'unknown'),
                'cpu': round(cpu, 1),
                'mem': round(mem, 1),
                'mem_used': mem_used,
                'mem_total': mem_total,
                'disk_read': disk_read,
                'disk_write': disk_write,
                'net_in': net_in,
                'net_out': net_out,
                'disk_used': disk_used,
                'timestamp': vm_status.get('time', 0),
                'history': {
                    'timestamps': timestamps,
                    'cpu': cpu_history,
                    'mem': mem_history,
                    'disk': disk_history,
                    'net': net_history
                }
            }
        })
    except Exception as e:
        logger.error(f"Error al obtener métricas de VM {vmid}: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@login_required
def api_dashboard_metrics(request):
    """
    API endpoint para obtener métricas en tiempo real de todas las VMs y nodos.
    """
    try:
        proxmox = get_proxmox_connection()
        nodes_data = []
        vms_data = []
        
        # Obtener todos los nodos
        nodes = proxmox.nodes.get()
        
        for node in nodes:
            node_name = node['node']
            
            # Obtener métricas del nodo
            try:
                node_status = proxmox.nodes(node_name).status.get()
                node_metrics = {
                    'node': node_name,
                    'status': node['status'],
                    'cpu': node_status.get('cpu', 0) * 100,  # Convertir a porcentaje
                    'mem': node_status.get('memory', {}).get('used', 0) / node_status.get('memory', {}).get('total', 1) * 100,
                    'disk_used': round(node_status.get('rootfs', {}).get('used', 0) / (1024 ** 3), 2),  # GB
                    'disk_total': round(node_status.get('rootfs', {}).get('total', 1) / (1024 ** 3), 2),  # GB
                    'uptime': node_status.get('uptime', 0),
                    'ping': 15  # ms (simulado)
                }
                nodes_data.append(node_metrics)
            except Exception as e:
                logger.warning(f"Error al obtener métricas del nodo {node_name}: {str(e)}")
            
            # Obtener VMs (QEMU)
            try:
                qemu_vms = proxmox.nodes(node_name).qemu.get()
                for vm in qemu_vms:
                    vm_data = {
                        'vmid': vm['vmid'],
                        'name': vm.get('name', f"VM {vm['vmid']}"),
                        'node': node_name,
                        'type': 'qemu',
                        'status': vm.get('status', 'unknown'),
                        'cpu': 0,
                        'mem': 0,
                        'mem_used': 0,
                        'mem_total': 0,
                        'disk_read': 0,
                        'disk_write': 0,
                        'net_in': 0,
                        'net_out': 0,
                        'disk_used': 0,
                        'disk_total': 0
                    }
                    
                    # Obtener métricas adicionales si la VM está en ejecución
                    if vm.get('status') == 'running':
                        try:
                            vm_status = proxmox.nodes(node_name).qemu(vm['vmid']).status.current.get()
                            
                            vm_data['cpu'] = vm_status.get('cpu', 0) * 100
                            vm_data['mem'] = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
                            vm_data['mem_used'] = round(vm_status.get('mem', 0) / (1024 ** 2), 2)  # MB
                            vm_data['mem_total'] = round(vm_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
                            vm_data['disk_read'] = round(vm_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
                            vm_data['disk_write'] = round(vm_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
                            vm_data['net_in'] = round(vm_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
                            vm_data['net_out'] = round(vm_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
                            vm_data['ping'] = 10  # ms (simulado)
                            
                            # Calcular uso de disco (simplificado para respuesta rápida)
                            vm_data['disk_used'] = 0
                            vm_data['disk_total'] = 0
                        except Exception as e:
                            logger.warning(f"Error al obtener métricas de VM {vm['vmid']}: {str(e)}")
                    
                    vms_data.append(vm_data)
            except Exception as e:
                logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
            
            # Obtener LXC containers
            try:
                lxc_containers = proxmox.nodes(node_name).lxc.get()
                for container in lxc_containers:
                    container_data = {
                        'vmid': container['vmid'],
                        'name': container.get('name', f"CT {container['vmid']}"),
                        'node': node_name,
                        'type': 'lxc',
                        'status': container.get('status', 'unknown'),
                        'cpu': 0,
                        'mem': 0,
                        'mem_used': 0,
                        'mem_total': 0,
                        'disk_read': 0,
                        'disk_write': 0,
                        'net_in': 0,
                        'net_out': 0,
                        'disk_used': 0,
                        'disk_total': 0
                    }
                    
                    # Obtener métricas adicionales si el contenedor está en ejecución
                    if container.get('status') == 'running':
                        try:
                            container_status = proxmox.nodes(node_name).lxc(container['vmid']).status.current.get()
                            
                            container_data['cpu'] = container_status.get('cpu', 0) * 100
                            container_data['mem'] = container_status.get('mem', 0) / container_status.get('maxmem', 1) * 100
                            container_data['mem_used'] = round(container_status.get('mem', 0) / (1024 ** 2), 2)  # MB
                            container_data['mem_total'] = round(container_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
                            container_data['disk_read'] = round(container_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
                            container_data['disk_write'] = round(container_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
                            container_data['net_in'] = round(container_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
                            container_data['net_out'] = round(container_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
                            container_data['ping'] = 8  # ms (simulado)
                            
                            # Calcular uso de disco
                            container_data['disk_used'] = round(container_status.get('disk', 0) / (1024 ** 3), 2)  # GB
                            container_data['disk_total'] = round(container_status.get('maxdisk', 0) / (1024 ** 3), 2)  # GB
                        except Exception as e:
                            logger.warning(f"Error al obtener métricas de LXC {container['vmid']}: {str(e)}")
                    
                    vms_data.append(container_data)
            except Exception as e:
                logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
        
        # Calcular VMs en ejecución
        running_vms = sum(1 for vm in vms_data if vm.get('status') == 'running')
        
        return JsonResponse({
            'success': True,
            'timestamp': int(time.time()),
            'data': {
                'nodes': nodes_data,
                'vms': vms_data,
                'summary': {
                    'total_vms': len(vms_data),
                    'running_vms': running_vms,
                    'total_nodes': len(nodes_data),
                    'online_nodes': sum(1 for node in nodes_data if node.get('status') == 'online')
                }
            }
        })
    except Exception as e:
        logger.error(f"Error al obtener métricas del dashboard: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

# Nuevas vistas para las métricas
@login_required
def metrics_dashboard(request):
    """
    Dashboard de métricas personalizado utilizando Chart.js
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Obtener todos los nodos para el selector
        nodes = []
        try:
            nodes = proxmox.nodes.get()
        except Exception as e:
            logger.warning(f"Error al obtener los nodos para el dashboard de métricas: {str(e)}")
        
        return render(request, 'metrics_dashboard.html', {
            'nodes': nodes,
        })
    except Exception as e:
        messages.error(request, f"Error al cargar el dashboard de métricas: {str(e)}")
        return redirect('dashboard')

@login_required
def grafana_dashboard(request):
    """
    Vista que integra un dashboard de Grafana vía iframe
    """
    # Aquí podrías pasar cualquier parámetro adicional que necesites
    dashboard_url = settings.GRAFANA_URL if hasattr(settings, 'GRAFANA_URL') else "http://localhost:3000"
    dashboard_id = settings.GRAFANA_DASHBOARD_ID if hasattr(settings, 'GRAFANA_DASHBOARD_ID') else "proxmox-monitoring"
    
    return render(request, 'grafana.html', {
        'dashboard_url': dashboard_url,
        'dashboard_id': dashboard_id
    })

@login_required
def api_metrics(request):
    """
    API endpoint para obtener métricas históricas
    """
    timeframe = request.GET.get('timeframe', 'hour')
    node_filter = request.GET.get('node', None)
    vm_filter = request.GET.get('vmid', None)
    
    try:
        proxmox = get_proxmox_connection()
        
        # Obtener timestamps según el timeframe
        end_time = datetime.now()
        
        if timeframe == 'hour':
            start_time = end_time - timedelta(hours=1)
            interval = timedelta(minutes=5)
            rrd_timeframe = 'hour'
        elif timeframe == 'day':
            start_time = end_time - timedelta(days=1)
            interval = timedelta(hours=1)
            rrd_timeframe = 'day'
        elif timeframe == 'week':
            start_time = end_time - timedelta(days=7)
            interval = timedelta(hours=6)
            rrd_timeframe = 'week'
        else:  # month
            start_time = end_time - timedelta(days=30)
            interval = timedelta(days=1)
            rrd_timeframe = 'month'
        
        # Estructura para almacenar datos
        metrics_data = {
            'timestamps': [],
            'cpu_history': {'nodes': {}, 'vms': {}},
            'memory_history': {'nodes': {}, 'vms': {}},
            'disk_history': {'read': {}, 'write': {}},
            'network_history': {'in': {}, 'out': {}},
            'top_vms': [],
            'averages': {
                'cpu': 0,
                'memory': 0,
                'active_vms': 0,
                'active_nodes': 0
            }
        }
        
        # Recolectar datos de nodos
        nodes = proxmox.nodes.get()
        active_nodes = 0
        total_cpu = 0
        total_mem = 0
        
        for node in nodes:
            node_name = node['node']
            
            # Filtrar por nodo si se especifica
            if node_filter and node_name != node_filter:
                continue
            
            # Obtener estadísticas del nodo
            try:
                # Verificar si el nodo está en línea
                if node.get('status') == 'online':
                    active_nodes += 1
                    
                    # Obtener estadísticas RRD para gráficos
                    rrd_data = proxmox.nodes(node_name).rrddata.get(
                        timeframe=rrd_timeframe,
                        cf='AVERAGE'
                    )
                    
                    # Procesar datos RRD
                    cpu_data = []
                    mem_data = []
                    timestamps = []
                    
                    for point in rrd_data:
                        time_val = point.get('time', 0)
                        timestamps.append(datetime.fromtimestamp(time_val).strftime('%Y-%m-%d %H:%M:%S'))
                        
                        # Datos de CPU
                        cpu_val = point.get('cpu', 0) * 100  # Convertir a porcentaje
                        cpu_data.append(cpu_val)
                        
                        # Datos de Memoria
                        mem_val = 0
                        if 'memused' in point and 'memtotal' in point and point['memtotal'] > 0:
                            mem_val = (point['memused'] / point['memtotal']) * 100
                        mem_data.append(mem_val)
                    
                    # Almacenar datos del nodo
                    metrics_data['cpu_history']['nodes'][node_name] = cpu_data
                    metrics_data['memory_history']['nodes'][node_name] = mem_data
                    
                    # Si este es el primer nodo, guardar los timestamps
                    if not metrics_data['timestamps'] and timestamps:
                        metrics_data['timestamps'] = timestamps
                    
                    # Obtener estadísticas actuales
                    node_status = proxmox.nodes(node_name).status.get()
                    cpu_usage = node_status.get('cpu', 0) * 100
                    mem_usage = node_status.get('memory', {}).get('used', 0) / node_status.get('memory', {}).get('total', 1) * 100
                    
                    total_cpu += cpu_usage
                    total_mem += mem_usage
            except Exception as e:
                logger.warning(f"Error al obtener estadísticas del nodo {node_name}: {str(e)}")
        
        # Recolectar datos de VMs
        vms = []
        active_vms = 0
        
        # Obtener todas las VMs de todos los nodos
        for node in nodes:
            node_name = node['node']
            
            # Filtrar por nodo si se especifica
            if node_filter and node_name != node_filter:
                continue
            
            # Obtener VMs (QEMU)
            try:
                qemu_vms = proxmox.nodes(node_name).qemu.get()
                for vm in qemu_vms:
                    vm['node'] = node_name
                    vm['type'] = 'qemu'
                    vms.append(vm)
                    
                    # Filtrar por VM si se especifica
                    if vm_filter and str(vm['vmid']) != vm_filter:
                        continue
                    
                    # Obtener métricas para VMs en ejecución
                    if vm.get('status') == 'running':
                        active_vms += 1
                        
                        try:
                            # Obtener estado actual
                            vm_status = proxmox.nodes(node_name).qemu(vm['vmid']).status.current.get()
                            
                            # Obtener datos RRD para gráficos
                            vm_rrd_data = proxmox.nodes(node_name).qemu(vm['vmid']).rrddata.get(
                                timeframe=rrd_timeframe,
                                cf='AVERAGE'
                            )
                            
                            # Procesar datos RRD
                            vm_cpu_data = []
                            vm_mem_data = []
                            vm_disk_read = []
                            vm_disk_write = []
                            vm_net_in = []
                            vm_net_out = []
                            
                            for point in vm_rrd_data:
                                # Datos de CPU
                                cpu_val = point.get('cpu', 0) * 100  # Convertir a porcentaje
                                vm_cpu_data.append(cpu_val)
                                
                                # Datos de Memoria
                                mem_val = 0
                                if 'mem' in point and 'maxmem' in point and point['maxmem'] > 0:
                                    mem_val = (point['mem'] / point['maxmem']) * 100
                                vm_mem_data.append(mem_val)
                                
                                # Datos de Disco
                                vm_disk_read.append(point.get('diskread', 0) / (1024 ** 2))  # MB/s
                                vm_disk_write.append(point.get('diskwrite', 0) / (1024 ** 2))  # MB/s
                                
                                # Datos de Red
                                vm_net_in.append(point.get('netin', 0) / (1024 ** 2))  # Mbps
                                vm_net_out.append(point.get('netout', 0) / (1024 ** 2))  # Mbps
                            
                            # Almacenar datos de la VM
                            vm_name = vm.get('name', f"VM {vm['vmid']}")
                            metrics_data['cpu_history']['vms'][vm_name] = vm_cpu_data
                            metrics_data['memory_history']['vms'][vm_name] = vm_mem_data
                            metrics_data['disk_history']['read'][vm_name] = vm_disk_read
                            metrics_data['disk_history']['write'][vm_name] = vm_disk_write
                            metrics_data['network_history']['in'][vm_name] = vm_net_in
                            metrics_data['network_history']['out'][vm_name] = vm_net_out
                            
                            # Calcular uso actual para top VMs
                            current_cpu = vm_status.get('cpu', 0) * 100
                            current_mem = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
                            
                            # Añadir a la lista de top VMs
                            metrics_data['top_vms'].append({
                                'id': vm['vmid'],
                                'name': vm_name,
                                'node': node_name,
                                'cpu': round(current_cpu, 1),
                                'memory': round(current_mem, 1),
                                'disk_io': round(vm_status.get('diskread', 0) / (1024 ** 2) + vm_status.get('diskwrite', 0) / (1024 ** 2), 1),
                                'network': round(vm_status.get('netin', 0) / (1024 ** 2) + vm_status.get('netout', 0) / (1024 ** 2), 1)
                            })
                        except Exception as e:
                            logger.warning(f"Error al obtener datos RRD para VM {vm['vmid']}: {str(e)}")
            except Exception as e:
                logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
            
            # Obtener contenedores LXC
            try:
                lxc_containers = proxmox.nodes(node_name).lxc.get()
                for container in lxc_containers:
                    container['node'] = node_name
                    container['type'] = 'lxc'
                    vms.append(container)
                    
                    # Filtrar por VM si se especifica
                    if vm_filter and str(container['vmid']) != vm_filter:
                        continue
                    
                    # Obtener métricas para contenedores en ejecución
                    if container.get('status') == 'running':
                        active_vms += 1
                        
                        try:
                            # Obtener estado actual
                            container_status = proxmox.nodes(node_name).lxc(container['vmid']).status.current.get()
                            
                            # Obtener datos RRD para gráficos
                            container_rrd_data = proxmox.nodes(node_name).lxc(container['vmid']).rrddata.get(
                                timeframe=rrd_timeframe,
                                cf='AVERAGE'
                            )
                            
                            # Procesar datos RRD (similar a las VMs)
                            container_cpu_data = []
                            container_mem_data = []
                            container_disk_read = []
                            container_disk_write = []
                            container_net_in = []
                            container_net_out = []
                            
                            for point in container_rrd_data:
                                # Datos de CPU
                                cpu_val = point.get('cpu', 0) * 100
                                container_cpu_data.append(cpu_val)
                                
                                # Datos de Memoria
                                mem_val = 0
                                if 'mem' in point and 'maxmem' in point and point['maxmem'] > 0:
                                    mem_val = (point['mem'] / point['maxmem']) * 100
                                container_mem_data.append(mem_val)
                                
                                # Datos de Disco
                                container_disk_read.append(point.get('diskread', 0) / (1024 ** 2))
                                container_disk_write.append(point.get('diskwrite', 0) / (1024 ** 2))
                                
                                # Datos de Red
                                container_net_in.append(point.get('netin', 0) / (1024 ** 2))
                                container_net_out.append(point.get('netout', 0) / (1024 ** 2))
                            
                            # Almacenar datos del contenedor
                            container_name = container.get('name', f"CT {container['vmid']}")
                            metrics_data['cpu_history']['vms'][container_name] = container_cpu_data
                            metrics_data['memory_history']['vms'][container_name] = container_mem_data
                            metrics_data['disk_history']['read'][container_name] = container_disk_read
                            metrics_data['disk_history']['write'][container_name] = container_disk_write
                            metrics_data['network_history']['in'][container_name] = container_net_in
                            metrics_data['network_history']['out'][container_name] = container_net_out
                            
                            # Calcular uso actual para top VMs
                            current_cpu = container_status.get('cpu', 0) * 100
                            current_mem = container_status.get('mem', 0) / container_status.get('maxmem', 1) * 100
# Añadir a la lista de top VMs
                            metrics_data['top_vms'].append({
                                'id': container['vmid'],
                                'name': container_name,
                                'node': node_name,
                                'cpu': round(current_cpu, 1),
                                'memory': round(current_mem, 1),
                                'disk_io': round(container_status.get('diskread', 0) / (1024 ** 2) + container_status.get('diskwrite', 0) / (1024 ** 2), 1),
                                'network': round(container_status.get('netin', 0) / (1024 ** 2) + container_status.get('netout', 0) / (1024 ** 2), 1)
                            })
                        except Exception as e:
                            logger.warning(f"Error al obtener datos RRD para contenedor {container['vmid']}: {str(e)}")
            except Exception as e:
                logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
        
        # Calcular promedios
        if active_nodes > 0:
            metrics_data['averages']['cpu'] = round(total_cpu / active_nodes, 1)
            metrics_data['averages']['memory'] = round(total_mem / active_nodes, 1)
        
        metrics_data['averages']['active_vms'] = active_vms
        metrics_data['averages']['active_nodes'] = active_nodes
        
        # Ordenar top VMs por uso de CPU
        metrics_data['top_vms'] = sorted(metrics_data['top_vms'], key=lambda x: x['cpu'], reverse=True)[:10]
        
        return JsonResponse({
            'success': True,
            'data': metrics_data
        })
    except Exception as e:
        logger.error(f"Error al obtener métricas históricas: {str(e)}")
        
        # Si hay un error, devolver datos simulados para pruebas
        # Esto se puede eliminar en producción
        return JsonResponse({
            'success': False,
            'message': str(e),
            'fallback_data': True,
            'data': generate_fallback_metrics_data(timeframe)
        })

def generate_fallback_metrics_data(timeframe):
    """
    Genera datos simulados para pruebas cuando hay errores con Proxmox
    """
    # Generar timestamps
    end_time = datetime.now()
    
    if timeframe == 'hour':
        start_time = end_time - timedelta(hours=1)
        interval = timedelta(minutes=5)
    elif timeframe == 'day':
        start_time = end_time - timedelta(days=1)
        interval = timedelta(hours=1)
    elif timeframe == 'week':
        start_time = end_time - timedelta(days=7)
        interval = timedelta(hours=6)
    else:  # month
        start_time = end_time - timedelta(days=30)
        interval = timedelta(days=1)
    
    timestamps = []
    current = start_time
    while current <= end_time:
        timestamps.append(current.strftime('%Y-%m-%d %H:%M:%S'))
        current += interval
    
    # Generar datos simulados
    nodes = ['node1', 'node2']
    vms = ['vm1', 'vm2', 'vm3', 'vm4']
    
    cpu_history = {
        'nodes': {node: [random.uniform(10, 80) for _ in timestamps] for node in nodes},
        'vms': {vm: [random.uniform(5, 95) for _ in timestamps] for vm in vms}
    }
    
    memory_history = {
        'nodes': {node: [random.uniform(20, 70) for _ in timestamps] for node in nodes},
        'vms': {vm: [random.uniform(10, 90) for _ in timestamps] for vm in vms}
    }
    
    disk_history = {
        'read': {vm: [random.uniform(0, 50) for _ in timestamps] for vm in vms},
        'write': {vm: [random.uniform(0, 40) for _ in timestamps] for vm in vms}
    }
    
    network_history = {
        'in': {vm: [random.uniform(0, 100) for _ in timestamps] for vm in vms},
        'out': {vm: [random.uniform(0, 80) for _ in timestamps] for vm in vms}
    }
    
    # Generar datos para top VMs
    top_vms = []
    for vm in vms:
        top_vms.append({
            'id': random.randint(100, 999),
            'name': vm,
            'node': random.choice(nodes),
            'cpu': random.uniform(10, 95),
            'memory': random.uniform(10, 95),
            'disk_io': random.uniform(0, 100),
            'network': random.uniform(0, 200)
        })
    
    # Calcular promedios
    avg_cpu = sum(sum(cpu_history['nodes'][node]) for node in nodes) / (len(nodes) * len(timestamps))
    avg_mem = sum(sum(memory_history['nodes'][node]) for node in nodes) / (len(nodes) * len(timestamps))
    
    return {
        'timestamps': timestamps,
        'cpu_history': cpu_history,
        'memory_history': memory_history,
        'disk_history': disk_history,
        'network_history': network_history,
        'averages': {
            'cpu': round(avg_cpu, 1),
            'memory': round(avg_mem, 1),
            'active_vms': len(vms),
            'active_nodes': len(nodes)
        },
        'top_vms': top_vms
    }