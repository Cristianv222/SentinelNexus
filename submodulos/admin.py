
from django.contrib import admin
from .models import (
    TipoRecurso, SistemaOperativo, ProxmoxServer, Nodo, RecursoFisico,
    MaquinaVirtual, Server, ServerMetric, LocalMetric, ServerMetrics,
    AsignacionRecursosInicial, AuditoriaPeriodo, AuditoriaRecursosCabecera,
    AuditoriaRecursosDetalle, EstadisticaPeriodo, EstadisticaRecursos
)

# --- Registros para la Configuración de Infraestructura ---

@admin.register(ProxmoxServer)
class ProxmoxServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostname', 'username', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'hostname')

@admin.register(Server)
class ServerAdmin(admin.ModelAdmin):
    """
    """
    list_display = ('name', 'host', 'node', 'username', 'active')
    list_filter = ('active',)
    search_fields = ('name', 'host', 'node')

@admin.register(Nodo)
class NodoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'hostname', 'ip_address', 'proxmox_server', 'estado')
    list_filter = ('estado', 'proxmox_server')
    search_fields = ('nombre', 'hostname', 'ip_address')

@admin.register(MaquinaVirtual)
class MaquinaVirtualAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'vmid', 'nodo', 'estado', 'vm_type', 'is_monitored')
    list_filter = ('estado', 'vm_type', 'is_monitored', 'nodo')
    search_fields = ('nombre', 'hostname', 'vmid')

# --- Registros para ver las Métricas Recolectadas ---

@admin.register(ServerMetric)
class ServerMetricAdmin(admin.ModelAdmin):
    """
    Aquí es donde 'tasks.py' guarda las métricas.
    """
    list_display = ('server', 'timestamp', 'cpu_usage', 'memory_usage', 'disk_usage')
    list_filter = ('server', 'timestamp')

@admin.register(LocalMetric)
class LocalMetricAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'cpu_usage', 'memory_usage', 'disk_usage')
    list_filter = ('timestamp',)

@admin.register(ServerMetrics)
class ServerMetricsAdmin(admin.ModelAdmin):
    """
   
   """
    list_display = ( 'timestamp', 'cpu_usage', 'memory_usage')
    list_filter = ( 'timestamp',)

# --- Registros para Modelos de Soporte ---

admin.site.register(TipoRecurso)
admin.site.register(SistemaOperativo)

# (Puedes registrar los otros modelos si también necesitas verlos en el admin)
# admin.site.register(RecursoFisico)
# admin.site.register(AsignacionRecursosInicial)
# admin.site.register(AuditoriaPeriodo)
# admin.site.register(AuditoriaRecursosCabecera)
# admin.site.register(AuditoriaRecursosDetalle)
# admin.site.register(EstadisticaPeriodo)
# admin.site.register(EstadisticaRecursos)