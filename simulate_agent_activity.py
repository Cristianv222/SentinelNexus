
import os
import django
import time
import random
from datetime import datetime

# Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import AgentLog

def simulate():
    print("🚀 Iniciando simulación de actividad de agentes...")
    print("Presiona CTRL+C para detener.")
    
    agents = ["Cerebro", "Monitor-PVE1", "Monitor-PVE2", "Watchdog"]
    actions = [
        ("INFO", "Escaneo de rutina completado.", None),
        ("INFO", "Métricas de nodo recibidas.", {"cpu": 12, "ram": 45}),
        ("WARNING", "Detectado uso alto de CPU.", {"node": "PVE1", "cpu": 88}),
        ("ACTION", "Iniciando migración preventiva.", {"vm": "Web-Prod", "target": "PVE2"}),
        ("ACTION", "Limpiando caché de memoria.", {"freed": "2GB"}),
        ("CRITICAL", "Nodo PVE3 no responde al ping.", {"retries": 3}),
        ("INFO", "Balanceo de carga finalizado.", {"moved_vms": 1})
    ]

    try:
        while True:
            agent = random.choice(agents)
            level, msg, details = random.choice(actions)
            
            # Variar un poco los mensajes
            if "CPU" in msg:
                details["cpu"] = random.randint(80, 99)
            
            AgentLog.objects.create(
                agent_name=agent,
                level=level,
                message=msg,
                details=details
            )
            
            print(f"➕ Log generado: [{agent}] {msg}")
            
            # Esperar entre 1 y 3 segundos
            time.sleep(random.uniform(1.0, 3.0))
            
    except KeyboardInterrupt:
        print("\n🛑 Simulación detenida.")

if __name__ == "__main__":
    simulate()
