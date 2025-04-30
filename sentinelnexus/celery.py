import os
from celery import Celery

# Establecer la variable de entorno para configuraciones
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')

# Crear la instancia de la aplicación Celery
app = Celery('sentinelnexus')

# Cargar configuración desde settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descubrir tareas automáticamente
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')