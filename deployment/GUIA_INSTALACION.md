# Guía de Despliegue en Servidor Linux (Producción)

Sigue estos pasos para instalar SentinelNexus y el Agente Cerebro en tu servidor definitivo para que funcionen 24/7.

## 1. Preparar el Código en el Servidor
Accede a tu servidor por SSH y ubícate donde quieras instalarlo (ej: `/opt/sentinelnexus`).

```bash
cd /opt
# Clonar tu repo (si no lo has hecho)
git clone https://github.com/Cristianv222/SentinelNexus.git sentinelnexus
cd sentinelnexus

# O si ya existe, actualiza los cambios recientes:
git pull origin main
```

## 2. Preparar el Entorno Virtual
Asegúrate de tener Python y las dependencias.

```bash
# Instalar venv si no lo tienes
apt update && apt install python3-venv -y

# Crear y activar entorno
python3 -m venv venv
source venv/bin/activate

# Instalar requisitos
pip install -r requirements.txt
pip install gunicorn  # Necesario para el servidor web robusto
```

## 3. Configurar los Servicios (Auto-Arranque)
Vamos a instalar los "demonios" para que si el servidor se reinicia, todo arranque solo.

### Editar Rutas
Revisa los archivos `deployment/cerebro.service` y `deployment/sentinel_web.service`.
Asegúrate de que las rutas coincidan con donde instalaste tu proyecto.
Por defecto asumen `/opt/sentinelnexus`. Si usas otra ruta, edítalos con `nano`.

### Copiar y Activar
```bash
# Copiar archivos al sistema
cp deployment/cerebro.service /etc/systemd/system/
cp deployment/sentinel_web.service /etc/systemd/system/

# Recargar el gestor de servicios
systemctl daemon-reload

# Habilitar para que inicien al arranque
systemctl enable cerebro.service
systemctl enable sentinel_web.service

# Iniciar ahora mismo
systemctl start cerebro.service
systemctl start sentinel_web.service
```

## 4. Verificar Estado
```bash
systemctl status cerebro.service
systemctl status sentinel_web.service
```
Si ves puntos verdes (active/running), ¡Felicidades! Tu sistema Watchdog es ahora inmortal.
