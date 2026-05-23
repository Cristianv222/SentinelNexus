import os
import django
from django.utils import timezone
from datetime import timedelta

# Configurar entorno de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

from submodulos.models import VMMetric, ServerMetric

def clean_database():
    limite = timezone.now() - timedelta(days=14)
    print(f"Iniciando limpieza de base de datos...")
    print(f"Buscando registros anteriores a {limite} (más de 14 días de antigüedad)...")
    
    try:
        print("Eliminando VMMetric antiguas (esto puede tardar unos minutos debido al gran volumen)...")
        total_vms, _ = VMMetric.objects.filter(timestamp__lt=limite).delete()
        print(f"[OK] Se eliminaron {total_vms} registros antiguos de VMMetric.")
    except Exception as e:
        print(f"Error eliminando VMMetrics: {e}")
        
    try:
        print("Eliminando ServerMetric antiguas...")
        total_servers, _ = ServerMetric.objects.filter(timestamp__lt=limite).delete()
        print(f"[OK] Se eliminaron {total_servers} registros antiguos de ServerMetric.")
    except Exception as e:
        print(f"Error eliminando ServerMetrics: {e}")
        
    print("¡Mantenimiento de base de datos completado exitosamente!")

if __name__ == "__main__":
    clean_database()
