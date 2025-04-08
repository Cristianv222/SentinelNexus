from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

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
    verify_ssl = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Servidor Proxmox"
        verbose_name_plural = "Servidores Proxmox"

# Nodo en la infraestructura (relacionado con ProxmoxServer)
# Manteniendo solo la versión más completa
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

    class Meta:
        db_table = 'age_nodo'
        verbose_name = 'Nodo'
        verbose_name_plural = 'Nodos'

    def __str__(self):
        return self.nombre

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
# Manteniendo solo la versión más completa
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