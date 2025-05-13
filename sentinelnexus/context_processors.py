# sentinelnexus/context_processors.py
from django.conf import settings

def grafana_settings(request):
    """
    Añade la configuración de Grafana al contexto de las plantillas
    """
    return {
        'GRAFANA_ENABLED': getattr(settings, 'GRAFANA_ENABLED', False),
        'GRAFANA_URL': getattr(settings, 'GRAFANA_URL', ''),
    }