
import os
import django
from datetime import timedelta
from django.utils import timezone
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import VMMetric, ServerMetric, ServerPrediction

def check_metrics():
    print(f"Checking database for recent metrics... (Current Time: {timezone.now()})")
    
    # Check Server Metrics
    recent_servers = ServerMetric.objects.order_by('-timestamp')[:5]
    print(f"\nLast 5 Server Metrics:")
    for m in recent_servers:
        print(f"[{m.timestamp}] Server ID: {m.server_id} - CPU: {m.cpu_usage}% RAM: {m.ram_usage}%")
        
    # Check VM Metrics
    recent_vms = VMMetric.objects.order_by('-timestamp')[:5]
    print(f"\nLast 5 VM Metrics:")
    for m in recent_vms:
        # Use vm_name as discovered in fix
        print(f"[{m.timestamp}] VM: {m.vm_name} - CPU: {m.cpu_usage}% RAM: {m.ram_usage}%")

    # Check Predictions
    print(f"\nLast 5 Server Predictions:")
    try:
        recent_preds = ServerPrediction.objects.order_by('-timestamp')[:5]
        for p in recent_preds:
            print(f"[{p.timestamp}] Server: {p.server.name} - Pred CPU: {p.predicted_cpu_usage}%")
    except Exception as e:
        print(f"Could not read predictions: {e}")

if __name__ == "__main__":
    check_metrics()
