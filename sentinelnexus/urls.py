from django.contrib import admin
from django.views.generic.base import RedirectView, TemplateView
from django.urls import path, re_path, include
from django.contrib.auth.views import LoginView, LogoutView
from . import views



urlpatterns = [
    # Página principal redirige al dashboard de nodos
    path('', RedirectView.as_view(url='/nodes/', permanent=False), name='home'),
    
    # URLs de administración
    path('admin/', admin.site.urls),
    
    # URLs de autenticación
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # ========== RUTAS PRINCIPALES PARA MÚLTIPLES NODOS ==========
    
    # Dashboard principal de nodos - USA: dashboard/nodes_overview.html
    path('nodes/', views.nodes_overview, name='nodes_overview'),
    
    # Vista detallada de un nodo específico - USA: dashboard/node_detail_new.html
    path('nodes/<str:node_key>/', views.node_detail_new, name='node_detail_new'),
    
    # Vista detallada de VM con nodo específico - USA: dashboard/vm_detail_new.html
    path('nodes/<str:node_key>/vms/<str:node_name>/<int:vmid>/type/<str:vm_type>/', 
         views.vm_detail_new, name='vm_detail_new'),
    
    # Acciones de VMs con nodo específico
    path('nodes/<str:node_key>/vms/<str:node_name>/<int:vmid>/type/<str:vm_type>/action/<str:action>/', 
         views.vm_action_new, name='vm_action_new'),
    
    # Crear nueva VM
    path('nodes/<str:node_key>/vms/<str:node_name>/create/', 
         views.vm_create, name='vm_create'),
    
    # ========== DASHBOARD PRINCIPAL ==========
    
    # Dashboard principal (main) - USA: main_dashboard.html
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Dashboard de Agentes (Live Console)
    path('dashboard/agents/', views.agent_dashboard, name='agent_dashboard'),
    path('dashboard/agents/logs/', views.agent_logs_partial, name='agent_logs_partial'),
    path('nodes/<str:node_name>/vms/<int:vmid>/toggle-watchdog/', views.toggle_vm_watchdog, name='toggle_vm_watchdog'),
    
    # Dashboard de métricas - USA: metrics_dashboard.html
    path('metrics/', views.metrics_dashboard, name='metrics_dashboard'),

    # Dashboard de datos - USA: data_dashboard.html
    path('data/', views.data_dashboard, name='data_dashboard'),
    path('data/export/', views.export_data_csv, name='export_data_csv'),
    
    # ========== RUTAS LEGACY (COMPATIBILIDAD) ==========
    
    # Sincronización con Proxmox
    path('sync-proxmox/', views.sync_proxmox, name='sync_proxmox'),
    
    # Rutas para detalles de VM (sin acciones) - LEGACY
    path('vms/<str:node_name>/<int:vmid>/', views.vm_detail, name='vm_detail'),
    path('vms/<str:node_name>/<int:vmid>/type/<str:vm_type>/', views.vm_detail, name='vm_detail_with_type'),
    
    # Rutas para acciones de VM - LEGACY
    path('vms/<str:node_name>/<int:vmid>/action/<str:action>/', views.vm_action, name='vm_action'),
    path('vms/<str:node_name>/<int:vmid>/type/<str:vm_type>/action/<str:action>/', views.vm_action, name='vm_action_with_type'),
    
    # Consola de VM - LEGACY
    path('vms/<str:node_name>/<int:vmid>/type/<str:vm_type>/console/', views.vm_console, name='vm_console'),
    
    # Node details - LEGACY
    path('nodes-legacy/<str:node_name>/', views.node_detail, name='node_detail'),
    
    # Server list
    path('servers/', views.server_list, name='server_list'),
    
    # ========== API ENDPOINTS ==========
    
    # APIs Legacy
    path('api/nodes/', views.api_get_nodes, name='api_nodes'),
    path('api/vms/', views.api_get_vms, name='api_vms'),
    path('api/vms/<str:node_name>/<int:vmid>/status/', views.api_vm_status, name='api_vm_status'),
    path('api/vms/<str:node_name>/<int:vmid>/metrics/', views.api_vm_metrics, name='api_vm_metrics'),
    path('api/dashboard/metrics/', views.api_dashboard_metrics, name='api_dashboard_metrics'),
    path('api/metrics/', views.api_metrics, name='api_metrics'),
    
    # APIs para múltiples nodos
    path('api/nodes-multi/', views.api_get_nodes_multi, name='api_nodes_multi'),
    path('api/nodes/<str:node_key>/vms/', views.api_get_vms_by_node, name='api_vms_by_node'),
    path('api/nodes/<str:node_key>/status/', views.api_node_status, name='api_node_status'),
    path('api/nodes/<str:node_key>/vms/<str:node_name>/<int:vmid>/status/', views.api_vm_status_new, name='api_vm_status_new'),
    path('api/nodes/<str:node_key>/vms/<str:node_name>/<int:vmid>/metrics/', views.api_vm_metrics_new, name='api_vm_metrics_new'),

    # APIs de métricas
    path('api/metrics/', views.api_metrics, name='api_metrics'),
    path('api/metrics/realtime/', views.api_metrics_realtime, name='api_metrics_realtime'),
    path('api/servers/metrics/', views.api_servers_metrics, name='api_servers_metrics'),
    
    # Vista de métricas
    path('metrics/', views.metrics_dashboard, name='metrics'),
    path('predictions/', views.predictions_dashboard, name='predictions_dashboard'),
    path('api/predictions/<int:server_id>/', views.get_metrics_predictions, name='metrics_predictions'),
    path('api/server/<int:server_id>/vms/', views.get_server_vms, name='server_vms'),

    path('api/vms/metrics/', views.vms_metrics_api, name='vms_metrics_api'),
    
]