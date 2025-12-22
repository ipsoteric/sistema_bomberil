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
    function getData(id) {
        return JSON.parse(document.getElementById(id).textContent);
    }

    // 2. Obtenemos los valores pasados desde Django
    var dataDisponible = getData('data-disponible');
    var dataPrestamo = getData('data-prestamo');
    var dataPreparacion = getData('data-preparacion');
    var dataTransito = getData('data-transito');
    var dataRevision = getData('data-revision');
    var dataReparacion = getData('data-reparacion');

    // Configuración del Gráfico (Doughnut Chart)
    var ctx = document.getElementById("myPieChart");

    // Verificar si existe el canvas para evitar errores en otras páginas
    if (ctx) {
    var myPieChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: [
                "Disponible", 
                "En Préstamo", 
                "En Preparación", 
                "En Tránsito", 
                "Pendiente Revisión", 
                "En Reparación"
            ],
            datasets: [{
                data: [
                  dataDisponible, 
                  dataPrestamo, 
                  dataPreparacion, 
                  dataTransito, 
                  dataRevision, 
                  dataReparacion
                ],
                backgroundColor: [
                  '#1cc88a', // Disponible (Verde)
                  '#4e73df', // Préstamo (Azul)
                  '#36b9cc', // Preparación (Cyan/Teal)
                  '#f6c23e', // Tránsito (Amarillo/Naranja)
                  '#858796', // Revisión (Gris)
                  '#e74a3b'  // Reparación (Rojo)
                ],
                hoverBackgroundColor: [
                  '#17a673', 
                  '#2e59d9', 
                  '#2c9faf', 
                  '#dda20a', 
                  '#60616f', 
                  '#be2617'
                ],
                hoverBorderColor: "rgba(234, 236, 244, 1)",
            }],
        },
        options: {
            maintainAspectRatio: false,
            tooltips: {
                backgroundColor: "rgb(255,255,255)",
                bodyFontColor: "#858796",
                borderColor: '#dddfeb',
                borderWidth: 1,
                xPadding: 15,
                yPadding: 15,
                displayColors: false,
                caretPadding: 10,
            },
            legend: {
                display: false // Ocultamos la leyenda por defecto para usar la HTML personalizada si quieres
            },
            cutoutPercentage: 80,
        },
    });
    }
});