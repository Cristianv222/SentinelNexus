// metrics.js - Sistema mejorado de métricas en tiempo real

// Estado global
const MetricsManager = {
    charts: {},
    vmCharts: {},
    predictionCharts: {},
    autoRefreshInterval: null,
    isAutoRefreshing: false,
    expandedServers: {},
    lastValidData: null,
    retryCount: 0,
    maxRetries: 3
};

// Configuración
const CONFIG = {
    refreshInterval: 30000,
    requestTimeout: 15000,
    cacheExpiry: 10000,
    chartOptions: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 500 },
        plugins: { legend: { display: false } }
    }
};

// Cache local para evitar pérdida de datos
class DataCache {
    static set(key, data) {
        const cacheData = {
            data: data,
            timestamp: Date.now()
        };
        localStorage.setItem(`metrics_${key}`, JSON.stringify(cacheData));
    }
    
    static get(key, maxAge = CONFIG.cacheExpiry) {
        try {
            const cached = localStorage.getItem(`metrics_${key}`);
            if (!cached) return null;
            
            const cacheData = JSON.parse(cached);
            const age = Date.now() - cacheData.timestamp;
            
            if (age < maxAge) {
                return cacheData.data;
            }
        } catch (e) {
            console.error('Error leyendo caché:', e);
        }
        return null;
    }
}

// Función principal mejorada
async function loadServerMetrics() {
    try {
        // Intentar obtener del caché primero
        const cachedData = DataCache.get('server_metrics', 5000);
        if (cachedData && !document.hidden) {
            updateDisplay(cachedData);
        }
        
        // Hacer petición con timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.requestTimeout);
        
        const response = await fetch('/api/metrics/', {
            signal: controller.signal,
            headers: {
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.success && data.servers) {
            // Guardar en caché
            DataCache.set('server_metrics', data);
            MetricsManager.lastValidData = data;
            MetricsManager.retryCount = 0;
            
            // Actualizar display
            updateDisplay(data);
            
            // Actualizar timestamp
            updateLastRefreshTime();
        }
        
    } catch (error) {
        handleLoadError(error);
    }
}

// Función para actualizar toda la visualización
function updateDisplay(data) {
    if (!data.servers) return;
    
    data.servers.forEach((server, index) => {
        const serverNum = index + 1;
        updateServerCard(serverNum, server);
    });
}

// Actualizar tarjeta de servidor individual
function updateServerCard(serverNum, server) {
    // Nombre del servidor
    const nameEl = document.getElementById(`server-name-${serverNum}`);
    if (nameEl && server.name) {
        // Asegurar que use el nombre correcto
        const correctNames = ['Servidor Principal', 'Servidor Secundario', 'Servidor Backup'];
        nameEl.textContent = correctNames[serverNum - 1] || server.name;
    }
    
    // Estado online/offline
    const statusEl = document.getElementById(`server-status-${serverNum}`);
    if (statusEl) {
        if (server.online) {
            statusEl.className = 'server-status status-online';
            statusEl.innerHTML = '<span class="pulse"></span> ONLINE';
        } else {
            statusEl.className = 'server-status status-offline';
            statusEl.innerHTML = '<span class="pulse"></span> OFFLINE';
        }
    }
    
    // Actualizar métricas solo si hay datos válidos
    if (server.metrics) {
        // CPU
        if (typeof server.metrics.cpu?.usage === 'number') {
            updateCircularProgress(`cpu-circle-${serverNum}`, server.metrics.cpu.usage);
        }
        
        // Memoria
        if (typeof server.metrics.memory?.percent === 'number') {
            updateCircularProgress(`mem-circle-${serverNum}`, server.metrics.memory.percent);
        }
        
        // Disco
        if (typeof server.metrics.disk?.percent === 'number') {
            updateCircularProgress(`disk-circle-${serverNum}`, server.metrics.disk.percent);
        }
        
        // Red
        const netMbps = server.metrics.network?.out_mbps || 0;
        const netEl = document.getElementById(`net-value-${serverNum}`);
        if (netEl) netEl.textContent = netMbps.toFixed(1);
        
        // Información adicional
        updateServerInfo(serverNum, server);
    }
    
    // Actualizar gráficos históricos
    if (server.history && server.history.timestamps?.length > 0) {
        updateServerCharts(serverNum, server.history);
    }
}

// Actualizar información del servidor
function updateServerInfo(serverNum, server) {
    const elements = {
        [`cores-${serverNum}`]: server.metrics.cpu?.cores || '--',
        [`ram-total-${serverNum}`]: server.metrics.memory?.total_gb ? 
            `${server.metrics.memory.total_gb} GB` : '--',
        [`storage-${serverNum}`]: formatStorage(server.metrics.disk),
        [`vms-${serverNum}`]: server.vms?.active || '0',
        [`uptime-${serverNum}`]: server.uptime || '--'
    };
    
    for (const [id, value] of Object.entries(elements)) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }
}

// Formatear almacenamiento
function formatStorage(disk) {
    if (!disk) return '--';
    
    if (disk.total_tb && disk.total_tb >= 1) {
        return `${disk.total_tb.toFixed(2)} TB`;
    } else if (disk.total_gb) {
        return `${disk.total_gb.toFixed(1)} GB`;
    }
    return '--';
}

// Actualizar gráficos con animación suave
function updateServerCharts(serverNum, history) {
    // CPU Chart
    const cpuChart = MetricsManager.charts[`cpu-${serverNum}`];
    if (cpuChart) {
        cpuChart.data.labels = history.timestamps;
        cpuChart.data.datasets[0].data = history.cpu;
        cpuChart.update('none'); // Sin animación para evitar parpadeo
    }
    
    // Memory Chart
    const memChart = MetricsManager.charts[`mem-${serverNum}`];
    if (memChart) {
        memChart.data.labels = history.timestamps;
        memChart.data.datasets[0].data = history.memory;
        memChart.update('none');
    }
}

// Actualizar círculo de progreso mejorado
function updateCircularProgress(elementId, value) {
    const circle = document.getElementById(elementId);
    const text = document.getElementById(elementId.replace('circle', 'text'));
    
    if (circle && text) {
        const circumference = 2 * Math.PI * 54;
        const validValue = Math.max(0, Math.min(100, value || 0));
        const offset = circumference - (validValue / 100) * circumference;
        
        // Transición suave
        circle.style.transition = 'stroke-dashoffset 0.5s ease-in-out';
        circle.style.strokeDashoffset = offset;
        
        // Actualizar texto
        text.textContent = Math.round(validValue) + '%';
        
        // Cambiar color según el valor
        if (validValue > 80) {
            circle.style.stroke = '#e74c3c'; // Rojo
        } else if (validValue > 60) {
            circle.style.stroke = '#f39c12'; // Naranja
        } else {
            circle.style.stroke = '#2ecc71'; // Verde
        }
    }
}

// Manejo mejorado de errores
function handleLoadError(error) {
    console.error('Error cargando métricas:', error);
    
    // Si es un abort, no hacer nada
    if (error.name === 'AbortError') return;
    
    MetricsManager.retryCount++;
    
    // Usar último dato válido si existe
    if (MetricsManager.lastValidData) {
        updateDisplay(MetricsManager.lastValidData);
    }
    
    // Reintentar si no se ha excedido el límite
    if (MetricsManager.retryCount < MetricsManager.maxRetries) {
        setTimeout(() => loadServerMetrics(), 5000 * MetricsManager.retryCount);
    } else {
        // Mostrar estado offline en todos los servidores
        for (let i = 1; i <= 3; i++) {
            const statusEl = document.getElementById(`server-status-${i}`);
            if (statusEl) {
                statusEl.className = 'server-status status-offline';
                statusEl.innerHTML = '<span class="pulse"></span> ERROR CONEXIÓN';
            }
        }
    }
}

// Toggle VMs mejorado
async function toggleVMs(serverNum, event) {
    event.stopPropagation();
    
    const container = document.getElementById(`vms-container-${serverNum}`);
    const card = container.closest('.server-card');
    
    if (container.classList.contains('show')) {
        container.classList.remove('show');
        card.classList.remove('expanded');
        MetricsManager.expandedServers[serverNum] = false;
    } else {
        container.classList.add('show');
        card.classList.add('expanded');
        MetricsManager.expandedServers[serverNum] = true;
        await loadVMsForServer(serverNum);
        // Cargar predicciones si está expandido
        if (CONFIG.enablePredictions) {
            loadPredictions(serverNum);
        }
    }
}

// Inicializar gráficos
function initCharts() {
    for (let i = 1; i <= 3; i++) {
        // CPU Chart
        const cpuCtx = document.getElementById(`cpu-chart-${i}`);
        if (cpuCtx) {
            MetricsManager.charts[`cpu-${i}`] = new Chart(cpuCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        borderColor: '#f39c12',
                        backgroundColor: 'rgba(243, 156, 18, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 2
                    }]
                },
                options: {
                    ...CONFIG.chartOptions,
                    scales: {
                        x: {
                            display: true,
                            grid: { color: 'rgba(255, 255, 255, 0.1)' },
                            ticks: { color: 'rgba(255, 255, 255, 0.5)', maxTicksLimit: 6 }
                        },
                        y: {
                            display: true,
                            grid: { color: 'rgba(255, 255, 255, 0.1)' },
                            ticks: { 
                                color: 'rgba(255, 255, 255, 0.5)',
                                callback: value => value + '%'
                            },
                            min: 0,
                            max: 100
                        }
                    }
                }
            });
        }
        
        // Memory Chart
        const memCtx = document.getElementById(`mem-chart-${i}`);
        if (memCtx) {
            MetricsManager.charts[`mem-${i}`] = new Chart(memCtx.getContext('2d'), {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4,
                        fill: true,
                        pointRadius: 2
                    }]
                },
                options: CONFIG.chartOptions
            });
        }
    }
}

// Actualizar tiempo de última actualización
function updateLastRefreshTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('es-ES');
    
    for (let i = 1; i <= 3; i++) {
        const el = document.getElementById(`last-update-${i}`);
        if (el) el.textContent = timeStr;
    }
}

// Toggle auto-refresh mejorado
function toggleAutoRefresh() {
    const icon = document.getElementById('auto-refresh-icon');
    const text = document.getElementById('auto-refresh-text');
    
    if (MetricsManager.isAutoRefreshing) {
        clearInterval(MetricsManager.autoRefreshInterval);
        icon.className = 'fas fa-play me-2';
        text.textContent = 'Auto-Actualización';
        MetricsManager.isAutoRefreshing = false;
    } else {
        MetricsManager.autoRefreshInterval = setInterval(loadServerMetrics, CONFIG.refreshInterval);
        icon.className = 'fas fa-pause me-2';
        text.textContent = 'Detener Auto';
        MetricsManager.isAutoRefreshing = true;
    }
}

// Inicialización mejorada
document.addEventListener('DOMContentLoaded', function() {
    console.log('Inicializando sistema de métricas...');
    
    // Inicializar charts
    initCharts();
    
    // Cargar datos iniciales
    loadServerMetrics();
    
    // Auto-refresh por defecto
    MetricsManager.autoRefreshInterval = setInterval(loadServerMetrics, CONFIG.refreshInterval);
    MetricsManager.isAutoRefreshing = true;
    
    // Pausar cuando la pestaña no está visible
    document.addEventListener('visibilitychange', function() {
        if (document.hidden && MetricsManager.isAutoRefreshing) {
            clearInterval(MetricsManager.autoRefreshInterval);
        } else if (!document.hidden && MetricsManager.isAutoRefreshing) {
            loadServerMetrics();
            MetricsManager.autoRefreshInterval = setInterval(loadServerMetrics, CONFIG.refreshInterval);
        }
    });
});

// Exportar para uso global
window.MetricsManager = MetricsManager;
window.loadServerMetrics = loadServerMetrics;
window.toggleVMs = toggleVMs;
window.toggleAutoRefresh = toggleAutoRefresh;

async function refreshVMmetrics() {
  try {
    const res = await fetch('/api/vms/metrics/');
    const json = await res.json();

    json.vms.forEach(vm => {
      const card = document.querySelector(
        `[data-vmid="${vm.vmid}"][data-node="${vm.node}"]`
      );
      if (!card) return;

      // Actualizar valores de métricas
      card.querySelector('.cpu-val').textContent = vm.cpu.toFixed(1) + '%';
      card.querySelector('.mem-val').textContent = vm.mem.toFixed(1) + '%';
      card.querySelector('.disk-val').textContent = vm.disk.toFixed(1) + ' GB';
      card.querySelector('.net-val').textContent =
        `${vm.net_in.toFixed(1)} / ${vm.net_out.toFixed(1)} MB`;

      // Cambiar color del estado (opcional)
      const statusEl = card.querySelector('.vm-status');
      if (statusEl) {
        statusEl.textContent = vm.status.toUpperCase();
        statusEl.className = 'vm-status ' + (vm.status === 'running' ? 'running' : 'stopped');
      }
    });
  } catch (err) {
    console.error('Error al actualizar métricas:', err);
  }
}

// Actualización cada 8 segundos
setInterval(refreshVMmetrics, 8000);
