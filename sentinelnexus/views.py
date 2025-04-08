from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.conf import settings
from proxmoxer import ProxmoxAPI
import json

def get_proxmox_connection():
    """
    Establece una conexión con el servidor Proxmox.
    """
    proxmox = ProxmoxAPI(
        settings.PROXMOX_HOST,
        user=settings.PROXMOX_USER,
        password=settings.PROXMOX_PASSWORD,
        verify_ssl=settings.PROXMOX_VERIFY_SSL
    )
    return proxmox

@login_required
def dashboard(request):
    """
    Dashboard principal que muestra una visión general de los nodos y VMs
    """
    proxmox = get_proxmox_connection()
    
    try:
        # Obtener todos los nodos
        nodes = proxmox.nodes.get()
        
        # Obtener todas las VMs
        vms = []
        for node in nodes:
            node_name = node['node']
            # Obtener VMs (QEMU)
            qemu_vms = proxmox.nodes(node_name).qemu.get()
            for vm in qemu_vms:
                vm['node'] = node_name
                vm['type'] = 'qemu'
                vms.append(vm)
            
            # Obtener LXC containers
            lxc_containers = proxmox.nodes(node_name).lxc.get()
            for container in lxc_containers:
                container['node'] = node_name
                container['type'] = 'lxc'
                vms.append(container)
                
        # Obtener resumen del cluster
        cluster_status = None
        try:
            cluster_status = proxmox.cluster.status.get()
        except:
            # Si no es un cluster, simplemente pasamos
            pass
            
        return render(request, 'dashboard.html', {
            'nodes': nodes,
            'vms': vms,
            'cluster_status': cluster_status
        })
    except Exception as e:
        messages.error(request, f"Error al conectar con Proxmox: {str(e)}")
        return render(request, 'dashboard.html', {
            'connection_error': True,
            'error_message': str(e)
        })

@login_required
def node_detail(request, node_name):
    """
    Muestra los detalles de un nodo específico.
    """
    proxmox = get_proxmox_connection()
    
    try:
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
    
    try:
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
    
    try:
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
    proxmox = get_proxmox_connection()
    
    try:
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
    proxmox = get_proxmox_connection()
    node_filter = request.GET.get('node')
    
    try:
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
    proxmox = get_proxmox_connection()
    
    try:
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