from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from proxmoxer import ProxmoxAPI, AuthenticationError
import json
import logging
import time

logger = logging.getLogger(__name__)

def get_proxmox_connection():
    """
    Establece una conexión con el servidor Proxmox.
    """
    try:
        # Verificar si el usuario tiene el formato correcto
        if '@' not in settings.PROXMOX['user']:
            # Si el usuario no tiene un realm, agregar @pam por defecto
            user = f"{settings.PROXMOX['user']}@pam"
        else:
            user = settings.PROXMOX['user']
        
        logger.info(f"Intentando conectar con Proxmox: {settings.PROXMOX['host']} como {user}")
        
        proxmox = ProxmoxAPI(
            settings.PROXMOX['host'],
            user=user,
            password=settings.PROXMOX['password'],
            verify_ssl=settings.PROXMOX['verify_ssl']
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
        raise Exception(f"Error al conectar con Proxmox en {settings.PROXMOX['host']}: {str(e)}")

@login_required
def dashboard(request):
    """
    Dashboard principal que muestra una visión general de los nodos y VMs
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Obtener todos los nodos
        nodes = proxmox.nodes.get()
        
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
                            vm_config = proxmox.nodes(node_name).qemu(vm['vmid']).config.get()
                            
                            vm['cpu'] = vm_status.get('cpu', 0) * 100
                            vm['mem'] = vm_status.get('mem', 0) / vm_status.get('maxmem', 1) * 100
                            vm['mem_used'] = round(vm_status.get('mem', 0) / (1024 ** 2), 2)  # MB
                            vm['mem_total'] = round(vm_status.get('maxmem', 0) / (1024 ** 2), 2)  # MB
                            vm['disk_read'] = round(vm_status.get('diskread', 0) / (1024 ** 2), 2)  # MB/s
                            vm['disk_write'] = round(vm_status.get('diskwrite', 0) / (1024 ** 2), 2)  # MB/s
                            vm['net_in'] = round(vm_status.get('netin', 0) / (1024 ** 2), 2)  # Mbps
                            vm['net_out'] = round(vm_status.get('netout', 0) / (1024 ** 2), 2)  # Mbps
                            vm['ping'] = 10  # ms (simulado)
                            
                            # Calcular uso de disco
                            disk_info = proxmox.nodes(node_name).qemu(vm['vmid']).rrddata.get(timeframe='hour')
                            if disk_info:
                                last_data = disk_info[-1]
                                vm['disk_used'] = round(last_data.get('disk', 0) / (1024 ** 3), 2)  # GB
                            else:
                                vm['disk_used'] = 0
                            
                            # Obtener tamaño total del disco
                            for key, value in vm_config.items():
                                if key.startswith(('ide', 'scsi', 'virtio')) and 'size' in value:
                                    size_str = value.split('size=')[1].split(',')[0]
                                    if 'G' in size_str:
                                        vm['disk_total'] = float(size_str.replace('G', ''))
                                    elif 'M' in size_str:
                                        vm['disk_total'] = float(size_str.replace('M', '')) / 1024
                                    break
                            
                        except Exception as e:
                            logger.warning(f"Error al obtener métricas de VM {vm['vmid']}: {str(e)}")
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
                            container_config = proxmox.nodes(node_name).lxc(container['vmid']).config.get()
                            
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
        except:
            # Si no es un cluster, simplemente pasamos
            pass
        
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
        node_status = proxmox.nodes(node_name).status.get()
        
        # Obtener VMs en este nodo
        qemu_vms = proxmox.nodes(node_name).qemu.get()
        for vm in qemu_vms:
            vm['type'] = 'qemu'
            
        # Obtener contenedores LXC en este nodo
        lxc_containers = proxmox.nodes(node_name).lxc.get()
        for container in lxc_containers:
            container['type'] = 'lxc'
            
        # Combinar VMs y contenedores
        vms = qemu_vms + lxc_containers
        
        # Obtener información del almacenamiento
        storage_info = proxmox.nodes(node_name).storage.get()
        
        # Obtener información de la red
        network_info = proxmox.nodes(node_name).network.get()
        
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
            try:
                # Intentar como QEMU VM
                proxmox.nodes(node_name).qemu(vmid).status.current.get()
                vm_type = 'qemu'
            except:
                try:
                    # Intentar como LXC container
                    proxmox.nodes(node_name).lxc(vmid).status.current.get()
                    vm_type = 'lxc'
                except Exception as e:
                    messages.error(request, f"No se pudo detectar el tipo de VM: {str(e)}")
                    return redirect('node_detail', node_name=node_name)
        
        # Obtener estado actual
        if vm_type == 'qemu':
            vm_status = proxmox.nodes(node_name).qemu(vmid).status.current.get()
            vm_config = proxmox.nodes(node_name).qemu(vmid).config.get()
        else:  # 'lxc'
            vm_status = proxmox.nodes(node_name).lxc(vmid).status.current.get()
            vm_config = proxmox.nodes(node_name).lxc(vmid).config.get()
        
        # Obtener historial de tareas
        tasks = proxmox.nodes(node_name).tasks.get(
            vmid=vmid,
            limit=10,
            start=0
        )
        
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
        return redirect('node_detail', node_name=node_name)

@login_required
def vm_action(request, node_name, vmid, action, vm_type=None):
    """
    Realiza una acción en una máquina virtual o contenedor.
    """
    try:
        proxmox = get_proxmox_connection()
        
        # Si no se proporciona vm_type, detectarlo automáticamente
        if vm_type is None:
            try:
                # Intentar como QEMU VM
                proxmox.nodes(node_name).qemu(vmid).status.current.get()
                vm_type = 'qemu'
            except:
                try:
                    # Intentar como LXC container
                    proxmox.nodes(node_name).lxc(vmid).status.current.get()
                    vm_type = 'lxc'
                except Exception as e:
                    messages.error(request, f"No se pudo detectar el tipo de VM: {str(e)}")
                    return redirect('node_detail', node_name=node_name)
        
        result = None
        # Ejecutar la acción correspondiente
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
        
        # Redirigir a la página de detalles
        if vm_type:
            return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
        else:
            return redirect('vm_detail', node_name=node_name, vmid=vmid)

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
                node['cpu'] = status.get('cpu', 0)
                node['memory'] = {
                    'total': status.get('memory', {}).get('total', 0),
                    'used': status.get('memory', {}).get('used', 0),
                    'free': status.get('memory', {}).get('free', 0)
                }
                node['uptime'] = status.get('uptime', 0)
            except:
                # Si hay error al obtener el estado, continuar con el siguiente nodo
                pass
                
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
            except:
                # Si hay error, continuar con el siguiente tipo
                pass
            
            # Obtener contenedores LXC
            try:
                lxc_containers = proxmox.nodes(node_name).lxc.get()
                for container in lxc_containers:
                    container['node'] = node_name
                    container['type'] = 'lxc'
                    vms.append(container)
            except:
                # Si hay error, continuar con el siguiente nodo
                pass
                
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
        
        # Obtener estado actual
        if vm_type == 'qemu':
            vm_status = proxmox.nodes(node_name).qemu(vmid).status.current.get()
        else:  # 'lxc'
            vm_status = proxmox.nodes(node_name).lxc(vmid).status.current.get()
            
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