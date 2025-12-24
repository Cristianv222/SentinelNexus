 # utils/proxmox_manager.py
from django.conf import settings
from proxmoxer import ProxmoxAPI, AuthenticationError
import logging

logger = logging.getLogger(__name__)

class ProxmoxManager:
    """
    Clase para gestionar múltiples conexiones a nodos Proxmox
    """
    
    def __init__(self):
        self.active_nodes = self._get_active_nodes()
    
    def _get_active_nodes(self):
        """Obtiene los nodos que tienen configuración completa desde BD o settings"""
        active_nodes = {}
        
        # 1. Intentar cargar desde Base de Datos (Prioridad)
        try:
            from submodulos.models import ProxmoxServer
            servers = ProxmoxServer.objects.filter(is_active=True)
            
            for server in servers:
                # Usar ID como clave principal (string)
                node_key = str(server.id)
                active_nodes[node_key] = {
                    'host': server.hostname,
                    'user': server.username,
                    'password': server.password,
                    'verify_ssl': server.verify_ssl,
                    'port': '8006',
                    'name': server.name,
                    'node': server.node_name,
                    'type': 'db',
                    'db_id': server.id
                }
                # También mapear por hostname para búsquedas inversas
                active_nodes[server.hostname] = active_nodes[node_key]
                logger.info(f"Cargado servidor Proxmox desde BD: {server.name} ({server.hostname})")
                
        except Exception as e:
            logger.warning(f"No se pudieron cargar nodos desde BD: {str(e)}")

        # 2. Cargar desde settings como fallback o complemento
        if hasattr(settings, 'PROXMOX_NODES'):
            for key, config in settings.PROXMOX_NODES.items():
                # Solo agregar si no existe ya (la BD tiene prioridad)
                if key not in active_nodes:
                    if (config.get('host') and config.get('user') and config.get('password')):
                        config['type'] = 'ksettings'
                        config['node'] = config.get('node', 'pve') # Default node name
                        active_nodes[key] = config
                        logger.info(f"Nodo Proxmox activo desde settings: {key}")
        
        return active_nodes
    
    def get_node_config(self, node_key):
        """Obtiene la configuración de un nodo específico"""
        return self.active_nodes.get(node_key)
    
    def get_all_nodes(self):
        """Obtiene todos los nodos activos"""
        return self.active_nodes
    
    def get_node_names(self):
        """Obtiene una lista de nombres de nodos activos"""
        return list(self.active_nodes.keys())
    
    def is_node_active(self, node_key):
        """Verifica si un nodo está activo"""
        return node_key in self.active_nodes
    
    def get_connection(self, node_key):
        """
        Establece una conexión con un nodo específico de Proxmox
        """
        node_config = self.get_node_config(node_key)
        if not node_config:
            raise ValueError(f"Nodo '{node_key}' no encontrado o no configurado")
        
        try:
            # Asegurar formato correcto del usuario
            user = node_config['user']
            if '@' not in user:
                user = f"{user}@pam"
            
            # Especificar puerto si no está incluido
            host = node_config['host']
            port = node_config.get('port', '8006')
            if ':' not in host:
                host = f"{host}:{port}"
                
            logger.info(f"Conectando a nodo {node_key}: {host} como {user}")
            
            proxmox = ProxmoxAPI(
                host,
                user=user,
                password=node_config['password'],
                verify_ssl=node_config.get('verify_ssl', False),
                timeout=30
            )
            
            # Probar la conexión
            proxmox.version.get()
            logger.info(f"Conexión exitosa con nodo {node_key}")
            return proxmox
            
        except AuthenticationError as e:
            logger.error(f"Error de autenticación en nodo {node_key}: {str(e)}")
            raise AuthenticationError(f"Error de autenticación en {node_key}: {str(e)}")
        except Exception as e:
            logger.error(f"Error al conectar con nodo {node_key}: {str(e)}")
            raise Exception(f"Error al conectar con {node_key}: {str(e)}")
    
    def get_connection_url(self, node_key):
        """Construye la URL de conexión para un nodo"""
        node_config = self.get_node_config(node_key)
        if not node_config:
            return None
        
        protocol = 'https' if node_config.get('verify_ssl', False) else 'https'
        host = node_config['host']
        port = node_config.get('port', '8006')
        
        return f"{protocol}://{host}:{port}"
    
    def test_connection(self, node_key):
        """Prueba la conexión a un nodo específico"""
        try:
            proxmox = self.get_connection(node_key)
            version = proxmox.version.get()
            return {
                'success': True,
                'version': version,
                'message': 'Conexión exitosa'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Error de conexión: {str(e)}'
            }
    
    def validate_nodes(self):
        """Valida la configuración de todos los nodos"""
        validation_results = {}
        
        for node_key, node_config in self.active_nodes.items():
            validation_results[node_key] = {
                'valid': True,
                'issues': []
            }
            
            # Validar campos requeridos
            required_fields = ['host', 'user', 'password']
            for field in required_fields:
                if not node_config.get(field):
                    validation_results[node_key]['valid'] = False
                    validation_results[node_key]['issues'].append(f"Campo {field} faltante")
            
            # Validar formato de host (IP o hostname)
            host = node_config.get('host', '')
            if host and not (self._is_valid_ip(host) or self._is_valid_hostname(host)):
                validation_results[node_key]['valid'] = False
                validation_results[node_key]['issues'].append("Formato de host inválido")
        
        return validation_results
    
    def _is_valid_ip(self, ip):
        """Valida si es una IP válida"""
        try:
            import ipaddress
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def _is_valid_hostname(self, hostname):
        """Valida si es un hostname válido"""
        import re
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return re.match(pattern, hostname) is not None

# Instancia global del manager
proxmox_manager = ProxmoxManager()

# Funciones de conveniencia
def get_active_proxmox_nodes():
    """Función de conveniencia para obtener nodos activos"""
    return proxmox_manager.get_all_nodes()

def get_proxmox_node(node_key):
    """Función de conveniencia para obtener un nodo específico"""
    return proxmox_manager.get_node_config(node_key)

def get_proxmox_connection(node_key):
    """Función de conveniencia para obtener conexión a un nodo"""
    return proxmox_manager.get_connection(node_key)