
import os

file_path = 'submodulos/templates/metrics.html'

try:
    with open(file_path, 'rb') as f:
        content_bytes = f.read()
    
    # Intentar decodificar ignorando/reemplazando errores
    # El error reportado fue 0xc3, que es comúnmente 'Ã' en latin-1 o inicio de utf-8
    content_str = content_bytes.decode('utf-8', errors='replace')
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content_str)
        
    print("Successfully sanitized metrics.html")
except Exception as e:
    print(f"Error sanitizing file: {e}")
