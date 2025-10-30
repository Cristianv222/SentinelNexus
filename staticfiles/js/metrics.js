// metrics.js - Manejo de métricas en tiempo real

let cpuChart, memoryChart;

// Función principal para cargar métricas
async function loadMetrics() {
    try {
        const response = await fetch('/api/metrics/');
        const data = await response.json();
        
        if (data.success) {
            // Actualizar valores en los medidores circulares
            updateGauges(data.server_comparison);
            
            // Actualizar gráficos
            updateCharts(data);
            
            // Actualizar estado
            updateStatus(true);
            
            // Actualizar timestamp
            document.getElementById('last-update').textContent = 
                new Date().toLocaleTimeString();
        }
    } catch (error) {
        console.error('Error cargando métricas:', error);
        updateStatus(false);
    }
}

// Actualizar medidores
function updateGauges(serverData) {
    if (serverData.cpu && serverData.cpu.length > 0) {
        // Actualizar CPU
        const cpuEl = document.querySelector('.col-md-3:nth-child(1) h2');
        if (cpuEl) cpuEl.textContent = serverData.cpu[0].toFixed(1) + '%';
        
        // Actualizar Memoria
        const memEl = document.querySelector('.col-md-3:nth-child(2) h2');
        if (memEl) memEl.textContent = serverData.memory[0].toFixed(1) + '%';
        
        // Actualizar Disco
        const diskEl = document.querySelector('.col-md-3:nth-child(3) h2');
        if (diskEl) diskEl.textContent = serverData.disk[0].toFixed(1) + '%';
    }
}

// Actualizar gráficos Chart.js
function updateCharts(data) {
    const ctx1 = document.getElementById('cpuHistoryChart');
    const ctx2 = document.getElementById('memoryHistoryChart');
    
    if (ctx1 && !cpuChart) {
        cpuChart = new Chart(ctx1.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.timestamps,
                datasets: [{
                    label: 'CPU %',
                    data: data.cpu_data,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    } else if (cpuChart) {
        cpuChart.data.labels = data.timestamps;
        cpuChart.data.datasets[0].data = data.cpu_data;
        cpuChart.update();
    }
    
    if (ctx2 && !memoryChart) {
        memoryChart = new Chart(ctx2.getContext('2d'), {
            type: 'line',
            data: {
                labels: data.timestamps,
                datasets: [{
                    label: 'Memoria %',
                    data: data.memory_data,
                    borderColor: 'rgb(54, 162, 235)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                }
            }
        });
    } else if (memoryChart) {
        memoryChart.data.labels = data.timestamps;
        memoryChart.data.datasets[0].data = data.memory_data;
        memoryChart.update();
    }
}

// Actualizar estado
function updateStatus(isOnline) {
    const badge = document.querySelector('.badge');
    if (badge) {
        if (isOnline) {
            badge.classList.remove('bg-danger');
            badge.classList.add('bg-success');
            badge.textContent = 'ONLINE';
        } else {
            badge.classList.remove('bg-success');
            badge.classList.add('bg-danger');
            badge.textContent = 'OFFLINE';
        }
    }
}

// Inicializar al cargar
document.addEventListener('DOMContentLoaded', function() {
    loadMetrics();
    // Actualizar cada 30 segundos
    setInterval(loadMetrics, 30000);
});