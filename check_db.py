
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import ServerMetric, VMMetric, ServerPrediction, VMPrediction, ProxmoxServer

print("--- Database Check ---")
print(f"Total Server Metrics: {ServerMetric.objects.count()}")
print(f"Total VM Metrics: {VMMetric.objects.count()}")
print(f"Total Server Predictions: {ServerPrediction.objects.count()}")
print(f"Total VM Predictions: {VMPrediction.objects.count()}")

last_server_metric = ServerMetric.objects.order_by('-timestamp').first()
if last_server_metric:
    print(f"Last Server Metric: {last_server_metric.timestamp}")
else:
    print("No Server Metrics found.")

last_vm_metric = VMMetric.objects.order_by('-timestamp').first()
if last_vm_metric:
    print(f"Last VM Metric: {last_vm_metric.timestamp}")
else:
    print("No VM Metrics found.")
    
active_servers = ProxmoxServer.objects.filter(is_active=True).count()
print(f"Active Servers: {active_servers}")
