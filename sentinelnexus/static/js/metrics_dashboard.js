// SentinelNexus Metrics Dashboard JS

// Variables globales
let charts = {};
let vmCache = {};
let expandedServers = {};

const chartConfig = {
  type: "line",
  options: {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index',
      intersect: false,
    },
    plugins: { 
        legend: { display: true, labels: { color: 'white' } },
        tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      x: { display: true, ticks: { color: "rgba(255, 255, 255, 0.5)", maxTicksLimit: 8 }, grid: { color: "rgba(255, 255, 255, 0.1)" } },
      y: { display: true, ticks: { color: "rgba(255, 255, 255, 0.5)", callback: function (value) { return value + "%"; } }, grid: { color: "rgba(255, 255, 255, 0.1)" }, min: 0, max: 100 }
    }
  }
};

function initCharts() {
  for (let i = 1; i <= 4; i++) {
      // CPU Chart con predicción
      const cpuCtx = document.getElementById(`cpu-chart-${i}`);
      if(cpuCtx) {
          charts[`cpu-${i}`] = new Chart(cpuCtx.getContext("2d"), {
              ...chartConfig,
              data: { 
                  labels: [], 
                  datasets: [
                      { 
                          label: 'Historial', 
                          data: [], 
                          borderColor: "#f39c12", 
                          backgroundColor: "rgba(243, 156, 18, 0.1)", 
                          tension: 0.4, 
                          fill: true 
                      },
                      { 
                          label: 'Predicción', 
                          data: [], 
                          borderColor: "#e67e22", 
                          borderDash: [5, 5],
                          backgroundColor: "rgba(230, 126, 34, 0.0)", 
                          tension: 0.4, 
                          fill: false,
                          pointRadius: 0
                      }
                  ] 
              }
          });
      }
      
      // RAM Chart con predicción
      const memCtx = document.getElementById(`mem-chart-${i}`);
      if(memCtx) {
          charts[`mem-${i}`] = new Chart(memCtx.getContext("2d"), {
              ...chartConfig,
              data: { 
                  labels: [], 
                  datasets: [
                      { 
                          label: 'Historial', 
                          data: [], 
                          borderColor: "#3498db", 
                          backgroundColor: "rgba(52, 152, 219, 0.1)", 
                          tension: 0.4, 
                          fill: true 
                      },
                      { 
                          label: 'Predicción', 
                          data: [], 
                          borderColor: "#2980b9", 
                          borderDash: [5, 5],
                          backgroundColor: "rgba(41, 128, 185, 0.0)", 
                          tension: 0.4, 
                          fill: false,
                          pointRadius: 0
                      }
                  ] 
              }
          });
      }
  }
}

function updateCircularProgress(elementId, value) {
  const circle = document.getElementById(elementId);
  const text = document.getElementById(elementId.replace("circle", "text"));
  if (circle && text) {
    const circumference = 2 * Math.PI * 54;
    const offset = circumference - (value / 100) * circumference;
    try { circle.style.strokeDashoffset = offset; } catch(e){}
    if(text) text.textContent = Math.round(value) + "%";
  }
}

async function loadServerMetrics() {
  try {
    // Cargar Métricas y Predicciones en paralelo
    const [metricsRes, ...predictionsRes] = await Promise.all([
        fetch("/api/metrics/"),
        // Fetch predictions for server 1, 2, 3 (assuming max 3 servers for now or dynamic)
        fetch("/api/predictions/1/"),
        fetch("/api/predictions/2/"),
        fetch("/api/predictions/3/")
    ]);

    const data = await metricsRes.json();
    const predictions = [];
    
    // Procesar respuestas de predicción
    for(const res of predictionsRes) {
        try {
            if(res.ok) predictions.push(await res.json());
            else predictions.push(null);
        } catch(e) { predictions.push(null); }
    }

    if (data.success && data.servers) {
      data.servers.forEach((server, index) => {
        const serverNum = index + 1;
        const predData = predictions[index];

        // Actualizar UI básica
        updateServerUI(server, serverNum);

        // Actualizar Gráficos con Merge de Historial + Predicción
        if (server.history && server.history.timestamps.length > 0) {
          updateChartWithPrediction(
              `cpu-${serverNum}`, 
              server.history.timestamps, 
              server.history.cpu, 
              predData?.predictions?.cpu
          );
          updateChartWithPrediction(
              `mem-${serverNum}`, 
              server.history.timestamps, 
              server.history.memory, 
              predData?.predictions?.memory
          );
        }
      });
    }
  } catch (error) { console.error("Error loading metrics:", error); }
}

function updateServerUI(server, serverNum) {
    const nameEl = document.getElementById(`server-name-${serverNum}`);
    if(nameEl) nameEl.textContent = server.name;

    const statusElement = document.getElementById(`server-status-${serverNum}`);
    if(statusElement) {
        if (server.online) {
          statusElement.className = "server-status status-online";
          statusElement.innerHTML = '<span class="pulse"></span> ONLINE';
        } else {
          statusElement.className = "server-status status-offline";
          statusElement.innerHTML = '<span class="pulse"></span> OFFLINE';
        }
    }
    updateCircularProgress(`cpu-circle-${serverNum}`, server.metrics.cpu.usage || 0);
    updateCircularProgress(`mem-circle-${serverNum}`, server.metrics.memory.percent || 0);
    updateCircularProgress(`disk-circle-${serverNum}`, server.metrics.disk.percent || 0);
    
    const elCores = document.getElementById(`cores-${serverNum}`);
    if(elCores) elCores.textContent = server.metrics.cpu.cores || "--";
    const elRam = document.getElementById(`ram-total-${serverNum}`);
    if(elRam) elRam.textContent = server.metrics.memory.total_gb ? `${server.metrics.memory.total_gb} GB` : "--";
    const elStorage = document.getElementById(`storage-${serverNum}`);
    if(elStorage) elStorage.textContent = server.metrics.disk.total_tb ? `${server.metrics.disk.total_tb.toFixed(2)} TB` : "--";
    const elVms = document.getElementById(`vms-${serverNum}`);
    if(elVms) elVms.textContent = server.vms?.active || "0";
    const elUptime = document.getElementById(`uptime-${serverNum}`);
    if(elUptime) elUptime.textContent = server.uptime || "--";
    
    const netLoad = Math.min(server.metrics.network?.out_mbps || 0, 100);
    const netCircle = document.getElementById(`net-circle-${serverNum}`);
    if(netCircle) {
         const circumference = 2 * Math.PI * 54;
         const offset = circumference - (netLoad / 100) * circumference;
         netCircle.style.strokeDashoffset = offset;
    }
    const netText = document.getElementById(`net-text-${serverNum}`);
    if (netText) netText.textContent = `${Math.round(netLoad)}%`;
    const netMbpsText = document.getElementById(`net-mbps-${serverNum}`);
    if (netMbpsText) netMbpsText.textContent = `${(server.metrics.network?.out_mbps || 0).toFixed(1)} Mbps`;
}

function updateChartWithPrediction(chartId, histLabels, histData, predObj) {
    if (!charts[chartId]) return;
    
    let finalLabels = [...histLabels];
    let finalHistData = [...histData];
    let finalPredData = new Array(histData.length).fill(null); // Relleno null para parte histórica
    
    // Conectar el último punto histórico con el primero predicho
    if (histData.length > 0) {
        finalPredData[finalPredData.length - 1] = histData[histData.length - 1];
    }

    if (predObj && predObj.labels && predObj.data) {
        // Agregar etiquetas y datos de predicción
        finalLabels = finalLabels.concat(predObj.labels);
        finalPredData = finalPredData.concat(predObj.data);
        
        // El dataset histórico necesita nulls para la parte futura
         const futureNulls = new Array(predObj.data.length).fill(null);
         finalHistData = finalHistData.concat(futureNulls);
    }

    charts[chartId].data.labels = finalLabels;
    charts[chartId].data.datasets[0].data = finalHistData;
    charts[chartId].data.datasets[1].data = finalPredData;
    charts[chartId].update();
}

function toggleVMs(serverNum, event) {
  event.stopPropagation();
  const container = document.getElementById(`vms-container-${serverNum}`);
  if(!container) return;
  const card = container.closest(".server-card");
  if (container.classList.contains("show")) {
    container.classList.remove("show"); card.classList.remove("expanded"); expandedServers[serverNum] = false;
  } else {
    container.classList.add("show"); card.classList.add("expanded"); expandedServers[serverNum] = true; loadVMsForServer(serverNum);
  }
}

async function loadVMsForServer(serverNum) {
  try {
    if (vmCache[serverNum]) renderVMs(serverNum, vmCache[serverNum]);
    const response = await fetch(`/api/server/${serverNum}/vms/`);
    const data = await response.json();
    if (data.success && data.vms) {
      vmCache[serverNum] = data.vms;
      renderVMs(serverNum, data.vms);
    } else {
       renderVMs(serverNum, []);
    }
  } catch (error) { console.error(error); }
}

function renderVMs(serverNum, vms) {
  const grid = document.getElementById(`vm-grid-${serverNum}`);
  if (!grid) return;
  grid.innerHTML = "";
  vms.forEach((vm) => {
    grid.appendChild(createVMCard(vm));
    setTimeout(() => { createVMChart(vm.id, vm); }, 100);
  });
  const activeVMs = vms.filter((vm) => vm.status === "running").length;
  const elVms = document.getElementById(`vms-${serverNum}`);
  if(elVms) elVms.textContent = activeVMs;
}

function createVMCard(vm) {
  const card = document.createElement("div");
  card.className = "vm-card";
  const statusIcon = vm.status === "running" ? '<i class="fas fa-play-circle me-1"></i>ON' : '<i class="fas fa-stop-circle me-1"></i>OFF';
  card.innerHTML = `
      <div class="vm-header">
          <div><div class="vm-name"><i class="fas fa-server me-2"></i>${vm.name}</div><small style="color:rgba(255,255,255,0.5)">ID:${vm.vmid}</small></div>
          <span class="vm-status ${vm.status}">${statusIcon}</span>
      </div>
      <div class="vm-metrics">
          <div class="vm-metric"><div class="vm-metric-value" style="color:#f39c12">${vm.cpu}%</div><div class="vm-metric-label">CPU</div></div>
          <div class="vm-metric"><div class="vm-metric-value" style="color:#3498db">${vm.memory}%</div><div class="vm-metric-label">RAM</div></div>
      </div>
      <div class="vm-chart"><canvas id="chart-${vm.id}"></canvas></div>
      <div class="vm-actions"><button class="vm-btn-console" onclick="openVMConsole('${vm.vmid}')"><i class="fas fa-terminal"></i></button></div>
  `;
  return card;
}

function createVMChart(vmId, vmData) {
  const ctx = document.getElementById(`chart-${vmId}`);
  if (!ctx) return;
  // Destruir si existe (importante para recargas)
  // if(vmCharts[vmId]) vmCharts[vmId].destroy(); // No tenemos vmCharts global expuesto aqui facil, pero podemos ignorar o recrear.
  
  new Chart(ctx.getContext("2d"), {
    type: "line", data: { labels: ["","","","","",""], datasets: [{ data: [vmData.cpu, vmData.cpu, vmData.cpu], borderColor: "#f39c12", fill: false, pointRadius: 0 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { display: false, min: 0, max: 100 } } }
  });
}

function openVMConsole(vmid) { window.open(`/vm/${vmid}/console/`, "_blank", "width=800,height=600"); }

document.addEventListener("DOMContentLoaded", function () {
  initCharts();
  loadServerMetrics();
  setInterval(() => { loadServerMetrics(); }, 30000);
});
