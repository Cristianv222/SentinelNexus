from django.contrib import admin
from django.views.generic.base import RedirectView, TemplateView
from django.urls import path, re_path, include
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    # Página principal redirige al dashboard
    path('', RedirectView.as_view(url='/dashboard/', permanent=False), name='home'),
    
    # URLs de administración
    path('admin/', admin.site.urls),
    
    # URLs de autenticación
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(template_name='registration/logged_out.html'), name='logout'),
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Rutas de la aplicación
    path('servers/', views.server_list, name='server_list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('nodes/<str:node_name>/', views.node_detail, name='node_detail'),
    path('vms/<str:node_name>/<int:vmid>/', views.vm_detail, name='vm_detail'),
    path('vms/<str:node_name>/<int:vmid>/<str:vm_type>/', views.vm_detail, name='vm_detail_with_type'),
    path('vms/<str:node_name>/<int:vmid>/<str:action>/', views.vm_action, name='vm_action'),
    path('vms/<str:node_name>/<int:vmid>/<str:vm_type>/<str:action>/', views.vm_action, name='vm_action_with_type'),
    
    # API endpoints
    path('api/nodes/', views.api_get_nodes, name='api_nodes'),
    path('api/vms/', views.api_get_vms, name='api_vms'),
    path('api/vms/<str:node_name>/<int:vmid>/status/', views.api_vm_status, name='api_vm_status'),
    
    # Nuevas APIs para gráficas de métricas
    path('api/vms/<str:node_name>/<int:vmid>/metrics/', views.api_vm_metrics, name='api_vm_metrics'),
    path('api/dashboard/metrics/', views.api_dashboard_metrics, name='api_dashboard_metrics'),

    # En sentinelnexus/urls.py añade estas líneas a urlpatterns:
    path('metrics/', views.metrics_dashboard, name='metrics_dashboard'),
    path('grafana/', views.grafana_dashboard, name='grafana_dashboard'),
    path('api/metrics/', views.api_metrics, name='api_metrics'),
    path('sync-proxmox/', views.sync_proxmox, name='sync_proxmox'),
    path('vm/<str:node_name>/<int:vmid>/<str:vm_type>/console/', views.vm_console, name='vm_console'),




    path('grafana/', views.grafana_dashboard, name='grafana_dashboard'),
    
    # Proxy para Grafana (path vacío)
    path('grafana-proxy/', views.grafana_proxy, name='grafana_proxy_base'),
    
    # Proxy para Grafana (con path)
    path('grafana-proxy/<path:path>', views.grafana_proxy, name='grafana_proxy'),
    # En sentinelnexus/urls.py
    path('test-grafana/', views.test_grafana_connection, name='test_grafana'),
]