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
from submodulos.models import (
    ProxmoxServer, Nodo, SistemaOperativo, MaquinaVirtual,
    TipoRecurso, RecursoFisico, AsignacionRecursosInicial,
    AuditoriaPeriodo, AuditoriaRecursosCabecera, AuditoriaRecursosDetalle
)
import threading
import os
import string
import subprocess
import requests
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

logger = logging.getLogger(__name__)

@csrf_exempt
def grafana_proxy(request, path=''):
    """
    Proxy mejorado para Grafana que gestiona redirecciones y cookies correctamente
    para evitar bucles de redirección y problemas de autenticación.
    """
    grafana_url = getattr(settings, 'GRAFANA_URL', 'http://10.100.100.201:3000')
    
    # Normalizar el path para evitar problemas con barras
    path = path.lstrip('/') if path else ''
    url = f"{grafana_url}/{path}" if path else grafana_url
    
    # Detectar bucles de redirección
    redirect_count = int(request.COOKIES.get('grafana_redirect_count', 0))
    if redirect_count > 5:  # Limitar a 5 redirecciones
        return HttpResponse(
            """
            <div style="padding: 20px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 5px;">
                <h3>Error: Demasiadas redirecciones</h3>
                <p>Se detectó un bucle de redirección entre Django y Grafana.</p>
                <p>Posibles soluciones:</p>
                <ul>
                    <li>Verifica la configuración en grafana.ini</li>
                    <li>Asegúrate de que serve_from_sub_path = true y root_url = http://tu-servidor/grafana-proxy</li>
                    <li>Considera activar auth.anonymous.enabled = true para desarrollo</li>
                </ul>
                <p>Puedes acceder directamente a <a href="{grafana_url}" target="_blank">Grafana</a> para probar que funciona.</p>
            </div>
            """,
            content_type='text/html',
            status=400
        )
    
    logger.debug(f"Proxying request to: {url} (redirect count: {redirect_count})")
    
    try:
        # Preservar todos los parámetros y encabezados originales
        headers = {}
        for header, value in request.headers.items():
            if header.lower() not in ['host', 'content-length']:
                headers[header] = value
                
        # Añadir token si existe
        api_key = getattr(settings, 'GRAFANA_API_KEY', '')
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        # Añadir headers de CORS y origin
        proxy_host = request.get_host()
        proxy_url_base = f"{request.scheme}://{proxy_host}/grafana-proxy"
        headers['X-Forwarded-Host'] = proxy_host
        headers['X-Forwarded-Proto'] = request.scheme
        headers['Origin'] = f"{request.scheme}://{proxy_host}"
        
        # Headers de autenticación si el usuario está autenticado
        if request.user.is_authenticated:
            headers['X-WEBAUTH-USER'] = request.user.username
            headers['X-WEBAUTH-NAME'] = request.user.get_full_name() or request.user.username
            headers['X-WEBAUTH-EMAIL'] = getattr(request.user, 'email', '')
        
        # Recolectar cookies para enviar a Grafana
        cookies = {}
        for cookie_name, cookie_value in request.COOKIES.items():
            # Excluir nuestra cookie de contador de redirecciones
            if cookie_name != 'grafana_redirect_count':
                cookies[cookie_name] = cookie_value
        
        # Realizar la solicitud con el método original
        response = requests.request(
            method=request.method,
            url=url,
            params=request.GET.dict(),
            data=request.body,
            headers=headers,
            cookies=cookies,
            timeout=15,
            verify=False,  # Solo para desarrollo
            allow_redirects=False  # Manejar redirecciones manualmente
        )
        
        # Manejar redirecciones para evitar bucles
        if response.status_code in [301, 302, 303, 307, 308]:
            redirect_url = response.headers.get('Location', '')
            
            # Reescribir la URL de redirección
            if redirect_url.startswith(grafana_url):
                # Si es una URL completa a Grafana, convertirla a nuestro proxy
                new_redirect = redirect_url.replace(grafana_url, proxy_url_base)
                logger.debug(f"Rewriting external redirect from {redirect_url} to {new_redirect}")
                redirect_url = new_redirect
            elif redirect_url.startswith('/'):
                # Si es una URL relativa desde la raíz, añadir nuestro prefijo
                new_redirect = f"/grafana-proxy{redirect_url}"
                logger.debug(f"Rewriting relative redirect from {redirect_url} to {new_redirect}")
                redirect_url = new_redirect
            
            # Crear respuesta de redirección
            django_response = HttpResponse(status=response.status_code)
            django_response['Location'] = redirect_url
            
            # Incrementar contador de redirecciones
            django_response.set_cookie('grafana_redirect_count', str(redirect_count + 1), max_age=60)
            
            # Transferir cookies de la respuesta original
            for cookie in response.cookies:
                cookie_obj = response.cookies[cookie]
                django_response.set_cookie(
                    key=cookie,
                    value=cookie_obj.value,
                    expires=cookie_obj.expires,
                    path="/grafana-proxy" if cookie_obj.path == "/" else f"/grafana-proxy{cookie_obj.path}",
                    domain=None,
                    secure=cookie_obj.secure,
                    httponly=True,
                    samesite='None'  # Para permitir cookies en iframe
                )
            
            return django_response
        
        # Para respuestas normales (no redirecciones), resetear contador
        content_type = response.headers.get('Content-Type', '')
        content = response.content
        
        # Procesar contenido HTML, JS, CSS y JSON para reescribir URLs
        if content_type and ('text/html' in content_type or 
                           'application/javascript' in content_type or 
                           'text/css' in content_type or 
                           'application/json' in content_type):
            try:
                content_text = content.decode('utf-8')
                
                # Reemplazar URLs absolutas con nuestro prefijo proxy
                
                # URLs en atributos href y src
                content_text = content_text.replace('href="/', 'href="/grafana-proxy/')
                content_text = content_text.replace('src="/', 'src="/grafana-proxy/')
                content_text = content_text.replace("href='/", "href='/grafana-proxy/")
                content_text = content_text.replace("src='/", "src='/grafana-proxy/")
                
                # URLs en código JavaScript
                content_text = content_text.replace('"/api/', '"/grafana-proxy/api/')
                content_text = content_text.replace('"/public/', '"/grafana-proxy/public/')
                content_text = content_text.replace('"/assets/', '"/grafana-proxy/assets/')
                content_text = content_text.replace('"/login/', '"/grafana-proxy/login/')
                content_text = content_text.replace('"/logout/', '"/grafana-proxy/logout/')
                content_text = content_text.replace('"/css/', '"/grafana-proxy/css/')
                content_text = content_text.replace('"/img/', '"/grafana-proxy/img/')
                content_text = content_text.replace('"/js/', '"/grafana-proxy/js/')
                content_text = content_text.replace('"/build/', '"/grafana-proxy/build/')
                content_text = content_text.replace('"/avatar/', '"/grafana-proxy/avatar/')
                content_text = content_text.replace('"/dashboard', '"/grafana-proxy/dashboard')
                content_text = content_text.replace('"/d/', '"/grafana-proxy/d/')
                content_text = content_text.replace('"/explore', '"/grafana-proxy/explore')
                content_text = content_text.replace('"/plugins/', '"/grafana-proxy/plugins/')
                
                # Configuración del subpath en JSON
                content_text = content_text.replace('"appSubUrl":""', '"appSubUrl":"/grafana-proxy"')
                content_text = content_text.replace('"appSubUrl":"/"', '"appSubUrl":"/grafana-proxy/"')
                
                # Reemplazar referencias a la URL completa
                content_text = content_text.replace(grafana_url, proxy_url_base)
                
                # Recodificar el contenido
                content = content_text.encode('utf-8')
                
            except UnicodeDecodeError:
                logger.warning(f"No se pudo decodificar el contenido para reescribir URLs: {content_type}")
        
        # Crear respuesta Django
        django_response = HttpResponse(
            content=content,
            status=response.status_code,
            content_type=content_type
        )
        
        # Resetear contador de redirecciones
        django_response.set_cookie('grafana_redirect_count', '0', max_age=60)
        
        # Transferir encabezados, excepto los que causarían problemas
        excluded_headers = ['content-length', 'transfer-encoding', 'connection', 'content-encoding', 'set-cookie']
        for header, value in response.headers.items():
            if header.lower() not in excluded_headers:
                django_response[header] = value
        
        # Transferir cookies con la configuración correcta para el proxy
        for cookie in response.cookies:
            cookie_obj = response.cookies[cookie]
            
            # Ajustar el path para que funcione con nuestro proxy
            cookie_path = "/grafana-proxy"
            if cookie_obj.path and cookie_obj.path != "/":
                cookie_path = f"/grafana-proxy{cookie_obj.path}"
                
            django_response.set_cookie(
                key=cookie,
                value=cookie_obj.value,
                expires=cookie_obj.expires,
                path=cookie_path,
                domain=None,  # Usar dominio por defecto
                secure=cookie_obj.secure,
                httponly=True,  # Mejorar seguridad
                samesite='None'  # Permitir uso en iframe
            )
        
        return django_response
        
    except Exception as e:
        logger.error(f"Error en grafana_proxy: {str(e)}", exc_info=True)
        error_msg = f"""
        <div style="padding: 20px; background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; border-radius: 5px;">
            <h3>Error al conectar con Grafana</h3>
            <p>{str(e)}</p>
            <hr>
            <p>Comprueba que Grafana esté funcionando correctamente en <a href="{grafana_url}" target="_blank">{grafana_url}</a></p>
            <p>Asegúrate de que tu servidor Django puede acceder a esa URL.</p>
            <details>
                <summary>Detalles técnicos (Expandir)</summary>
                <p><strong>URL solicitada:</strong> {url}</p>
                <p><strong>Método:</strong> {request.method}</p>
            </details>
        </div>
        """
        return HttpResponse(error_msg, content_type='text/html', status=500)
    
@login_required
def grafana_dashboard(request):
    """
    Vista que muestra el dashboard de Grafana integrado
    """
    context = {
        'grafana_url': settings.GRAFANA_URL,
        'dashboard_id': getattr(settings, 'GRAFANA_DASHBOARD_ID', 'proxmox-monitoring'),
    }
    return render(request, 'grafana.html', context)

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

# Clase para sincronizar datos de Proxmox con la base de datos
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
            self.proxmox = get_proxmox_connection()
            # Crear o actualizar el registro del servidor en la base de datos
            self.server, created = ProxmoxServer.objects.update_or_create(
                hostname=settings.PROXMOX['host'].split(':')[0],  # Quitar puerto si existe
                defaults={
                    'name': f"Proxmox-{settings.PROXMOX['host'].split(':')[0]}",
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
        self.sync_nodes()
        self.sync_resource_types()
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
            logger.error(f"Error al sincronizar almacenamiento para nodo {node.nombre}: {str(e)}")

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
                    logger.error(f"Error al obtener VMs QEMU en nodo {node_name}: {str(e)}")
                
                # Obtener todos los contenedores LXC
                try:
                    lxc_containers = self.proxmox.nodes(node_name).lxc.get()
                    for container in lxc_containers:
                        self.process_vm(node, container, 'lxc')
                except Exception as e:
                    logger.error(f"Error al obtener contenedores LXC en nodo {node_name}: {str(e)}")
                    
            except Nodo.DoesNotExist:
                logger.error(f"Nodo {node_name} no encontrado en la base de datos.")

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
                'last_checked': datetime.now()
            }
        )
        
        # Si es una VM nueva, asignarle recursos iniciales
        if created:
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
                try:
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
                            if 'size' in str(value):
                                # Convertir de formato Proxmox (ej: 32G) a GB
                                size_str = str(value).split('size=')[1].split(',')[0]
                                if 'G' in size_str:
                                    storage_gb += float(size_str.replace('G', ''))
                                elif 'T' in size_str:
                                    storage_gb += float(size_str.replace('T', '')) * 1024
                    
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=storage_resource,
                        cantidad_asignada=storage_gb
                    )
                except Exception as e:
                    logger.error(f"Error al obtener config de VM {vm.nombre}: {str(e)}")
                    # Asignar valores por defecto
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=cpu_resource,
                        cantidad_asignada=1
                    )
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=ram_resource,
                        cantidad_asignada=512
                    )
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=storage_resource,
                        cantidad_asignada=20
                    )
            
            # Proceso similar para LXC, con ajustes específicos para contenedores
            elif vm_type == 'lxc':
                try:
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
                    
                    # Asignar almacenamiento
                    storage_gb = 8  # Valor por defecto
                    if 'rootfs' in lxc_config and 'size' in str(lxc_config.get('rootfs', '')):
                        storage_str = str(lxc_config.get('rootfs')).split('size=')[1].split(',')[0]
                        if 'G' in storage_str:
                            storage_gb = float(storage_str.replace('G', ''))
                        elif 'T' in storage_str:
                            storage_gb = float(storage_str.replace('T', '')) * 1024
                    
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=storage_resource,
                        cantidad_asignada=storage_gb
                    )
                except Exception as e:
                    logger.error(f"Error al obtener config de LXC {vm.nombre}: {str(e)}")
                    # Asignar valores por defecto
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=cpu_resource,
                        cantidad_asignada=1
                    )
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=ram_resource,
                        cantidad_asignada=512
                    )
                    AsignacionRecursosInicial.objects.create(
                        maquina_virtual=vm,
                        recurso=storage_resource,
                        cantidad_asignada=8
                    )
        
        except Exception as e:
            logger.error(f"Error al asignar recursos iniciales para VM {vm.nombre}: {str(e)}")

# Función para sincronizar datos desde la vista
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
        
        # Sincronizar datos con la base de datos
        try:
            # Si ha pasado más de 1 hora desde la última sincronización, realizar una nueva
            # Puedes ajustar esta lógica según tus necesidades
            last_sync = ProxmoxServer.objects.filter(is_active=True).order_by('-updated_at').first()
            sync_needed = True
            
            if last_sync and last_sync.updated_at:
                time_since_last_sync = datetime.now() - last_sync.updated_at.replace(tzinfo=None)
                if time_since_last_sync.total_seconds() < 3600:  # Menos de 1 hora
                    sync_needed = False
            
            if sync_needed:
                logger.info("Iniciando sincronización de datos con la base de datos...")
                sync_result = sync_proxmox_data()
                if sync_result['status'] == 'success':
                    logger.info("Sincronización completada correctamente")
                else:
                    logger.error(f"Error en la sincronización: {sync_result['message']}")
        except Exception as sync_error:
            logger.error(f"Error al intentar sincronizar datos: {str(sync_error)}")
            
        # Obtener datos de la base de datos para mostrar en el dashboard
        db_nodes = Nodo.objects.all().count()
        db_vms = MaquinaVirtual.objects.all().count()
        db_resources = RecursoFisico.objects.all()
            
        return render(request, 'dashboard.html', {
            'nodes': nodes,
            'vms': vms,
            'running_vms': running_vms,
            'cluster_status': cluster_status,
            'db_nodes': db_nodes,
            'db_vms': db_vms,
            'db_resources': db_resources
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
def sync_proxmox(request):
    """
    Vista para sincronizar datos de Proxmox
    """
    if request.method == 'POST':
        server_id = request.POST.get('server_id')
        result = sync_proxmox_data(server_id)
        
        if result['status'] == 'success':
            messages.success(request, result['message'])
        else:
            messages.error(request, result['message'])
    
    return redirect('dashboard')

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
        
        # Obtener datos del nodo desde la base de datos
        try:
            db_node = Nodo.objects.get(nombre=node_name)
            db_resources = RecursoFisico.objects.filter(nodo=db_node)
            db_vms = MaquinaVirtual.objects.filter(nodo=db_node)
        except Nodo.DoesNotExist:
            db_node = None
            db_resources = []
            db_vms = []
        
        return render(request, 'node_detail.html', {
            'node_name': node_name,
            'node_status': node_status,
            'vms': vms,
            'storage_info': storage_info,
            'network_info': network_info,
            'db_node': db_node,
            'db_resources': db_resources,
            'db_vms': db_vms
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
        
        # Obtener datos de la VM desde la base de datos
        try:
            db_node = Nodo.objects.get(nombre=node_name)
            db_vm = MaquinaVirtual.objects.get(nodo=db_node, vmid=vmid)
            db_resources = AsignacionRecursosInicial.objects.filter(maquina_virtual=db_vm)
        except (Nodo.DoesNotExist, MaquinaVirtual.DoesNotExist):
            db_vm = None
            db_resources = []
        
        return render(request, 'vm_detail.html', {
            'node_name': node_name,
            'vmid': vmid,
            'vm_type': vm_type,
            'vm_status': vm_status,
            'vm_config': vm_config,
            'tasks': tasks,
            'db_vm': db_vm,
            'db_resources': db_resources
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
            
            # Actualizar estado en la base de datos
            try:
                db_node = Nodo.objects.get(nombre=node_name)
                db_vm = MaquinaVirtual.objects.get(nodo=db_node, vmid=vmid)
                
                # Establecer el estado según la acción
                if action == 'start':
                    db_vm.estado = 'running'
                elif action in ['stop', 'shutdown']:
                    db_vm.estado = 'stopped'
                
                db_vm.last_checked = datetime.now()
                db_vm.save()
            except (Nodo.DoesNotExist, MaquinaVirtual.DoesNotExist) as db_error:
                logger.warning(f"No se pudo actualizar el estado en BD: {str(db_error)}")
        
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
        # Obtener servidores desde la base de datos
        proxmox_servers = ProxmoxServer.objects.all()
        
        # Obtener información de Proxmox si es posible
        nodes = []
        try:
            proxmox = get_proxmox_connection()
            nodes = proxmox.nodes.get()
        except Exception as e:
            logger.warning(f"Error al obtener nodos de Proxmox: {str(e)}")
        
        return render(request, 'server_list.html', {
            'proxmox_servers': proxmox_servers,
            'nodes': nodes
        })
    except Exception as e:
        messages.error(request, f"Error al obtener lista de servidores: {str(e)}")
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
        
        # Actualizar datos en la base de datos
        try:
            db_node = Nodo.objects.get(nombre=node_name)
            db_vm, created = MaquinaVirtual.objects.get_or_create(
                nodo=db_node,
                vmid=vmid,
                defaults={
                    'nombre': vm_status.get('name', f"VM-{vmid}"),
                    'hostname': vm_status.get('name', f"VM-{vmid}"),
                    'vm_type': vm_type,
                    'estado': vm_status.get('status', 'unknown'),
                    'is_monitored': True,
                    'last_checked': datetime.now()
                }
            )
            if not created:
                db_vm.estado = vm_status.get('status', 'unknown')
                db_vm.last_checked = datetime.now()
                db_vm.save()
                
        except Exception as db_error:
            logger.warning(f"Error al actualizar datos de VM en BD: {str(db_error)}")
        
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
        
        # Actualizar datos en la base de datos
        try:
            # Sincronizar nodos y VMs si es necesario
            sync_needed = False
            last_sync = ProxmoxServer.objects.filter(is_active=True).order_by('-updated_at').first()
            
            if last_sync and last_sync.updated_at:
                time_since_last_sync = datetime.now() - last_sync.updated_at.replace(tzinfo=None)
                if time_since_last_sync.total_seconds() > 7200:  # Más de 2 horas
                    sync_needed = True
            else:
                sync_needed = True
                
            if sync_needed:
                logger.info("Sincronizando datos con la base de datos desde api_dashboard_metrics...")
                sync_thread = threading.Thread(target=sync_proxmox_data)
                sync_thread.daemon = True
                sync_thread.start()
        except Exception as sync_error:
            logger.error(f"Error al programar sincronización: {str(sync_error)}")
        
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
        
        # Obtener todas las VMs para el selector
        vms = []
        try:
            # Obtener VMs de la base de datos
            db_vms = MaquinaVirtual.objects.all().select_related('nodo', 'sistema_operativo')
            
            for vm in db_vms:
                vms.append({
                    'vmid': vm.vmid,
                    'name': vm.nombre,
                    'node': vm.nodo.nombre,
                    'type': vm.vm_type,
                    'status': vm.estado,
                    'os': str(vm.sistema_operativo)
                })
        except Exception as e:
            logger.warning(f"Error al obtener VMs de la base de datos: {str(e)}")
            
            # Si falla la BD, intentar obtener desde Proxmox directamente
            for node in nodes:
                node_name = node['node']
                try:
                    qemu_vms = proxmox.nodes(node_name).qemu.get()
                    for vm in qemu_vms:
                        vms.append({
                            'vmid': vm['vmid'],
                            'name': vm.get('name', f"VM {vm['vmid']}"),
                            'node': node_name,
                            'type': 'qemu',
                            'status': vm.get('status', 'unknown')
                        })
                except Exception as e:
                    logger.warning(f"Error al obtener VMs QEMU del nodo {node_name}: {str(e)}")
                
                try:
                    lxc_containers = proxmox.nodes(node_name).lxc.get()
                    for container in lxc_containers:
                        vms.append({
                            'vmid': container['vmid'],
                            'name': container.get('name', f"CT {container['vmid']}"),
                            'node': node_name,
                            'type': 'lxc',
                            'status': container.get('status', 'unknown')
                        })
                except Exception as e:
                    logger.warning(f"Error al obtener contenedores LXC del nodo {node_name}: {str(e)}")
        
        # Obtener estadísticas generales desde la base de datos
        db_stats = {
            'total_nodes': Nodo.objects.count(),
            'total_vms': MaquinaVirtual.objects.count(),
            'recursos': RecursoFisico.objects.all().select_related('nodo', 'tipo_recurso').count()
        }
        
        return render(request, 'metrics_dashboard.html', {
            'nodes': nodes,
            'vms': vms,
            'db_stats': db_stats
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
@login_required
def vm_console(request, node_name, vmid, vm_type):
    """Vista para mostrar la consola de una máquina virtual."""
    
    # Verificar que el tipo sea qemu (solo VMs, no contenedores)
    if vm_type != 'qemu':
        messages.error(request, "La consola solo está disponible para máquinas virtuales KVM")
        return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
    
    try:
        # Usar la función existente para obtener la conexión Proxmox
        proxmox = get_proxmox_connection()
        
        # Obtener información de la VM
        vm_info = proxmox.nodes(node_name).qemu(vmid).status.current.get()
        
        # Verificar si la VM está en ejecución
        if vm_info['status'] != 'running':
            messages.warning(request, "La máquina virtual debe estar en ejecución para acceder a la consola")
            return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
        
        # Obtener el ticket de VNC
        vnc_config = proxmox.nodes(node_name).qemu(vmid).vncproxy.post()
        
        # Configurar proxy websocket
        console_port = random.randint(6000, 7000)  # Puerto aleatorio para el proxy
        proxy_token = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        # Iniciar websockify en un proceso separado
        websockify_cmd = f"websockify {console_port} {vnc_config['host']}:{vnc_config['port']} --web=/usr/share/novnc/ -t {proxy_token}"
        subprocess.Popen(websockify_cmd, shell=True)
        
        # Esperar un segundo para que websockify se inicie
        time.sleep(1)
        
        context = {
            'vm_name': vm_info['name'],
            'vmid': vmid,
            'node_name': node_name,
            'vnc_port': console_port,
            'vnc_token': proxy_token,
            'vnc_password': vnc_config.get('password', ''),
        }
        
        return render(request, 'vm_console.html', context)
        
    except Exception as e:
        logger.error(f"Error al conectar con la consola VNC para VM {vmid}: {str(e)}")
        messages.error(request, f"Error al conectar con la consola: {str(e)}")
        return redirect('vm_detail_with_type', node_name=node_name, vmid=vmid, vm_type=vm_type)
    