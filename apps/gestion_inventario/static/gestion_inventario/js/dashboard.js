document.addEventListener('DOMContentLoaded', function () {
    // Inicializar Tooltips de Bootstrap 5
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl)
    })

    const isDarkMode = document.body.classList.contains('dark-mode');
    const labelColor = isDarkMode ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.7)';
    const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // LEER LAS URLS DESDE EL OBJETO GLOBAL QUE DEFINIREMOS EN EL HTML
    // Usamos optional chaining (?.) por seguridad si el objeto no existe
    const urlGraficoCategoria = window.dashboardConfig?.urlGraficoCategoria;
    const urlGraficoEstado = window.dashboardConfig?.urlGraficoEstado;

    if (!urlGraficoCategoria || !urlGraficoEstado) {
        console.error("Dashboard URLs not configured. Make sure window.dashboardConfig is set.");
        return;
    }

    // GRÁFICO 1: CATEGORÍAS
    const ctxCat = document.getElementById('graficoCategorias')?.getContext('2d');
    if (ctxCat) {
        fetch(urlGraficoCategoria)
            .then(r => r.json())
            .then(data => {
                new Chart(ctxCat, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: 'Cantidad',
                            data: data.values,
                            backgroundColor: 'rgba(54, 162, 235, 0.8)',
                            borderColor: 'rgba(54, 162, 235, 1)',
                            borderWidth: 1,
                            borderRadius: 4
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: gridColor }, ticks: { color: labelColor, font: { size: 11 } } },
                            y: { grid: { display: false }, ticks: { color: labelColor, autoSkip: false, font: { size: 11 } } }
                        }
                    }
                });
            })
            .catch(e => console.error("Error loading category chart:", e));
    }

    // GRÁFICO 2: ESTADOS
    const ctxEst = document.getElementById('graficoEstados')?.getContext('2d');
    if (ctxEst) {
        fetch(urlGraficoEstado)
            .then(r => r.json())
            .then(data => {
                new Chart(ctxEst, {
                    type: 'doughnut',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            data: data.values,
                            backgroundColor: [
                                '#e74c3c', 
                                '#2ecc71', 
                                '#f1c40f', 
                                '#95a5a6', 
                                '#3498db', 
                                '#9b59b6'
                            ],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: labelColor, padding: 15, usePointStyle: true, font: { size: 11 } }
                            }
                        },
                        cutout: '65%'
                    }
                });
            })
            .catch(e => console.error("Error loading status chart:", e));
    }
});