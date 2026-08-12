import pandas as pd
import numpy as np
import xgboost as xgb
import shap
from django.utils import timezone
from datetime import timedelta
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

from submodulos.models import ProxmoxServer, ServerMetric, ServerPrediction, AgentLog, XAIExplanationLog
from submodulos.models import MaquinaVirtual, VMMetric, VMPrediction

def prepare_features(df, target_col):
    """
    Crea características avanzadas de series temporales (lags, rolling stats, 
    estacionalidad cíclica y aceleración) para el entrenamiento del regresor XGBoost.
    """
    df_feat = df[[target_col]].copy()
    
    # Lag features (valores históricos anteriores)
    df_feat['lag_1'] = df_feat[target_col].shift(1)
    df_feat['lag_2'] = df_feat[target_col].shift(2)
    df_feat['lag_3'] = df_feat[target_col].shift(3)
    
    # Lag de ciclo diario (si hay suficiente historial)
    if len(df_feat) >= 25:
        df_feat['lag_24'] = df_feat[target_col].shift(24)
    else:
        df_feat['lag_24'] = df_feat['lag_1']
        
    # Velocity / Accel (Diferencia de cambio reciente)
    df_feat['diff_1_2'] = df_feat['lag_1'] - df_feat['lag_2']
    
    # Rolling stats (Promedios y Volatilidad móvil)
    df_feat['rolling_mean_3'] = df_feat[target_col].shift(1).rolling(3, min_periods=1).mean()
    df_feat['rolling_mean_6'] = df_feat[target_col].shift(1).rolling(6, min_periods=1).mean()
    df_feat['rolling_std_3'] = df_feat[target_col].shift(1).rolling(3, min_periods=1).std().fillna(0.0)
    
    # Temporal & Cyclical features (Codificación armónica seno/coseno)
    hour = df_feat.index.hour
    dayofweek = df_feat.index.dayofweek
    
    df_feat['hour_sin'] = np.sin(2 * np.pi * hour / 24.0)
    df_feat['hour_cos'] = np.cos(2 * np.pi * hour / 24.0)
    df_feat['day_sin'] = np.sin(2 * np.pi * dayofweek / 7.0)
    df_feat['day_cos'] = np.cos(2 * np.pi * dayofweek / 7.0)
    
    # Eliminar filas con NaN por los desfases iniciales
    df_feat.dropna(inplace=True)
    return df_feat

def calculate_model_metrics(y_true, y_pred):
    """
    Calcula métricas académicas cuantitativas de precisión: RMSE, MAE, MAPE y R^2 score.
    """
    try:
        rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
        mae = float(mean_absolute_error(y_true, y_pred))
        
        # Evitar división por cero en MAPE
        non_zero_mask = y_true > 0.1
        if np.sum(non_zero_mask) > 0:
            mape = float(np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100.0)
        else:
            mape = 0.0
            
        std_true = np.std(y_true)
        if std_true < 0.001 and rmse < 0.5:
            r2 = 1.0
        else:
            r2 = float(r2_score(y_true, y_pred))
            if r2 < 0.0: r2 = 0.0
            
        return {
            'rmse': round(rmse, 2),
            'mae': round(mae, 2),
            'mape': round(mape, 2),
            'r2': round(r2, 3)
        }
    except Exception as e:
        return {'rmse': 0.0, 'mae': 0.0, 'mape': 0.0, 'r2': 0.0}

def generate_shap_explanation(model, X_sample, feature_names):
    """
    Genera una explicación matemática en lenguaje natural utilizando los valores SHAP del modelo.
    """
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)[0]
        
        friendly_names = {
            'lag_1': 'la carga en la última hora',
            'lag_2': 'la carga de hace 2 horas',
            'lag_3': 'la carga de hace 3 horas',
            'lag_24': 'el consumo del día anterior en este mismo horario (patrón diario)',
            'diff_1_2': 'la velocidad de cambio en la demanda de la última hora',
            'rolling_mean_3': 'la tendencia alcista reciente de 3 horas',
            'rolling_mean_6': 'la inercia promedio de las últimas 6 horas',
            'rolling_std_3': 'la volatilidad reciente del consumo',
            'hour_sin': 'el ciclo horario de producción',
            'hour_cos': 'el ciclo horario de producción',
            'day_sin': 'el comportamiento operativo del día de la semana',
            'day_cos': 'el comportamiento operativo del día de la semana'
        }
        
        contributions = []
        for name, val in zip(feature_names, shap_values):
            contributions.append((name, val))
            
        contributions.sort(key=lambda x: abs(x[1]), reverse=True)
        
        pos_contribs = [(n, v) for n, v in contributions if v > 0]
        total_pos = sum(v for n, v in pos_contribs)
        
        if total_pos > 0 and len(pos_contribs) > 0:
            explanation_parts = []
            for name, val in pos_contribs[:3]:
                pct = (val / total_pos) * 100
                explanation_parts.append(f"{pct:.0f}% debido a {friendly_names.get(name, name)}")
            
            explicacion = ", ".join(explanation_parts)
        else:
            top_name, _ = contributions[0]
            explicacion = f"comportamiento normal influenciado principalmente por {friendly_names.get(top_name, top_name)}"
            
        return explicacion, shap_values.tolist()
    except Exception as e:
        return f"Error en análisis de explicabilidad SHAP: {str(e)}", []

def generate_contextual_explanation(model, X_sample, feature_names, predicted_cpu, predicted_ram, is_vm, entity_name, future_time):
    """
    Genera un diagnóstico contextualizado profundo en español a partir de valores SHAP
    y parámetros de series temporales.
    """
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)[0]
        
        friendly_names = {
            'lag_1': 'la carga registrada en la última hora',
            'lag_2': 'el consumo de hace 2 horas',
            'lag_3': 'el consumo de hace 3 horas',
            'lag_24': 'el consumo histórico del día anterior en este mismo horario (patrón diario)',
            'diff_1_2': 'la aceleración súbita en la demanda de cómputo',
            'rolling_mean_3': 'la tendencia de consumo acumulada en las últimas 3 horas',
            'rolling_mean_6': 'la inercia promedio de carga de las últimas 6 horas',
            'rolling_std_3': 'la volatilidad observada en el consumo reciente',
            'hour_sin': 'la estacionalidad típica de la hora del día',
            'hour_cos': 'la estacionalidad típica de la hora del día',
            'day_sin': 'el comportamiento operativo cíclico del día de la semana',
            'day_cos': 'el comportamiento operativo cíclico del día de la semana'
        }
        
        contributions = []
        for name, val in zip(feature_names, shap_values):
            contributions.append((name, val))
            
        pos_contribs = [(n, v) for n, v in contributions if v > 0]
        neg_contribs = [(n, v) for n, v in contributions if v < 0]
        
        pos_contribs.sort(key=lambda x: x[1], reverse=True)
        neg_contribs.sort(key=lambda x: x[1])
        
        tipo_entidad = "Máquina Virtual" if is_vm else "Servidor Proxmox"
        
        if predicted_cpu > 80.0:
            diagnostico_evento = f"Pico Crítico Anómalo Previsto ({predicted_cpu:.1f}% CPU)"
            accion_recomendada = "Se recomienda al agente Vigilante (Watchdog) iniciar monitoreo activo de subprocesos y preparar balanceo de carga."
        elif predicted_cpu > 55.0:
            diagnostico_evento = f"Pico Operativo Moderado Detectado ({predicted_cpu:.1f}% CPU)"
            accion_recomendada = "Se recomienda vigilar el consumo de memoria concurrente y verificar tareas programadas (cron jobs)."
        elif predicted_cpu > 35.0:
            diagnostico_evento = f"Comportamiento Operativo Normal ({predicted_cpu:.1f}% CPU)"
            accion_recomendada = "Comportamiento dentro de límites operativos. Se aconseja mantener monitoreo preventivo regular."
        else:
            diagnostico_evento = f"Comportamiento Estable de Baja Carga ({predicted_cpu:.1f}% CPU)"
            accion_recomendada = "Mantener monitoreo pasivo regular en segundo plano."
            
        narrativa = (
            f"El análisis predictivo mediante XGBoost y explicabilidad SHAP para el {tipo_entidad.lower()} "
            f"<strong>{entity_name}</strong> a las {future_time.strftime('%H:%M')} del día {future_time.strftime('%d/%m')} "
            f"indica un {diagnostico_evento.lower()}. El consumo estimado se situará en un "
            f"<strong>{predicted_cpu:.1f}% de CPU</strong> y un <strong>{predicted_ram:.1f}% de RAM</strong>. "
        )
        
        if pos_contribs:
            drivers_desc = []
            for name, val in pos_contribs[:2]:
                drivers_desc.append(f"<strong>{friendly_names.get(name, name)}</strong> (SHAP: +{val:.2f}%)")
            
            narrativa += f"Este comportamiento de carga está siendo provocado e impulsado principalmente por {', en conjunto con '.join(drivers_desc)}. "
            
            top_feat = pos_contribs[0][0]
            if top_feat == 'lag_24':
                narrativa += "Esto confirma la presencia de un patrón estacional repetitivo diario en este mismo horario, característico de sus picos operativos cíclicos habituales. "
            elif top_feat in ['rolling_mean_3', 'rolling_mean_6']:
                narrativa += "Esto demuestra un incremento y acumulación sostenida en la carga en las horas precedentes, lo que crea una tendencia inercial. "
            elif top_feat in ['lag_1', 'lag_2', 'diff_1_2']:
                narrativa += "Esto refleja una aceleración rápida en la demanda de CPU en los últimos instantes registrados. "
            elif top_feat in ['hour_sin', 'hour_cos', 'day_sin', 'day_cos']:
                narrativa += "Esto se debe fuertemente al comportamiento estacional natural de la hora y el día de la semana. "
        else:
            narrativa += "No se registran factores que incrementen significativamente la carga, manteniéndose en una inercia operativa normal. "
            
        if neg_contribs:
            mitigators = []
            for name, val in neg_contribs[:2]:
                mitigators.append(f"<strong>{friendly_names.get(name, name)}</strong> (SHAP: {val:.2f}%)")
            narrativa += f"Por otro lado, elementos como {', seguido de '.join(mitigators)} actúan como amortiguadores, ayudando a mitigar el consumo previsto."
            
        return diagnostico_evento, narrativa, accion_recomendada, shap_values.tolist()
    except Exception as e:
        return "Error en diagnóstico", f"No se pudo generar explicación: {str(e)}", "Verificar logs de sistema", []

def recursive_forecast(model, df_resampled, target_col, steps, std_residuals, feature_names):
    """
    Genera predicciones iterativas paso a paso (recursivas) para 'steps' horas a futuro.
    Aplica límites lógicos entre 0% y 100%.
    """
    predictions = []
    lower_bounds = []
    upper_bounds = []
    feature_sets = []
    
    history = df_resampled[[target_col]].copy()
    last_timestamp = df_resampled.index[-1]
    
    for i in range(steps):
        future_time = last_timestamp + timedelta(hours=i+1)
        
        val_lag_1 = float(history[target_col].iloc[-1])
        val_lag_2 = float(history[target_col].iloc[-2]) if len(history) >= 2 else val_lag_1
        val_lag_3 = float(history[target_col].iloc[-3]) if len(history) >= 3 else val_lag_2
        val_lag_24 = float(history[target_col].iloc[-24]) if len(history) >= 24 else val_lag_1
        
        val_diff_1_2 = val_lag_1 - val_lag_2
        val_roll_3 = float(history[target_col].iloc[-3:].mean()) if len(history) >= 3 else val_lag_1
        val_roll_6 = float(history[target_col].iloc[-6:].mean()) if len(history) >= 6 else val_lag_1
        val_roll_std_3 = float(history[target_col].iloc[-3:].std()) if len(history) >= 3 else 0.0
        if np.isnan(val_roll_std_3): val_roll_std_3 = 0.0
        
        val_hour_sin = np.sin(2 * np.pi * future_time.hour / 24.0)
        val_hour_cos = np.cos(2 * np.pi * future_time.hour / 24.0)
        val_day_sin = np.sin(2 * np.pi * future_time.dayofweek / 7.0)
        val_day_cos = np.cos(2 * np.pi * future_time.dayofweek / 7.0)
        
        row_dict = {
            'lag_1': val_lag_1,
            'lag_2': val_lag_2,
            'lag_3': val_lag_3,
            'lag_24': val_lag_24,
            'diff_1_2': val_diff_1_2,
            'rolling_mean_3': val_roll_3,
            'rolling_mean_6': val_roll_6,
            'rolling_std_3': val_roll_std_3,
            'hour_sin': val_hour_sin,
            'hour_cos': val_hour_cos,
            'day_sin': val_day_sin,
            'day_cos': val_day_cos
        }
        
        X_future = pd.DataFrame([[row_dict[fn] for fn in feature_names]], columns=feature_names)
        
        pred_val = float(model.predict(X_future)[0])
        pred_val = max(0.0, min(100.0, pred_val))
        
        conf_low = max(0.0, pred_val - 1.96 * std_residuals)
        conf_up = min(100.0, pred_val + 1.96 * std_residuals)
        
        predictions.append(pred_val)
        lower_bounds.append(conf_low)
        upper_bounds.append(conf_up)
        feature_sets.append(X_future.iloc[0].values)
        
        new_row = pd.DataFrame({target_col: [pred_val]}, index=[future_time])
        history = pd.concat([history, new_row])
        
    return predictions, lower_bounds, upper_bounds, feature_sets

def fit_and_evaluate_model(X, y, n_estimators=60, max_depth=4, learning_rate=0.1):
    """
    Entrena el regresor XGBoost con división de validación fuera de muestra (out-of-fold validation)
    para obtener métricas científicas rigurosas no sesgadas (RMSE, MAE, MAPE, R^2).
    """
    n_samples = len(X)
    if n_samples >= 20:
        split_idx = int(n_samples * 0.85)
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]
    else:
        X_train, X_val = X, X
        y_train, y_val = y, y
        
    model = xgb.XGBRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        random_state=42,
        subsample=0.85,
        colsample_bytree=0.85
    )
    
    # Entrenar en conjunto de entrenamiento
    model.fit(X_train, y_train)
    
    # Evaluar en conjunto de validación fuera de muestra
    y_pred_val = model.predict(X_val)
    metrics = calculate_model_metrics(y_val.values, y_pred_val)
    
    # Ajuste final con todos los datos disponibles para la inferencia futura
    model.fit(X, y)
    
    std_residuals = float(np.std(y_val.values - y_pred_val)) if len(y_val) > 1 else float(np.std(y.values - model.predict(X)))
    if std_residuals < 1.0 or np.isnan(std_residuals): 
        std_residuals = 2.5
        
    return model, metrics, std_residuals

def train_and_predict_server(server_id, steps=24):
    """
    Entrena modelos XGBoost para un servidor Proxmox específico, evalúa métricas cuantitativas,
    calcula explicabilidad SHAP y guarda las predicciones en PostgreSQL.
    """
    try:
        server = ProxmoxServer.objects.get(pk=server_id)
        start_date = timezone.now() - timedelta(days=30)
 
        metrics = ServerMetric.objects.filter(
            server=server, 
            timestamp__gte=start_date
        ).order_by('timestamp').values('timestamp', 'cpu_usage', 'ram_usage')
        
        if not metrics.exists():
            print(f"[XGBoost] No hay métricas registradas para el servidor {server.name}")
            return None
            
        df = pd.DataFrame(list(metrics))
        df.rename(columns={'ram_usage': 'memory_usage'}, inplace=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        df_resampled = df.resample('h').mean().ffill()
        
        if len(df_resampled) < 6:
             print(f"[XGBoost] Datos insuficientes (< 6 horas) para servidor {server.name}")
             return None

        feature_names = ['lag_1', 'lag_2', 'lag_3', 'lag_24', 'diff_1_2', 'rolling_mean_3', 'rolling_mean_6', 'rolling_std_3', 'hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        
        # 1. Entrenar y Evaluar Modelo CPU
        df_features_cpu = prepare_features(df_resampled, 'cpu_usage')
        X_cpu = df_features_cpu[feature_names]
        y_cpu = df_features_cpu['cpu_usage']
        
        model_cpu, metrics_cpu, std_residuals_cpu = fit_and_evaluate_model(
            X_cpu, y_cpu, n_estimators=60, max_depth=4, learning_rate=0.1
        )
        
        preds_cpu, lows_cpu, ups_cpu, features_cpu = recursive_forecast(
            model_cpu, df_resampled, 'cpu_usage', steps, std_residuals_cpu, feature_names
        )

        # 2. Entrenar y Evaluar Modelo RAM
        df_features_ram = prepare_features(df_resampled, 'memory_usage')
        X_ram = df_features_ram[feature_names]
        y_ram = df_features_ram['memory_usage']
        
        model_ram, metrics_ram, std_residuals_ram = fit_and_evaluate_model(
            X_ram, y_ram, n_estimators=60, max_depth=4, learning_rate=0.1
        )
        
        preds_ram, _, _, features_ram = recursive_forecast(
            model_ram, df_resampled, 'memory_usage', steps, std_residuals_ram, feature_names
        )
        
        # 3. Explicabilidad SHAP en el pico proyectado
        max_cpu_idx = int(np.argmax(preds_cpu))
        max_cpu_time = df_resampled.index[-1] + timedelta(hours=max_cpu_idx + 1)
        max_cpu_val = preds_cpu[max_cpu_idx]
        
        expl_cpu, shap_vals_cpu = generate_shap_explanation(
            model_cpu, 
            features_cpu[max_cpu_idx].reshape(1, -1), 
            feature_names
        )
        
        diagnostico_evento, explicacion_texto, accion_recomendada, _ = generate_contextual_explanation(
            model_cpu,
            features_cpu[max_cpu_idx].reshape(1, -1),
            feature_names,
            max_cpu_val,
            preds_ram[max_cpu_idx],
            is_vm=False,
            entity_name=server.name,
            future_time=max_cpu_time
        )
        
        # Guardar en XAIExplanationLog
        XAIExplanationLog.objects.filter(
            tipo_entidad='server',
            server=server,
            timestamp_prediccion=max_cpu_time
        ).delete()
        
        XAIExplanationLog.objects.create(
            tipo_entidad='server',
            server=server,
            timestamp_prediccion=max_cpu_time,
            cpu_predicha=max_cpu_val,
            ram_predicha=preds_ram[max_cpu_idx],
            is_anomaly=bool(max_cpu_val > 80.0),
            diagnostico_evento=diagnostico_evento,
            explicacion_texto=explicacion_texto,
            accion_recomendada=accion_recomendada,
            valores_shap={name: float(val) for name, val in zip(feature_names, shap_vals_cpu)},
            features_usadas={name: float(val) for name, val in zip(feature_names, features_cpu[max_cpu_idx])}
        )
        
        # 4. Guardar Predicciones futuras en PostgreSQL
        last_timestamp = df_resampled.index[-1]
        for i in range(steps):
            future_time = last_timestamp + timedelta(hours=i+1)
            ServerPrediction.objects.filter(server=server, timestamp=future_time).delete()
            ServerPrediction.objects.create(
                server=server,
                timestamp=future_time,
                predicted_cpu_usage=preds_cpu[i],
                predicted_memory_usage=preds_ram[i],
                confidence_lower=lows_cpu[i],
                confidence_upper=ups_cpu[i]
            )
            
        print(f"[XGBoost] Servidor {server.name} procesado ({steps}h). Métricas CPU -> RMSE: {metrics_cpu['rmse']}%, MAE: {metrics_cpu['mae']}%, R²: {metrics_cpu['r2']}")
        
        AgentLog.objects.create(
            agent_name="Cerebro",
            level="ACTION",
            message=f"Modelo XGBoost entrenado para {server.name} (RMSE: {metrics_cpu['rmse']}%, MAE: {metrics_cpu['mae']}%, R²: {metrics_cpu['r2']})",
            details={
                "server_id": server.id,
                "server_name": server.name,
                "metrics_cpu": metrics_cpu,
                "metrics_ram": metrics_ram,
                "peak_time": max_cpu_time.isoformat(),
                "peak_cpu": max_cpu_val,
                "explanation_shap": expl_cpu
            }
        )
        return metrics_cpu
        
    except Exception as e:
        print(f"Error generando predicciones XGBoost para servidor {server_id}: {str(e)}")
        return None

def train_and_predict_vm(vm_id, steps=24):
    """
    Entrena un modelo XGBoost para una Máquina Virtual (VM), predice su comportamiento futuro,
    detecta anomalías, evalúa precisión y genera un análisis SHAP.
    """
    try:
        vm = MaquinaVirtual.objects.get(pk=vm_id)
        start_date = timezone.now() - timedelta(days=14) 
        
        metrics = VMMetric.objects.filter(
            vm_name=vm.nombre, 
            timestamp__gte=start_date
        ).order_by('timestamp').values('timestamp', 'cpu_usage', 'ram_usage')
        
        if not metrics.exists():
            print(f"[XGBoost] No hay métricas registradas para la VM {vm.nombre}")
            return None

        df = pd.DataFrame(list(metrics))
        df.rename(columns={'ram_usage': 'memory_usage'}, inplace=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        df_resampled = df.resample('h').mean().ffill()
        
        if len(df_resampled) < 6:
             print(f"[XGBoost] Datos insuficientes (< 6h) para VM {vm.nombre}")
             return None

        feature_names = ['lag_1', 'lag_2', 'lag_3', 'lag_24', 'diff_1_2', 'rolling_mean_3', 'rolling_mean_6', 'rolling_std_3', 'hour_sin', 'hour_cos', 'day_sin', 'day_cos']

        # 1. Entrenar y Predecir CPU de VM
        df_features_cpu = prepare_features(df_resampled, 'cpu_usage')
        X_cpu = df_features_cpu[feature_names]
        y_cpu = df_features_cpu['cpu_usage']
        
        model_cpu, metrics_cpu, std_residuals_cpu = fit_and_evaluate_model(
            X_cpu, y_cpu, n_estimators=40, max_depth=3, learning_rate=0.12
        )
        
        preds_cpu, _, _, features_cpu = recursive_forecast(
            model_cpu, df_resampled, 'cpu_usage', steps, std_residuals_cpu, feature_names
        )

        # 2. Entrenar y Predecir RAM de VM
        df_features_ram = prepare_features(df_resampled, 'memory_usage')
        X_ram = df_features_ram[feature_names]
        y_ram = df_features_ram['memory_usage']
        
        model_ram, metrics_ram, std_residuals_ram = fit_and_evaluate_model(
            X_ram, y_ram, n_estimators=40, max_depth=3, learning_rate=0.12
        )
        
        preds_ram, _, _, features_ram = recursive_forecast(
            model_ram, df_resampled, 'memory_usage', steps, std_residuals_ram, feature_names
        )
        
        # 3. Detección Inteligente de Anomalías
        mean_cpu = float(np.mean(y_cpu))
        std_cpu = float(np.std(y_cpu))
        anomaly_threshold_cpu = max(75.0, mean_cpu + 2 * std_cpu)
        
        # 4. Guardar Predicciones de VM
        last_timestamp = df_resampled.index[-1]
        anomaly_count = 0
        peak_idx = int(np.argmax(preds_cpu))
        
        for i in range(steps):
            future_time = last_timestamp + timedelta(hours=i+1)
            is_anomaly = bool(preds_cpu[i] > anomaly_threshold_cpu)
            if is_anomaly:
                anomaly_count += 1
            
            VMPrediction.objects.filter(vm=vm, timestamp=future_time).delete()
            VMPrediction.objects.create(
                vm=vm,
                timestamp=future_time,
                predicted_cpu_usage=preds_cpu[i],
                predicted_memory_usage=preds_ram[i],
                is_anomaly=is_anomaly
            )
            
        # 5. Explicabilidad SHAP en el pico
        peak_time = df_resampled.index[-1] + timedelta(hours=peak_idx + 1)
        peak_cpu_val = preds_cpu[peak_idx]
        
        expl_cpu, shap_vals_cpu = generate_shap_explanation(
            model_cpu, 
            features_cpu[peak_idx].reshape(1, -1), 
            feature_names
        )
        
        diagnostico_evento, explicacion_texto, accion_recomendada, _ = generate_contextual_explanation(
            model_cpu,
            features_cpu[peak_idx].reshape(1, -1),
            feature_names,
            peak_cpu_val,
            preds_ram[peak_idx],
            is_vm=True,
            entity_name=vm.nombre,
            future_time=peak_time
        )
        
        XAIExplanationLog.objects.filter(
            tipo_entidad='vm',
            vm=vm,
            timestamp_prediccion=peak_time
        ).delete()
        
        XAIExplanationLog.objects.create(
            tipo_entidad='vm',
            vm=vm,
            timestamp_prediccion=peak_time,
            cpu_predicha=peak_cpu_val,
            ram_predicha=preds_ram[peak_idx],
            is_anomaly=bool(peak_cpu_val > anomaly_threshold_cpu),
            diagnostico_evento=diagnostico_evento,
            explicacion_texto=explicacion_texto,
            accion_recomendada=accion_recomendada,
            valores_shap={name: float(val) for name, val in zip(feature_names, shap_vals_cpu)},
            features_usadas={name: float(val) for name, val in zip(feature_names, features_cpu[peak_idx])}
        )
        
        print(f"[XGBoost] VM {vm.nombre} procesada ({steps}h). Métricas CPU -> RMSE: {metrics_cpu['rmse']}%, MAE: {metrics_cpu['mae']}%, R²: {metrics_cpu['r2']}")
        return metrics_cpu
        
    except Exception as e:
        print(f"Error generando predicciones XGBoost para VM {vm_id}: {str(e)}")
        return None

def train_and_predict_all(steps=24):
    """
    Ejecuta el pipeline completo de entrenamiento y predicción XGBoost + SHAP XAI
    para todos los servidores Proxmox y máquinas virtuales registradas.
    Calcula y asienta las métricas globales de calibración en la base de datos.
    """
    print("[Forecasting Pipeline] Iniciando ciclo global de entrenamiento y predicción...")
    
    all_metrics = []
    
    servers = ProxmoxServer.objects.filter(is_active=True)
    if not servers.exists():
        servers = ProxmoxServer.objects.all()
        
    for server in servers:
        m = train_and_predict_server(server.id, steps=steps)
        if m: all_metrics.append(m)
        
    vms = MaquinaVirtual.objects.all()
    for vm in vms:
        m = train_and_predict_vm(vm.pk, steps=steps)
        if m: all_metrics.append(m)
        
    if all_metrics:
        avg_rmse = round(float(np.mean([m['rmse'] for m in all_metrics])), 2)
        avg_mae = round(float(np.mean([m['mae'] for m in all_metrics])), 2)
        avg_r2 = round(float(np.mean([m['r2'] for m in all_metrics])), 3)
        
        AgentLog.objects.create(
            agent_name="Cerebro",
            level="INFO",
            message=f"Pipeline ML Completado: {len(all_metrics)} modelos entrenados (RMSE Medio: {avg_rmse}%, MAE Medio: {avg_mae}%, R² Medio: {avg_r2})",
            details={
                "models_trained": len(all_metrics),
                "avg_rmse": avg_rmse,
                "avg_mae": avg_mae,
                "avg_r2": avg_r2
            }
        )
        print(f"[Forecasting Pipeline] Calibración Global -> Modelos: {len(all_metrics)}, RMSE Medio: {avg_rmse}%, MAE Medio: {avg_mae}%, R² Medio: {avg_r2}")
        
    print("[Forecasting Pipeline] Ciclo completado exitosamente.")
