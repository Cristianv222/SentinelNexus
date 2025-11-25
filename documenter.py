#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Documentador de estructura del proyecto SentinelNexus
Genera un archivo con la estructura completa del proyecto
"""

import os
import datetime
from pathlib import Path

class ProjectDocumenter:
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.output_file = self.project_root / "PROJECT_STRUCTURE.md"
        
        # Directorios y archivos a excluir
        self.exclude_dirs = {
            '__pycache__', 
            '.git', 
            'node_modules', 
            'venv', 
            'env', 
            '.vscode', 
            '.idea',
            'migrations',  # Excluir migraciones por defecto
            'static',      # Excluir archivos estáticos compilados
            'media'        # Excluir archivos de media
        }
        
        self.exclude_files = {
            '.pyc', 
            '.pyo', 
            '.pyd', 
            '.db', 
            '.sqlite3', 
            '.log',
            '.env',        # No incluir archivos de configuración sensible
            '.DS_Store',
            'Thumbs.db'
        }
        
        # Extensiones importantes para mostrar contenido
        self.important_extensions = {
            '.py', '.js', '.html', '.css', '.scss', '.json', 
            '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
            '.md', '.txt', '.rst', '.xml'
        }

    def should_exclude_dir(self, dir_name):
        """Verifica si un directorio debe ser excluido"""
        return dir_name in self.exclude_dirs or dir_name.startswith('.')

    def should_exclude_file(self, file_name, file_path):
        """Verifica si un archivo debe ser excluido"""
        # Excluir por extensión
        if any(file_name.endswith(ext) for ext in self.exclude_files):
            return True
        
        # Excluir archivos muy grandes (>1MB)
        try:
            if file_path.stat().st_size > 1024 * 1024:
                return True
        except:
            pass
            
        return False

    def get_file_info(self, file_path):
        """Obtiene información básica del archivo"""
        try:
            stat_info = file_path.stat()
            size = stat_info.st_size
            modified = datetime.datetime.fromtimestamp(stat_info.st_mtime)
            
            # Formatear tamaño
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/(1024*1024):.1f} MB"
            
            return {
                'size': size_str,
                'modified': modified.strftime('%Y-%m-%d %H:%M'),
                'lines': self.count_lines(file_path) if file_path.suffix in self.important_extensions else None
            }
        except Exception as e:
            return {'size': 'N/A', 'modified': 'N/A', 'lines': None, 'error': str(e)}

    def count_lines(self, file_path):
        """Cuenta las líneas de un archivo de texto"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except:
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return sum(1 for _ in f)
            except:
                return None

    def get_file_description(self, file_path):
        """Obtiene una breve descripción del archivo basada en su contenido"""
        if file_path.name == 'requirements.txt':
            return "📦 Dependencias de Python"
        elif file_path.name == 'manage.py':
            return "🔧 Script de administración de Django"
        elif file_path.name == 'settings.py':
            return "⚙️ Configuración principal de Django"
        elif file_path.name == 'urls.py':
            return "🌐 Configuración de URLs"
        elif file_path.name == 'models.py':
            return "🗄️ Modelos de base de datos"
        elif file_path.name == 'views.py':
            return "👁️ Vistas de la aplicación"
        elif file_path.name == 'forms.py':
            return "📝 Formularios"
        elif file_path.name == 'admin.py':
            return "👤 Configuración del panel de administración"
        elif file_path.name == 'apps.py':
            return "📱 Configuración de la aplicación"
        elif file_path.name == 'tests.py':
            return "🧪 Tests unitarios"
        elif file_path.name == '__init__.py':
            return "📂 Paquete Python"
        elif file_path.name == '.env':
            return "🔐 Variables de entorno (confidencial)"
        elif file_path.name == 'README.md':
            return "📖 Documentación del proyecto"
        elif file_path.suffix == '.html':
            return "🌐 Plantilla HTML"
        elif file_path.suffix == '.css':
            return "🎨 Estilos CSS"
        elif file_path.suffix == '.js':
            return "⚡ JavaScript"
        elif file_path.suffix == '.json':
            return "📋 Archivo de configuración JSON"
        elif file_path.suffix == '.py':
            return "🐍 Script Python"
        else:
            return ""

    def generate_tree_structure(self, start_path, prefix="", max_depth=None, current_depth=0):
        """Genera la estructura de árbol del proyecto"""
        if max_depth and current_depth >= max_depth:
            return []
        
        items = []
        try:
            # Obtener y ordenar los elementos
            entries = []
            for item in start_path.iterdir():
                if item.is_dir() and not self.should_exclude_dir(item.name):
                    entries.append((item, True))  # True para directorios
                elif item.is_file() and not self.should_exclude_file(item.name, item):
                    entries.append((item, False))  # False para archivos
            
            # Ordenar: directorios primero, luego archivos, ambos alfabéticamente
            entries.sort(key=lambda x: (not x[1], x[0].name.lower()))
            
            for i, (item, is_dir) in enumerate(entries):
                is_last = i == len(entries) - 1
                current_prefix = "└── " if is_last else "├── "
                
                if is_dir:
                    items.append(f"{prefix}{current_prefix}📁 **{item.name}/**")
                    # Recursión para subdirectorios
                    extension_prefix = prefix + ("    " if is_last else "│   ")
                    items.extend(self.generate_tree_structure(
                        item, extension_prefix, max_depth, current_depth + 1
                    ))
                else:
                    # Información del archivo
                    file_info = self.get_file_info(item)
                    description = self.get_file_description(item)
                    
                    file_line = f"{prefix}{current_prefix}📄 `{item.name}`"
                    if description:
                        file_line += f" - {description}"
                    
                    # Agregar información adicional
                    info_parts = []
                    if file_info['size'] != 'N/A':
                        info_parts.append(f"*{file_info['size']}*")
                    if file_info.get('lines'):
                        info_parts.append(f"*{file_info['lines']} líneas*")
                    
                    if info_parts:
                        file_line += f" `({', '.join(info_parts)})`"
                    
                    items.append(file_line)
        
        except PermissionError:
            items.append(f"{prefix}❌ Sin permisos de acceso")
        except Exception as e:
            items.append(f"{prefix}❌ Error: {str(e)}")
        
        return items

    def generate_summary(self):
        """Genera un resumen del proyecto"""
        summary = {
            'total_files': 0,
            'total_dirs': 0,
            'python_files': 0,
            'html_files': 0,
            'css_files': 0,
            'js_files': 0,
            'total_lines': 0,
            'file_types': {}
        }
        
        for root, dirs, files in os.walk(self.project_root):
            root_path = Path(root)
            
            # Filtrar directorios excluidos
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(d)]
            summary['total_dirs'] += len(dirs)
            
            for file in files:
                file_path = root_path / file
                if self.should_exclude_file(file, file_path):
                    continue
                
                summary['total_files'] += 1
                
                # Contar por extensión
                ext = file_path.suffix.lower()
                summary['file_types'][ext] = summary['file_types'].get(ext, 0) + 1
                
                if ext == '.py':
                    summary['python_files'] += 1
                elif ext == '.html':
                    summary['html_files'] += 1
                elif ext == '.css':
                    summary['css_files'] += 1
                elif ext == '.js':
                    summary['js_files'] += 1
                
                # Contar líneas para archivos importantes
                if ext in self.important_extensions:
                    lines = self.count_lines(file_path)
                    if lines:
                        summary['total_lines'] += lines
        
        return summary

    def generate_documentation(self):
        """Genera la documentación completa del proyecto"""
        print("🔍 Analizando estructura del proyecto...")
        
        # Generar resumen
        summary = self.generate_summary()
        
        # Generar estructura de árbol
        tree_structure = self.generate_tree_structure(self.project_root, max_depth=10)
        
        # Crear contenido del archivo
        content = f"""# 📁 Estructura del Proyecto SentinelNexus

**Generado automáticamente el:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 Resumen del Proyecto

- **Total de archivos:** {summary['total_files']}
- **Total de directorios:** {summary['total_dirs']}
- **Archivos Python:** {summary['python_files']}
- **Archivos HTML:** {summary['html_files']}
- **Archivos CSS:** {summary['css_files']}
- **Archivos JavaScript:** {summary['js_files']}
- **Total de líneas de código:** {summary['total_lines']:,}

### 📈 Distribución por tipo de archivo:
"""
        
        # Agregar distribución de tipos de archivo
        for ext, count in sorted(summary['file_types'].items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                ext_name = ext if ext else "(sin extensión)"
                content += f"- **{ext_name}:** {count} archivo{'s' if count > 1 else ''}\n"
        
        content += f"""

## 🌳 Estructura de Directorios y Archivos

```
📁 **{self.project_root.name}**
"""
        
        # Agregar estructura de árbol
        for line in tree_structure:
            content += line + "\n"
        
        content += """```

## 📝 Notas

- Los archivos de configuración sensibles (`.env`) están excluidos por seguridad
- Los directorios `__pycache__`, `venv`, `.git` y similares están excluidos
- Los archivos de migraciones de Django están excluidos por defecto
- Solo se muestran archivos menores a 1MB

---

*Documentación generada automáticamente por `documenter.py`*
"""
        
        # Guardar archivo
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Documentación generada exitosamente en: {self.output_file}")
            print(f"📊 Total de archivos documentados: {summary['total_files']}")
            print(f"📁 Total de directorios: {summary['total_dirs']}")
            
        except Exception as e:
            print(f"❌ Error al guardar la documentación: {e}")

def main():
    """Función principal"""
    print("🚀 Iniciando documentador del proyecto SentinelNexus...")
    
    documenter = ProjectDocumenter()
    documenter.generate_documentation()
    
    print("\n🎉 ¡Documentación completada!")
    print(f"📄 Revisa el archivo: {documenter.output_file}")

if __name__ == "__main__":
    main()