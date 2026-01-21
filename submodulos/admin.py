from django.contrib import admin
# Asegúrate de importar los modelos correctos. 
# Si borraste 'Server' o 'ServerMetrics' en models.py, bórralos de aquí también.
from .models import (
    TipoRecurso, SistemaOperativo, ProxmoxServer, Nodo, RecursoFisico,
    MaquinaVirtual, ServerMetric, LocalMetric, 
    AsignacionRecursosInicial, AuditoriaPeriodo, AuditoriaRecursosCabecera,
    AuditoriaRecursosDetalle, EstadisticaPeriodo, EstadisticaRecursos
    # Nota: He quitado 'Server' y 'ServerMetrics' de la lista por si acaso causan conflicto,
    # pero agrégalos si tus modelos aún existen.
)

# --- Registros para la Configuración de Infraestructura ---

@admin.register(ProxmoxServer)
class ProxmoxServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostname', 'username', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'hostname')

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


# Reemplazamos la configuración vieja de ServerMetric por la nueva que coincide con el nuevo modelo

@admin.register(ServerMetric)
class ServerMetricAdmin(admin.ModelAdmin):
    """
    Tabla para el historial de salud de servidores Proxmox (SPADE).
    """
    # Actualizado para coincidir con el modelo ServerMetric existente
    list_display = ('server', 'cpu_usage', 'memory_usage', 'uptime', 'timestamp')
    list_filter = ('server', 'timestamp')
    search_fields = ('server__name',)

# --------------------------------------

@admin.register(LocalMetric)
class LocalMetricAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'cpu_usage', 'memory_usage', 'disk_usage')
    list_filter = ('timestamp',)

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