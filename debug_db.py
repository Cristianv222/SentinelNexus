
import os
import django
from django.db import connection

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sentinelnexus.settings')
django.setup()

print("Inspecting Tables...")
with connection.cursor() as cursor:
    try:
        # Manual fix for VMMetric
        print("Renaming created_at to timestamp on submodulos_vmmetric...")
        cursor.execute("ALTER TABLE submodulos_vmmetric RENAME COLUMN created_at TO timestamp")
        print("Done.")
        
        # Verify
        cursor.execute("SELECT * FROM submodulos_vmmetric LIMIT 1")
        desc = cursor.description
        cols = [col[0] for col in desc]
        print(f"New Columns: {cols}")
        
    except Exception as e:
        print(f"Error listing tables: {e}")
