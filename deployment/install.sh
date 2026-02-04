#!/bin/bash

# Script de Instalación Automática para SentinelNexus (Server)
# Debe ejecutarse como ROOT

# 1. Detectar directorio actual
PROJECT_DIR=$(pwd)
echo "📂 Directorio del proyecto detectado: $PROJECT_DIR"

# 2. Verificar entorno virtual
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "⚠️  No se detectó entorno virtual (venv). Creándolo..."
    python3 -m venv venv
    echo "✅ Entorno creado. Instalando dependencias..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "✅ Entorno virtual detectado."
fi

# 3. Configurar rutas en los servicios
echo "⚙️  Configurando servicios con la ruta local..."

# Copiar templates a archivos temporales para editar
cp deployment/cerebro.service /tmp/cerebro.service
cp deployment/sentinel_web.service /tmp/sentinel_web.service

# Reemplazar ruta hardcodeada /opt/sentinelnexus por la real
sed -i "s|/opt/sentinelnexus|$PROJECT_DIR|g" /tmp/cerebro.service
sed -i "s|/opt/sentinelnexus|$PROJECT_DIR|g" /tmp/sentinel_web.service

# 4. Instalar servicios en Systemd
echo "🚀 Instalando servicios en /etc/systemd/system/..."
cp /tmp/cerebro.service /etc/systemd/system/cerebro.service
cp /tmp/sentinel_web.service /etc/systemd/system/sentinel_web.service

# 5. Recargar y Activar
systemctl daemon-reload
echo "🔄 Demonios recargados."

systemctl enable cerebro
systemctl restart cerebro
echo "🧠 Agente CEREBRO: Activado y Corriendo."

systemctl enable sentinel_web
systemctl restart sentinel_web
echo "🌐 Servidor WEB: Activado y Corriendo."

echo "---------------------------------------------------"
echo "✅ DEPLIEGUE FINALIZADO EXITOSAMENTE"
echo "   Puede verificar el estado con: systemctl status cerebro"
echo "---------------------------------------------------"
