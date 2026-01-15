
# ==========================================
# AGENT DASHBOARD VIEWS
# ==========================================

@login_required
def agent_dashboard(request):
    """
    Dashboard principal de Agentes (Live Console).
    """
    # Últimos 50 logs para carga inicial
    logs = AgentLog.objects.all().order_by('-timestamp')[:50]
    return render(request, 'dashboard/agent_console.html', {'logs': logs})

@login_required
def agent_logs_partial(request):
    """
    Vista parcial para HTMX polling.
    Retorna solo las filas de la tabla con los logs más recientes.
    """
    # Últimos 20 logs para refresco rápido
    logs = AgentLog.objects.all().order_by('-timestamp')[:20]
    return render(request, 'dashboard/partials/agent_log_rows.html', {'logs': logs})
