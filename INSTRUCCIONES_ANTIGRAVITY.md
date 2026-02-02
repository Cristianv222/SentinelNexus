# 🤖 INSTRUCCIONES PARA ANTIGRAVITY - COMPLETAR ARTÍCULO SENTINELNEXUS

## 📋 CONTEXTO
Estás ayudando a completar un artículo académico sobre SentinelNexus, un sistema de monitoreo predictivo con arquitectura Multi-Agente y modelos SARIMA. El código fuente está en este proyecto.

---

## 🎯 TAREAS A REALIZAR

### **TAREA 1: Extraer código de forecasting.py**

**Archivo objetivo:** `submodulos/logic/forecasting.py`

**Extraer:**
1. Función de preprocesamiento de series temporales
2. Función de selección de parámetros SARIMA (grid search o auto_arima)
3. Función de entrenamiento del modelo
4. Función de generación de predicciones
5. Función de evaluación de métricas (RMSE, MAE, MAPE, R²)

**Formato de salida:**
```python
# CÓDIGO EXTRAÍDO PARA ARTÍCULO - forecasting.py

def preprocess_time_series(df, column='cpu_usage'):
    """
    Preprocesamiento de series temporales para SARIMA.
    
    Args:
        df: DataFrame con columnas ['timestamp', 'cpu_usage', 'ram_usage']
        column: Métrica a procesar
    
    Returns:
        Serie temporal limpia y estacionaria
    """
    # TU CÓDIGO AQUÍ
    pass

def select_sarima_params(series, seasonal_period=24):
    """
    Selección automática de parámetros (p,d,q)(P,D,Q)s
    usando criterio AIC.
    """
    # TU CÓDIGO AQUÍ
    pass

def train_sarima_model(series, order=(1,1,1), seasonal_order=(1,1,1,24)):
    """
    Entrenamiento del modelo SARIMA.
    """
    # TU CÓDIGO AQUÍ
    pass

def generate_forecast(model, steps=24):
    """
    Genera pronóstico con intervalo de confianza.
    """
    # TU CÓDIGO AQUÍ
    pass

def evaluate_model(y_true, y_pred):
    """
    Calcula métricas de error: RMSE, MAE, MAPE, R².
    """
    # TU CÓDIGO AQUÍ
    pass
```

---

### **TAREA 2: Generar datos para resultados experimentales**

**Archivo objetivo:** `submodulos/management/commands/export_predictions.py` o base de datos

**Extraer:**
1. Últimos 30 días de métricas de CPU/RAM de al menos 2 VMs críticas
2. Predicciones generadas por el modelo SARIMA
3. Calcular métricas de error reales

**Formato de salida (CSV):**
```csv
timestamp,actual_cpu,predicted_cpu,actual_ram,predicted_ram,vm_name
2024-01-01 00:00:00,45.2,43.8,68.3,67.1,VM-MOODLE
2024-01-01 01:00:00,42.1,44.2,66.8,68.5,VM-MOODLE
...
```

**Calcular:**
```python
# Métricas por horizonte temporal
horizontes = [1, 6, 24]  # horas

for h in horizontes:
    rmse = calcular_rmse(actual, predicted, h)
    mae = calcular_mae(actual, predicted, h)
    mape = calcular_mape(actual, predicted, h)
    r2 = calcular_r2(actual, predicted, h)
    
    print(f"Horizonte {h}h: RMSE={rmse:.2f}, MAE={mae:.2f}, MAPE={mape:.2f}%, R²={r2:.3f}")
```

---

### **TAREA 3: Crear gráficas para el artículo**

Generar las siguientes visualizaciones y guardar en `image/`:

#### **Gráfica 1: Predicción vs Real (7 días)**
```python
import matplotlib.pyplot as plt
import pandas as pd

# Cargar datos de los últimos 7 días
df = pd.read_csv('datos_prediccion.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])

plt.figure(figsize=(12, 5))
plt.plot(df['timestamp'], df['actual_cpu'], label='Real', color='blue', linewidth=1.5)
plt.plot(df['timestamp'], df['predicted_cpu'], label='SARIMA Predicción', color='red', linewidth=1.5, linestyle='--')
plt.fill_between(df['timestamp'], df['lower_bound'], df['upper_bound'], alpha=0.2, color='red', label='IC 95%')
plt.xlabel('Tiempo')
plt.ylabel('Uso CPU (%)')
plt.title('Predicción SARIMA vs. Valores Reales - VM-MOODLE')
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('image/prediccion_vs_real.png', dpi=300)
plt.close()
```

#### **Gráfica 2: ACF y PACF**
```python
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
plot_acf(series_estacionaria, lags=48, ax=axes[0])
axes[0].set_title('Función de Autocorrelación (ACF)')
plot_pacf(series_estacionaria, lags=48, ax=axes[1])
axes[1].set_title('Función de Autocorrelación Parcial (PACF)')
plt.tight_layout()
plt.savefig('image/acf_pacf.png', dpi=300)
plt.close()
```

#### **Gráfica 3: Análisis de Residuos**
```python
residuos = model.resid

fig, axes = plt.subplots(2, 2, figsize=(12, 8))

# Residuos en el tiempo
axes[0, 0].plot(residuos)
axes[0, 0].set_title('Residuos del Modelo SARIMA')
axes[0, 0].set_xlabel('Tiempo')

# Histograma
axes[0, 1].hist(residuos, bins=30, edgecolor='black')
axes[0, 1].set_title('Distribución de Residuos')

# Q-Q plot
from scipy import stats
stats.probplot(residuos, dist="norm", plot=axes[1, 0])
axes[1, 0].set_title('Q-Q Plot')

# ACF de residuos
plot_acf(residuos, lags=40, ax=axes[1, 1])
axes[1, 1].set_title('ACF de Residuos')

plt.tight_layout()
plt.savefig('image/analisis_residuos.png', dpi=300)
plt.close()
```

#### **Gráfica 4: Comparativa de Métricas por Horizonte**
```python
horizontes = [1, 6, 12, 24]
rmse_values = [...]  # Tus valores reales
mae_values = [...]
mape_values = [...]

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

axes[0].plot(horizontes, rmse_values, marker='o', linewidth=2)
axes[0].set_title('RMSE por Horizonte Temporal')
axes[0].set_xlabel('Horizonte (horas)')
axes[0].set_ylabel('RMSE')
axes[0].grid(True, alpha=0.3)

axes[1].plot(horizontes, mae_values, marker='s', linewidth=2, color='orange')
axes[1].set_title('MAE por Horizonte Temporal')
axes[1].set_xlabel('Horizonte (horas)')
axes[1].set_ylabel('MAE')
axes[1].grid(True, alpha=0.3)

axes[2].plot(horizontes, mape_values, marker='^', linewidth=2, color='green')
axes[2].set_title('MAPE por Horizonte Temporal')
axes[2].set_xlabel('Horizonte (horas)')
axes[2].set_ylabel('MAPE (%)')
axes[2].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('image/metricas_horizonte.png', dpi=300)
plt.close()
```

---

### **TAREA 4: Generar tablas de datos para LaTeX**

#### **Tabla 1: Resultados de Grid Search para parámetros SARIMA**
```python
# Extraer resultados del grid search (si lo hiciste)
resultados_grid = [
    {"p": 0, "d": 1, "q": 1, "P": 1, "D": 1, "Q": 1, "s": 24, "AIC": 1523.4},
    {"p": 1, "d": 1, "q": 0, "P": 1, "D": 1, "Q": 1, "s": 24, "AIC": 1518.7},
    {"p": 1, "d": 1, "q": 1, "P": 1, "D": 1, "Q": 1, "s": 24, "AIC": 1512.3},  # ← MEJOR
    {"p": 2, "d": 1, "q": 1, "P": 1, "D": 1, "Q": 1, "s": 24, "AIC": 1515.8},
]

# Generar código LaTeX
print("\\begin{table}[h]")
print("\\centering")
print("\\caption{Selección de Parámetros SARIMA mediante Criterio AIC}")
print("\\begin{tabular}{|c|c|c|c|c|c|c|c|}")
print("\\hline")
print("p & d & q & P & D & Q & s & AIC \\\\ \\hline")
for r in resultados_grid:
    print(f"{r['p']} & {r['d']} & {r['q']} & {r['P']} & {r['D']} & {r['Q']} & {r['s']} & {r['AIC']:.1f} \\\\ \\hline")
print("\\end{tabular}")
print("\\end{table}")
```

#### **Tabla 2: Métricas de Precisión Detalladas**
```python
metricas = {
    "1h": {"RMSE": 2.34, "MAE": 1.87, "MAPE": 4.2, "R2": 0.92},
    "6h": {"RMSE": 4.12, "MAE": 3.45, "MAPE": 7.8, "R2": 0.87},
    "24h": {"RMSE": 6.89, "MAE": 5.67, "MAPE": 12.3, "R2": 0.85},
}

print("\\begin{table}[h]")
print("\\centering")
print("\\caption{Métricas de Error del Modelo SARIMA por Horizonte Temporal}")
print("\\label{tab:metricas-sarima}")
print("\\begin{tabular}{|l|c|c|c|c|}")
print("\\hline")
print("\\textbf{Horizonte} & \\textbf{RMSE} & \\textbf{MAE} & \\textbf{MAPE (\\%)} & \\textbf{R²} \\\\ \\hline")
for horizonte, m in metricas.items():
    print(f"{horizonte} & {m['RMSE']:.2f} & {m['MAE']:.2f} & {m['MAPE']:.1f} & {m['R2']:.3f} \\\\ \\hline")
print("\\end{tabular}")
print("\\end{table}")
```

---

### **TAREA 5: Documentar el pipeline completo**

Crear un diagrama de flujo del proceso de predicción:

```python
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

fig, ax = plt.subplots(figsize=(10, 8))
ax.set_xlim(0, 10)
ax.set_ylim(0, 10)
ax.axis('off')

# Definir cajas del flujo
boxes = [
    {"text": "1. Recolección\nAgente Monitor\n(cada 15s)", "pos": (5, 9), "color": "#E3F2FD"},
    {"text": "2. Almacenamiento\nPostgreSQL\nTimeSeries", "pos": (5, 7.5), "color": "#E8F5E9"},
    {"text": "3. Preprocesamiento\n- Limpieza\n- Outliers\n- Normalización", "pos": (5, 6), "color": "#FFF9C4"},
    {"text": "4. Selección Parámetros\nAuto ARIMA\nAIC mínimo", "pos": (5, 4.5), "color": "#FFE0B2"},
    {"text": "5. Entrenamiento\nSARIMA(1,1,1)(1,1,1)₂₄", "pos": (5, 3), "color": "#F3E5F5"},
    {"text": "6. Predicción\nHorizonte 1-24h\nIC 95%", "pos": (5, 1.5), "color": "#FFEBEE"},
]

for box in boxes:
    fancy_box = FancyBboxPatch(
        (box["pos"][0] - 1.5, box["pos"][1] - 0.4), 3, 0.8,
        boxstyle="round,pad=0.1", edgecolor='black', facecolor=box["color"], linewidth=2
    )
    ax.add_patch(fancy_box)
    ax.text(box["pos"][0], box["pos"][1], box["text"], 
            ha='center', va='center', fontsize=9, weight='bold')

# Flechas
for i in range(len(boxes) - 1):
    arrow = FancyArrowPatch(
        (boxes[i]["pos"][0], boxes[i]["pos"][1] - 0.5),
        (boxes[i+1]["pos"][0], boxes[i+1]["pos"][1] + 0.5),
        arrowstyle='->', mutation_scale=20, linewidth=2, color='black'
    )
    ax.add_patch(arrow)

plt.title("Pipeline de Predicción SARIMA - SentinelNexus", fontsize=14, weight='bold')
plt.tight_layout()
plt.savefig('image/pipeline_sarima.png', dpi=300, bbox_inches='tight')
plt.close()
```

---

## 📊 FORMATO DE SALIDA ESPERADO

Genera 3 archivos:

### **1. codigo_extraido.py**
Todo el código relevante de forecasting.py comentado y documentado.

### **2. datos_resultados.csv**
Datos reales de predicciones para generar gráficas.

### **3. tablas_latex.txt**
Todas las tablas en formato LaTeX listas para copiar al artículo.

---

## ✅ CHECKLIST DE VALIDACIÓN

Antes de terminar, verifica:
- [ ] Todo el código extraído compila sin errores
- [ ] Las 4 gráficas se generan correctamente en `image/`
- [ ] Las tablas tienen datos reales (no placeholder)
- [ ] Las métricas R², RMSE, MAE, MAPE son consistentes
- [ ] El modelo SARIMA identificado coincide con el del abstract: (1,1,1)(1,1,1)₂₄

---

## 🚀 EJECUCIÓN

```bash
# 1. Extraer código
python extract_forecasting_code.py

# 2. Generar datos de validación
python export_predictions.py --last-30-days --format csv

# 3. Crear todas las gráficas
python generate_article_figures.py

# 4. Generar tablas LaTeX
python generate_latex_tables.py

# 5. Verificar outputs
ls -lh image/*.png
cat tablas_latex.txt
head -20 datos_resultados.csv
```

---

## 📝 NOTAS IMPORTANTES

1. **Prioriza datos reales**: Si no tienes suficiente histórico, usa al menos 7 días reales
2. **Gráficas profesionales**: Usa DPI=300, colores consistentes, etiquetas claras
3. **Métricas consistentes**: Asegúrate que R²=0.87 mencionado en abstract se refleje en tablas
4. **Código limpio**: El código para el artículo debe estar bien comentado y simplificado

---

## 💡 SUGERENCIAS ADICIONALES

Si encuentras problemas:
- Usa `pmdarima.auto_arima` para selección automática de parámetros
- Para datos faltantes, considera interpolación lineal
- Si el modelo no converge, reduce el orden (p,q) o aumenta datos de entrenamiento
- Valida estacionariedad con test de Dickey-Fuller antes de entrenar

---

**¡ADELANTE, ANTIGRAVITY! Genera todo lo necesario para completar el artículo de SentinelNexus.** 🚀
