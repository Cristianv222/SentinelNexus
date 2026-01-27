
import os
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import ProxmoxServer, ServerMetric
from submodulos.logic.forecasting import train_and_predict_server

print("Debugging Forecast Generation...")

servers = ProxmoxServer.objects.filter(is_active=True)
if not servers.exists():
    print("No active servers found.")
else:
    for server in servers:
        print(f"Checking server: {server.name} (ID: {server.id})")
        metrics_count = ServerMetric.objects.filter(server=server).count()
        print(f" - Metric count: {metrics_count}")
        
        try:
            print(" - Attempting prediction...")
            train_and_predict_server(server.id)
            print(" - Success!")
        except Exception:
            traceback.print_exc()
