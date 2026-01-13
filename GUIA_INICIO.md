# Guía de Inicio Rápido - SentinelNexus

Este documento resume los pasos necesarios para iniciar el entorno de desarrollo del proyecto.

## 1. Arquitectura de Conexión

El sistema funciona conectando tres puntos clave:

1.  **Tu PC Local**: Donde corre Django (el código de la aplicación).
2.  **Base de Datos (10.100.100.245)**: Donde se guardan los usuarios y configuraciones.
3.  **Servidores Proxmox**: La infraestructura que monitoreamos.

**IMPORTANTE**: Dado que la Base de Datos está en un servidor remoto y tu configuración local espera encontrarla en `localhost:9999`, es **OBLIGATORIO** establecer un Túnel SSH.

## 2. Prerrequisitos

- Python 3.10+ instalado.
- Acceso SSH al servidor `10.100.100.245` (o donde esté alojada la BDD).
- Entorno virtual configurado (carpeta `venv`).

## 3. Pasos para Iniciar (Cada vez que trabajes)

### Paso 1: Abrir el Túnel SSH (Terminal 1)

Este comando "engaña" a tu PC local para que crea que la base de datos remota está en tu propia máquina en el puerto 9999.

```powershell
# Ejecuta esto en una terminal y DÉJALO CORRIENDO (no lo cierres)
ssh -L 9999:localhost:5432 usuario@10.100.100.245
```

_(Reemplaza `usuario` por tu usuario SSH real del servidor)_.

### Paso 2: Activar Entorno Virtual (Terminal 2)

```powershell
# En la carpeta del proyecto
.\venv\Scripts\activate
```

### Paso 3: Iniciar Servidor Django (Terminal 2)

```powershell
python manage.py runserver
```

## 4. Diagnóstico de Problemas Comunes

- **Error "Connection refused" o fallos de BDD**: Verifica que el Túnel SSH del Paso 1 siga abierto.
- **Proxmox Offline**: Verifica que tienes VPN o estás en la red `172.20.x.x` o `10.100.x.x` que te permite ver los servidores Proxmox.
  - Puedes probar conexión con: `ping 172.20.24.30`
