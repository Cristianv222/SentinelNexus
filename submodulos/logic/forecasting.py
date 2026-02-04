import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from django.utils import timezone
from datetime import timedelta
from submodulos.models import ProxmoxServer, ServerMetric, ServerPrediction
from submodulos.models import MaquinaVirtual, VMMetric, VMPrediction

def train_and_predict_server(server_id, steps=48):
    """
    Entrena un modelo SARIMA para un servidor específico y genera predicciones.
    
    Args:
        server_id (int): ID del ProxmoxServer.
        steps (int): Número de pasos (horas) a predecir. Default: 48 horas (2 días).
    """
    try:
        server = ProxmoxServer.objects.get(pk=server_id)
        
        # 1. Obtener datos históricos (últimos 30 días para entrenar)
        start_date = timezone.now() - timedelta(days=30)
 
        # Corrigiendo modelo y campos: Usamos ServerMetric (singular) y created_at
        # Nota: Usamos la relación ForeignKey directa 'server'
        metrics = ServerMetric.objects.filter(
            server=server, 
            timestamp__gte=start_date
        ).order_by('timestamp').values('timestamp', 'cpu_usage', 'ram_usage')
        
        if not metrics:
            print(f"No hay métricas suficientes para el servidor {server.name} (nodo: {server.node_name})")
            return

        df = pd.DataFrame(metrics)
        # Renombrar columnas para estandarizar
        df.rename(columns={'ram_usage': 'memory_usage'}, inplace=True)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resamplear a promedios horarios para suavizar y reducir ruido
        df_resampled = df.resample('h').mean().ffill()
        
        if len(df_resampled) < 24:
             print(f"Datos insuficientes (menos de 24h) para entrenar modelo de servidor {server.name}")
             return
        
        # 2. Entrenar Modelo CPU
        # SARIMA(1, 1, 1)(1, 1, 1, 24) es un buen punto de partida genérico para datos horarios estacionales
        model_cpu = SARIMAX(df_resampled['cpu_usage'], 
                            order=(1, 1, 1), 
                            seasonal_order=(1, 1, 1, 24),
                            enforce_stationarity=False,
                            enforce_invertibility=False)
        results_cpu = model_cpu.fit(disp=False)
        forecast_cpu = results_cpu.get_forecast(steps=steps)
        predicted_cpu = forecast_cpu.predicted_mean
        conf_int_cpu = forecast_cpu.conf_int()

        # 3. Entrenar Modelo RAM
        model_ram = SARIMAX(df_resampled['memory_usage'], 
                            order=(1, 1, 1), 
                            seasonal_order=(1, 1, 1, 24),
                            enforce_stationarity=False,
                            enforce_invertibility=False)
        results_ram = model_ram.fit(disp=False)
        forecast_ram = results_ram.get_forecast(steps=steps)
        predicted_ram = forecast_ram.predicted_mean
        
        # 4. Guardar Predicciones
        predictions_to_create = []
        last_timestamp = df_resampled.index[-1]
        
        for i in range(steps):
            future_time = last_timestamp + timedelta(hours=i+1)
            
            # Asegurar no negativos
            cpu_val = max(0, predicted_cpu.iloc[i])
            ram_val = max(0, predicted_ram.iloc[i])
            
            # Limpiar predicciones viejas para este timestamp si existen
            ServerPrediction.objects.filter(server=server, timestamp=future_time).delete()
            
            predictions_to_create.append(
                ServerPrediction(
                    server=server,
                    timestamp=future_time,
                    predicted_cpu_usage=cpu_val,
                    predicted_memory_usage=ram_val,
                    confidence_lower=max(0, conf_int_cpu.iloc[i, 0]),
                    confidence_upper=conf_int_cpu.iloc[i, 1]
                )
            )
        
        ServerPrediction.objects.bulk_create(predictions_to_create)
        print(f"Predicciones generadas para {server.name} ({steps} horas)")
        
    except Exception as e:
        print(f"Error generando predicciones para server {server_id}: {str(e)}")

def train_and_predict_vm(vm_id, steps=48):
    """
    Genera predicciones para una VM específica para detección de anomalías.
    """
    try:
        vm = MaquinaVirtual.objects.get(pk=vm_id)
        
        # 1. Obtener datos históricos
        start_date = timezone.now() - timedelta(days=14) 
        
        # Corrigiendo modelo: Usamos VMMetric (singular)
        # Filtramos por vm_name = vm.nombre
        metrics = VMMetric.objects.filter(
            vm_name=vm.nombre, 
            timestamp__gte=start_date
        ).order_by('timestamp').values('timestamp', 'cpu_usage', 'ram_usage')
        
        if not metrics:
            print(f"No hay métricas suficientes para la VM {vm.nombre}")
            return

        df = pd.DataFrame(metrics)
        df.rename(columns={'ram_usage': 'memory_usage'}, inplace=True)
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resamplear a promedios horarios
        df_resampled = df.resample('h').mean().ffill()
        
        if len(df_resampled) < 12: # Mínimo datos para intentar algo
             print(f"Datos insuficientes para entrenar modelo de VM {vm.nombre}")
             return

        # 2. Entrenar Modelo CPU
        model_cpu = SARIMAX(df_resampled['cpu_usage'], 
                            order=(1, 0, 1), 
                            seasonal_order=(0, 0, 0, 0), 
                            enforce_stationarity=False,
                            enforce_invertibility=False)
        results_cpu = model_cpu.fit(disp=False)
        forecast_cpu = results_cpu.get_forecast(steps=steps)
        predicted_cpu = forecast_cpu.predicted_mean

        # 3. Entrenar Modelo RAM
        model_ram = SARIMAX(df_resampled['memory_usage'], 
                            order=(1, 0, 1),
                            seasonal_order=(0, 0, 0, 0),
                            enforce_stationarity=False,
                            enforce_invertibility=False)
        results_ram = model_ram.fit(disp=False)
        forecast_ram = results_ram.get_forecast(steps=steps)
        predicted_ram = forecast_ram.predicted_mean
        
        # 4. Guardar Predicciones
        predictions_to_create = []
        last_timestamp = df_resampled.index[-1]
        
        for i in range(steps):
            future_time = last_timestamp + timedelta(hours=i+1)
            
            # Limpiar predicciones viejas
            VMPrediction.objects.filter(vm=vm, timestamp=future_time).delete()
            
            predictions_to_create.append(
                VMPrediction(
                    vm=vm,
                    timestamp=future_time,
                    predicted_cpu_usage=max(0, predicted_cpu.iloc[i]),
                    predicted_memory_usage=max(0, predicted_ram.iloc[i]),
                    is_anomaly=False
                )
            )
        
        VMPrediction.objects.bulk_create(predictions_to_create)
        print(f"Predicciones generadas para VM {vm.nombre}")
        
    except Exception as e:
        print(f"Error generando predicciones para VM {vm_id}: {str(e)}")
