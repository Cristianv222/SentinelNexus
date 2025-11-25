# 📁 Estructura del Proyecto SentinelNexus

**Generado automáticamente el:** 2025-09-10 17:01:45

## 📊 Resumen del Proyecto

- **Total de archivos:** 46
- **Total de directorios:** 7
- **Archivos Python:** 26
- **Archivos HTML:** 15
- **Archivos CSS:** 0
- **Archivos JavaScript:** 0
- **Total de líneas de código:** 11,383

### 📈 Distribución por tipo de archivo:
- **.py:** 26 archivos
- **.html:** 15 archivos
- **(sin extensión):** 4 archivos
- **.txt:** 1 archivo


## 🌳 Estructura de Directorios y Archivos

```
📁 **SentinelNexus**
├── 📁 **sentinelnexus/**
│   ├── 📄 `__init__.py` - 📂 Paquete Python `(*0 B*)`
│   ├── 📄 `asgi.py` - 🐍 Script Python `(*419 B*, *16 líneas*)`
│   ├── 📄 `celery.py` - 🐍 Script Python `(*537 B*, *18 líneas*)`
│   ├── 📄 `context_processors.py` - 🐍 Script Python `(*350 B*, *11 líneas*)`
│   ├── 📄 `settings.py` - ⚙️ Configuración principal de Django `(*9.1 KB*, *252 líneas*)`
│   ├── 📄 `urls.py` - 🌐 Configuración de URLs `(*4.2 KB*, *85 líneas*)`
│   ├── 📄 `views.py` - 👁️ Vistas de la aplicación `(*143.8 KB*, *3283 líneas*)`
│   └── 📄 `wsgi.py` - 🐍 Script Python `(*419 B*, *16 líneas*)`
├── 📁 **submodulos/**
│   ├── 📁 **templates/**
│   │   ├── 📁 **dashboard/**
│   │   │   ├── 📄 `node_detail_new.html` - 🌐 Plantilla HTML `(*29.9 KB*, *974 líneas*)`
│   │   │   ├── 📄 `nodes_overview.html` - 🌐 Plantilla HTML `(*20.2 KB*, *696 líneas*)`
│   │   │   └── 📄 `vm_detail_new.html` - 🌐 Plantilla HTML `(*31.9 KB*, *993 líneas*)`
│   │   ├── 📁 **registration/**
│   │   │   ├── 📄 `logged_out.html` - 🌐 Plantilla HTML `(*810 B*, *23 líneas*)`
│   │   │   ├── 📄 `login.html` - 🌐 Plantilla HTML `(*41.7 KB*, *1517 líneas*)`
│   │   │   ├── 📄 `password_reset_complete.html` - 🌐 Plantilla HTML `(*0 B*)`
│   │   │   ├── 📄 `password_reset_confirm.html` - 🌐 Plantilla HTML `(*0 B*)`
│   │   │   ├── 📄 `password_reset_done.html` - 🌐 Plantilla HTML `(*0 B*)`
│   │   │   └── 📄 `password_reset_form.html` - 🌐 Plantilla HTML `(*0 B*)`
│   │   ├── 📄 `add_server.html` - 🌐 Plantilla HTML `(*2.7 KB*, *59 líneas*)`
│   │   ├── 📄 `base.html` - 🌐 Plantilla HTML `(*16.0 KB*, *436 líneas*)`
│   │   ├── 📄 `main_dashboard.html` - 🌐 Plantilla HTML `(*22.0 KB*, *671 líneas*)`
│   │   ├── 📄 `server_detail_new.html` - 🌐 Plantilla HTML `(*3.0 KB*, *77 líneas*)`
│   │   ├── 📄 `server_list.html` - 🌐 Plantilla HTML `(*2.7 KB*, *61 líneas*)`
│   │   └── 📄 `vm_console.html` - 🌐 Plantilla HTML `(*7.7 KB*, *243 líneas*)`
│   ├── 📁 **templatestags/**
│   │   ├── 📄 `__init__.py` - 📂 Paquete Python `(*0 B*)`
│   │   └── 📄 `custom_filters.py` - 🐍 Script Python `(*753 B*, *28 líneas*)`
│   ├── 📄 `__init__.py` - 📂 Paquete Python `(*0 B*)`
│   ├── 📄 `admin.py` - 👤 Configuración del panel de administración `(*66 B*, *3 líneas*)`
│   ├── 📄 `apps.py` - 📱 Configuración de la aplicación `(*158 B*, *6 líneas*)`
│   ├── 📄 `models.py` - 🗄️ Modelos de base de datos `(*17.2 KB*, *440 líneas*)`
│   ├── 📄 `proxmox_service.py` - 🐍 Script Python `(*4.7 KB*, *134 líneas*)`
│   ├── 📄 `sync_proxmox.py` - 🐍 Script Python `(*15.9 KB*, *379 líneas*)`
│   ├── 📄 `tasks.py` - 🐍 Script Python `(*4.1 KB*, *101 líneas*)`
│   └── 📄 `tests.py` - 🧪 Tests unitarios `(*63 B*, *3 líneas*)`
├── 📁 **utils/**
│   ├── 📄 `__init__.py` - 📂 Paquete Python `(*388 B*, *15 líneas*)`
│   └── 📄 `proxmox_manager.py` - 🐍 Script Python `(*6.3 KB*, *171 líneas*)`
├── 📄 `.gitignore` `(*843 B*)`
├── 📄 `celerybeat-schedule` `(*4.0 KB*)`
├── 📄 `celerybeat-schedule-shm` `(*32.0 KB*)`
├── 📄 `celerybeat-schedule-wal` `(*494.9 KB*)`
├── 📄 `crear_nodo_prx2.py` - 🐍 Script Python `(*1.5 KB*, *56 líneas*)`
├── 📄 `detectar_so.py` - 🐍 Script Python `(*2.3 KB*, *64 líneas*)`
├── 📄 `documenter.py` - 🐍 Script Python `(*12.5 KB*, *333 líneas*)`
├── 📄 `generate_key.py` - 🐍 Script Python `(*464 B*, *12 líneas*)`
├── 📄 `manage.py` - 🔧 Script de administración de Django `(*691 B*, *22 líneas*)`
├── 📄 `requirements.txt` - 📦 Dependencias de Python `(*1.9 KB*, *99 líneas*)`
└── 📄 `test.py` - 🐍 Script Python `(*3.3 KB*, *86 líneas*)`
```

## 📝 Notas

- Los archivos de configuración sensibles (`.env`) están excluidos por seguridad
- Los directorios `__pycache__`, `venv`, `.git` y similares están excluidos
- Los archivos de migraciones de Django están excluidos por defecto
- Solo se muestran archivos menores a 1MB

---

*Documentación generada automáticamente por `documenter.py`*
