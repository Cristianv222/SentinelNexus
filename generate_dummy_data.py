
import os
import django
import random
from datetime import timedelta
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import ProxmoxServer, ServerPrediction, MaquinaVirtual, VMPrediction

print("Generating dummy predictions for visualization...")

# 1. Server Predictions
servers = ProxmoxServer.objects.filter(is_active=True)
now = timezone.now()

if not servers.exists():
    print("No servers found. Creating a dummy server...")
    # Create a dummy server if none exists so user sees something
    server = ProxmoxServer.objects.create(name="Proxmox-Primary (Demo)", hostname="192.168.1.10", node_name="pve")
    servers = [server]

for server in servers:
    print(f"Generating for server: {server.name}")
    # Clear old future predictions
    ServerPrediction.objects.filter(server=server, timestamp__gte=now).delete()
    
    predictions = []
    current_cpu = random.uniform(20, 40)
    current_ram = random.uniform(40, 60)
    
    for i in range(24):
        time_step = now + timedelta(hours=i+1)
        
        # Simulate some trend
        current_cpu += random.uniform(-5, 5)
        current_ram += random.uniform(-2, 3)
        
        # Clamping
        current_cpu = max(5, min(95, current_cpu))
        current_ram = max(10, min(90, current_ram))
        
        predictions.append(ServerPrediction(
            server=server,
            timestamp=time_step,
            predicted_cpu_usage=current_cpu,
            predicted_memory_usage=current_ram,
            confidence_lower=max(0, current_cpu - 10),
            confidence_upper=min(100, current_cpu + 10)
        ))
    
    ServerPrediction.objects.bulk_create(predictions)

# 2. VM Predictions (Anomalies)
vms = MaquinaVirtual.objects.all()[:5] # Just top 5
if not vms.exists():
    print("No VMs found. Skipping VM predictions.")
else:
    for vm in vms:
        print(f"Generating for VM: {vm.nombre}")
        VMPrediction.objects.filter(vm=vm, timestamp__gte=now).delete()
        
        predictions = []
        base_cpu = random.uniform(10, 30)
        
        for i in range(12): # 12 hours
            time_step = now + timedelta(hours=i+1)
             # Sprinkle some anomalies
            is_anomaly = random.random() < 0.1
            cpu_val = base_cpu + (random.uniform(20, 50) if is_anomaly else random.uniform(-2, 2))
            
            predictions.append(VMPrediction(
                vm=vm,
                timestamp=time_step,
                predicted_cpu_usage=max(0, min(100, cpu_val)),
                predicted_memory_usage=random.uniform(20, 40),
                is_anomaly=is_anomaly
            ))
            
        VMPrediction.objects.bulk_create(predictions)

print("Done! Predictions populated.")
