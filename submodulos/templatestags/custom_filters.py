from django import template
from datetime import datetime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Accede a elementos de un diccionario por clave"""
    if dictionary is None:
        return None
    return dictionary.get(key, None)

@register.filter
def startswith(text, prefix):
    """Comprueba si un texto comienza con un prefijo determinado"""
    if text is None:
        return False
    return text.startswith(prefix)

@register.filter
def timestamp_to_datetime(timestamp):
    """Convierte un timestamp Unix en un objeto datetime"""
    if timestamp is None:
        return ""
    try:
        return datetime.fromtimestamp(float(timestamp))
    except:
        return ""