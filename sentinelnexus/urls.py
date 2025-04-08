from django.contrib import admin
from django.views.generic.base import RedirectView, TemplateView
from django.urls import path, include
from . import views

urlpatterns = [
    # Página principal que renderiza base.html
    path('', TemplateView.as_view(template_name='base.html'), name='home'),
    
    # URLs de administración
    path('admin/', admin.site.urls),
    
    # URLs de autenticación
    path('accounts/', include('django.contrib.auth.urls')),
     path('servers/', views.server_list, name='server_list'),
    
    # Dashboard y otras URLs
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
]