from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Q

class TipoRecurso(models.Model):
    tipo_recurso_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    unidad_medida = models.CharField(max_length=20)
    descripcion = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'age_tipo_recurso'
        verbose_name = 'Tipo de Recurso'
        verbose_name_plural = 'Tipos de Recursos'

    def __str__(self):
        return self.nombre

class SistemaOperativo(models.Model):
    so_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    tipo = models.CharField(max_length=50)
    arquitectura = models.CharField(max_length=20)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'age_sistema_operativo'
        unique_together = ['nombre', 'version', 'arquitectura']
        verbose_name = 'Sistema Operativo'
        verbose_name_plural = 'Sistemas Operativos'

    def __str__(self):
        return f"{self.nombre} {self.version} ({self.arquitectura})"

# Servidor Proxmox - Movido antes de Nodo para evitar problemas de dependencia
class ProxmoxServer(models.Model):
    """Modelo para almacenar información sobre servidores Proxmox"""
    name = models.CharField(max_length=100, unique=True)
    hostname = models.CharField(max_length=255)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)  # Idealmente, usa encriptación
    node_name = models.CharField(max_length=100, default="pve", verbose_name="Nombre del Nodo (ej: www, prx1)") #Arreglo
    verify_ssl = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Añadir estos nuevos campos para almacenar especificaciones
    cpu_cores = models.IntegerField(default=0)
    cpu_model = models.CharField(max_length=255, blank=True)
    ram_total_bytes = models.BigIntegerField(default=0)
    storage_total_bytes = models.BigIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Servidor Proxmox"
        verbose_name_plural = "Servidores Proxmox"
    
    def get_or_create_node(self, node_name):
        """Obtiene o crea un nodo asociado a este servidor Proxmox"""
        from django.utils import timezone
        node, created = Nodo.objects.get_or_create(
            proxmox_server=self,
            nombre=node_name,
            defaults={
                'hostname': node_name,
                'ip_address': '0.0.0.0',  # Se debe actualizar posteriormente
                'estado': 'activo',
                'fecha_creacion': timezone.now()
            }
        )
        return node

# Nodo en la infraestructura (relacionado con ProxmoxServer)
class Nodo(models.Model):
    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    nodo_id = models.AutoField(primary_key=True)
    cluster_id = models.IntegerField(null=True, blank=True)  # Considerar modelo Cluster si aplica
    proxmox_server = models.ForeignKey(ProxmoxServer, on_delete=models.CASCADE, related_name='nodos', null=True, blank=True)
    nombre = models.CharField(max_length=100)
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField()
    ubicacion = models.CharField(max_length=255, null=True, blank=True)
    tipo_hardware = models.CharField(max_length=100, null=True, blank=True)
    estado = models.CharField(max_length=50, choices=STATUS_CHOICES, default='activo')
    ultimo_mantenimiento = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    # Nuevo campo
    proxmox_node_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'age_nodo'
        verbose_name = 'Nodo'
        verbose_name_plural = 'Nodos'
        # Agregar índice para buscar nodos por nombre
        indexes = [
            models.Index(fields=['nombre']),
        ]

    def __str__(self):
        return self.nombre
    
    @classmethod
    def get_by_proxmox_name(cls, server_name, node_name):
        """
        Obtiene un nodo utilizando el nombre del servidor Proxmox y el nombre del nodo.
        Si no existe, lo crea automáticamente.
        """
        try:
            # Primero intentamos encontrar el servidor Proxmox
            proxmox_server = ProxmoxServer.objects.get(name=server_name)
            
            # Luego buscamos el nodo o lo creamos si no existe
            return proxmox_server.get_or_create_node(node_name)
        except ProxmoxServer.DoesNotExist:
            # Si el servidor Proxmox no existe, creamos un error más descriptivo
            raise ValueError(f"El servidor Proxmox '{server_name}' no existe. Créalo primero.")

class RecursoFisico(models.Model):
    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    recurso_id = models.AutoField(primary_key=True)
    nodo = models.ForeignKey(Nodo, on_delete=models.CASCADE, related_name='recursos')
    tipo_recurso = models.ForeignKey(TipoRecurso, on_delete=models.PROTECT, related_name='recursos')
    nombre = models.CharField(max_length=100)
    capacidad_total = models.DecimalField(max_digits=12, decimal_places=2)
    capacidad_disponible = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(models.F('capacidad_total'))
        ]
    )
    estado = models.CharField(max_length=50, choices=STATUS_CHOICES, default='activo')

    class Meta:
        db_table = 'age_recurso_fisico'
        verbose_name = 'Recurso Físico'
        verbose_name_plural = 'Recursos Físicos'

    def __str__(self):
        return self.nombre

# Máquina Virtual integrada con VirtualMachine
class MaquinaVirtual(models.Model):
    STATUS_CHOICES = [
        ('running', 'En ejecución'),
        ('stopped', 'Detenido'),
        ('unknown', 'Desconocido')
    ]

    VM_TYPE_CHOICES = [
        ('qemu', 'KVM'),
        ('lxc', 'Contenedor LXC')
    ]

    vm_id = models.AutoField(primary_key=True)
    nodo = models.ForeignKey(Nodo, on_delete=models.CASCADE, related_name='maquinas_virtuales')
    sistema_operativo = models.ForeignKey(SistemaOperativo, on_delete=models.PROTECT)
    nombre = models.CharField(max_length=100)
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    vmid = models.IntegerField()  # ID dentro de Proxmox
    vm_type = models.CharField(max_length=10, choices=VM_TYPE_CHOICES, default='qemu')
    estado = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    is_monitored = models.BooleanField(default=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'age_maquina_virtual'
        unique_together = ('nodo', 'vmid')
        verbose_name = 'Máquina Virtual'
        verbose_name_plural = 'Máquinas Virtuales'

    def __str__(self):
        return f"{self.nombre} (ID: {self.vmid})"
    
    @classmethod
    def get_or_create_from_proxmox(cls, server_name, node_name, vmid, **kwargs):
        """
        Obtiene o crea una máquina virtual a partir de datos de Proxmox.
        Asegura que el nodo exista primero.
        """
        # Obtener o crear el nodo
        nodo = Nodo.get_by_proxmox_name(server_name, node_name)
        
        # Obtener o crear la máquina virtual
        try:
            vm = cls.objects.get(nodo=nodo, vmid=vmid)
            # Actualizar campos si se proporcionan en kwargs
            update_fields = []
            for key, value in kwargs.items():
                if hasattr(vm, key) and getattr(vm, key) != value:
                    setattr(vm, key, value)
                    update_fields.append(key)
            
            if update_fields:
                vm.save(update_fields=update_fields)
            
            return vm, False
        except cls.DoesNotExist:
            # Crear sistema operativo por defecto si es necesario
            if 'sistema_operativo' not in kwargs:
                sistema_operativo, _ = SistemaOperativo.objects.get_or_create(
                    nombre='Unknown',
                    version='Unknown',
                    tipo='Unknown',
                    arquitectura='x86_64',
                    defaults={'activo': True}
                )
                kwargs['sistema_operativo'] = sistema_operativo
            
            return cls.objects.create(nodo=nodo, vmid=vmid, **kwargs), True

class AsignacionRecursosInicial(models.Model):
    asignacion_id = models.AutoField(primary_key=True)
    maquina_virtual = models.ForeignKey(MaquinaVirtual, on_delete=models.CASCADE, related_name='asignaciones')
    recurso = models.ForeignKey(RecursoFisico, on_delete=models.CASCADE, related_name='asignaciones')
    cantidad_asignada = models.DecimalField(max_digits=12, decimal_places=2)
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'age_asignacion_recursos_inicial'
        verbose_name = 'Asignación de Recursos Inicial'
        verbose_name_plural = 'Asignaciones de Recursos Iniciales'

    def __str__(self):
        return f"{self.maquina_virtual} - {self.recurso} ({self.cantidad_asignada})"

class AuditoriaPeriodo(models.Model):
    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    periodo_id = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    estado = models.CharField(max_length=50, choices=STATUS_CHOICES, default='activo')

    class Meta:
        db_table = 'age_auditoria_periodo'
        verbose_name = 'Período de Auditoría'
        verbose_name_plural = 'Períodos de Auditoría'

    def __str__(self):
        return f"{self.descripcion or 'Período'} ({self.fecha_inicio} - {self.fecha_fin})"

class AuditoriaRecursosCabecera(models.Model):
    STATUS_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    auditoria_cabecera_id = models.AutoField(primary_key=True)
    maquina_virtual = models.ForeignKey(MaquinaVirtual, on_delete=models.CASCADE, related_name='auditorias')
    periodo = models.ForeignKey(AuditoriaPeriodo, on_delete=models.CASCADE, related_name='auditorias')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=50, choices=STATUS_CHOICES, default='activo')
    observaciones = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'age_auditoria_recursos_cabecera'
        verbose_name = 'Cabecera de Auditoría de Recursos'
        verbose_name_plural = 'Cabeceras de Auditoría de Recursos'

    def __str__(self):
        return f"Auditoría {self.auditoria_cabecera_id} - {self.maquina_virtual}"

class AuditoriaRecursosDetalle(models.Model):
    auditoria_detalle_id = models.AutoField(primary_key=True)
    auditoria_cabecera = models.ForeignKey(AuditoriaRecursosCabecera, on_delete=models.CASCADE, related_name='detalles')
    recurso = models.ForeignKey(RecursoFisico, on_delete=models.CASCADE, related_name='detalles_auditoria')
    consumo_actual = models.DecimalField(max_digits=12, decimal_places=2)
    porcentaje_uso = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )

    class Meta:
        db_table = 'age_auditoria_recursos_detalle'
        verbose_name = 'Detalle de Auditoría de Recursos'
        verbose_name_plural = 'Detalles de Auditoría de Recursos'

    def __str__(self):
        return f"Detalle {self.auditoria_detalle_id} - {self.recurso}"

class EstadisticaPeriodo(models.Model):
    NIVEL_CHOICES = [
        ('cluster', 'Cluster'),
        ('datacenter', 'Datacenter'),
        ('nodo', 'Nodo'),
    ]

    periodo_id = models.AutoField(primary_key=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    nivel_agregacion = models.CharField(max_length=20, choices=NIVEL_CHOICES)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'age_estadistica_periodo'
        verbose_name = 'Período de Estadística'
        verbose_name_plural = 'Períodos de Estadística'

    def __str__(self):
        return f"Período {self.periodo_id} - {self.nivel_agregacion}"

class EstadisticaRecursos(models.Model):
    TIPO_ENTIDAD_CHOICES = [
        ('cluster', 'Cluster'),
        ('datacenter', 'Datacenter'),
        ('nodo', 'Nodo'),
    ]

    estadistica_id = models.AutoField(primary_key=True)
    periodo = models.ForeignKey(EstadisticaPeriodo, on_delete=models.CASCADE, related_name='estadisticas')
    tipo_recurso = models.ForeignKey(TipoRecurso, on_delete=models.CASCADE, related_name='estadisticas')
    entidad_id = models.IntegerField()  # Consider using ForeignKey if you have specific entity models
    tipo_entidad = models.CharField(max_length=20, choices=TIPO_ENTIDAD_CHOICES)
    uso_promedio = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    uso_maximo = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    uso_minimo = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100)
        ]
    )
    total_asignado = models.DecimalField(max_digits=12, decimal_places=2)
    total_disponible = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'age_estadistica_recursos'
        verbose_name = 'Estadística de Recursos'
        verbose_name_plural = 'Estadísticas de Recursos'

    def __str__(self):
        return f"Estadística {self.estadistica_id} - {self.tipo_recurso} ({self.tipo_entidad})"
    
# Modelo Server modificado para integrarse con ProxmoxServer
class Server(models.Model):
    name = models.CharField(max_length=100)
    host = models.CharField(max_length=255)
    node = models.CharField(max_length=100)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    active = models.BooleanField(default=True)
    
    # Nuevo campo para relacionar con ProxmoxServer
    proxmox_server = models.ForeignKey(ProxmoxServer, on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_servers')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Asegura que exista el servidor Proxmox asociado"""
        super().save(*args, **kwargs)
        if not self.proxmox_server and self.active:
            # Crear automáticamente el servidor Proxmox si no existe
            proxmox_server, created = ProxmoxServer.objects.get_or_create(
                name=self.name,
                defaults={
                    'hostname': self.host,
                    'username': self.username,
                    'password': self.password,
                    'is_active': self.active
                }
            )
            if created or proxmox_server.hostname != self.host:
                proxmox_server.hostname = self.host
                proxmox_server.username = self.username
                proxmox_server.password = self.password
                proxmox_server.is_active = self.active
                proxmox_server.save()
            
            self.proxmox_server = proxmox_server
            # Guardar de nuevo sin llamar a este método para evitar recursividad
            super().save(update_fields=['proxmox_server'])

# Modelo para métricas de servidores Proxmox
class ServerMetric(models.Model):
    server = models.ForeignKey(Server, on_delete=models.CASCADE, related_name='metrics')
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_usage = models.FloatField()
    memory_usage = models.FloatField()
    disk_usage = models.FloatField()
    uptime = models.BigIntegerField()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['server', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.server.name} - {self.timestamp}"

# Modelo para métricas locales
class LocalMetric(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    cpu_usage = models.FloatField()
    memory_usage = models.FloatField()
    disk_usage = models.FloatField()
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"Local Metrics - {self.timestamp}"
    
class ServerMetrics(models.Model):
    """Métricas históricas de servidores Proxmox"""
    server = models.ForeignKey(ProxmoxServer, on_delete=models.CASCADE, related_name='server_metrics', null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    cpu_usage = models.FloatField(default=0.0)  # Porcentaje
    memory_usage = models.FloatField(default=0.0)  # Porcentaje
    memory_total = models.BigIntegerField(default=0)  # Bytes
    memory_used = models.BigIntegerField(default=0)  # Bytes
    disk_usage = models.FloatField(default=0.0)  # Porcentaje
    disk_total = models.BigIntegerField(default=0)  # Bytes
    disk_used = models.BigIntegerField(default=0)  # Bytes
    network_in = models.BigIntegerField(default=0)  # Bytes
    network_out = models.BigIntegerField(default=0)  # Bytes
    uptime = models.BigIntegerField(default=0)  # Segundos
    load_average = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, default='online')
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['server', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Métrica de Servidor'
        verbose_name_plural = 'Métricas de Servidores'

    def __str__(self):
        return f"{self.server.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    

class VMMetrics(models.Model):
    """Métricas históricas de Máquinas Virtuales"""
    vm = models.ForeignKey(MaquinaVirtual, on_delete=models.CASCADE, related_name='vm_metrics')
    timestamp = models.DateTimeField(default=timezone.now)
    cpu_usage = models.FloatField(default=0.0)  # Porcentaje
    cpu_cores = models.IntegerField(default=1)
    memory_usage = models.FloatField(default=0.0)  # Porcentaje
    memory_total = models.BigIntegerField(default=0)  # Bytes
    memory_used = models.BigIntegerField(default=0)  # Bytes
    disk_read = models.BigIntegerField(default=0)  # Bytes/s
    disk_write = models.BigIntegerField(default=0)  # Bytes/s
    network_in = models.BigIntegerField(default=0)  # Bytes/s
    network_out = models.BigIntegerField(default=0)  # Bytes/s
    status = models.CharField(max_length=20, default='unknown')
    uptime = models.BigIntegerField(default=0)  # Segundos
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['vm', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
        verbose_name = 'Métrica de VM'
        verbose_name_plural = 'Métricas de VMs'

    def __str__(self):
        return f"{self.vm.nombre} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

class MetricsAggregation(models.Model):
    """Agregaciones diarias de métricas para reportes"""
    server = models.ForeignKey(ProxmoxServer, on_delete=models.CASCADE, related_name='metrics_aggregations')
    date = models.DateField()
    avg_cpu = models.FloatField(default=0.0)
    avg_memory = models.FloatField(default=0.0)
    avg_disk = models.FloatField(default=0.0)
    max_cpu = models.FloatField(default=0.0)
    max_memory = models.FloatField(default=0.0)
    max_disk = models.FloatField(default=0.0)
    total_network_in = models.BigIntegerField(default=0)
    total_network_out = models.BigIntegerField(default=0)
    vm_count = models.IntegerField(default=0)
    active_vm_count = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['server', 'date']
        verbose_name = 'Agregación de Métricas'
        verbose_name_plural = 'Agregaciones de Métricas'

    def __str__(self):
        return f"{self.server.name} - {self.date}"