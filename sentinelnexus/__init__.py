from .celery import app as celery_app

__all__ = ('celery_app',)

# ======================================================
# 💉 PARCHE DE COMPATIBILIDAD POSTGRESQL ("Monkey Patch")
# ======================================================
# Django 4.2.27 en features.py exige PostgreSQL 14+, pero
# nuestro servidor de producción corre 13.x.
# Esto sobreescribe la validación al iniciar la app.
try:
    from django.db.backends.postgresql.features import DatabaseFeatures
    DatabaseFeatures.minimum_database_version = (12,)
except ImportError:
    pass
