/* Archivo: dashboard.js */

// Este script se ejecuta cuando el contenido del DOM (la página) se ha cargado.
document.addEventListener("DOMContentLoaded", function() {
    
    /* NOTA: Los datos 'dataRangos' y 'dataProfesiones' son de EJEMPLO. */

    
    // --- Gráfico 1: Voluntarios por Rango (Barras) ---
    const ctxRango = document.getElementById('graficoVoluntariosPorRango');
    
    // Datos de EJEMPLO
    const dataRangos = {
        labels: ['Aspirante', 'Vol. Activo', 'Vol. Honorario', 'Director', 'Capitán'],
        data: [10, 25, 15, 3, 5]
    };

    // Comprueba si el elemento canvas existe antes de crear el gráfico
    if (ctxRango) {
        new Chart(ctxRango, {
            type: 'bar',
            data: {
                labels: dataRangos.labels,
                datasets: [{
                    label: '# de Voluntarios',
                    data: dataRangos.data,
                    backgroundColor: 'rgba(54, 162, 235, 0.6)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                maintainAspectRatio: false, // Permite que el gráfico se ajuste al contenedor
                scales: {
                    y: {
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        display: false // Oculta la leyenda (ya es obvio por el título)
                    }
                }
            }
        });
    }

    // --- Gráfico 2: Voluntarios por Profesión (Torta/Doughnut) ---
    const ctxProfesion = document.getElementById('graficoVoluntariosPorProfesion');
    
    // Datos de EJEMPLO
    const dataProfesiones = {
        labels: ['Ingeniero', 'Estudiante', 'Profesor', 'Comerciante', 'Otro'],
        data: [12, 18, 7, 9, 12]
    };

    // Comprueba si el elemento canvas existe antes de crear el gráfico
    if (ctxProfesion) {
        new Chart(ctxProfesion, {
            type: 'doughnut',
            data: {
                labels: dataProfesiones.labels,
                datasets: [{
                    label: 'Profesiones',
                    data: dataProfesiones.data,
                    backgroundColor: [
                        'rgba(255, 99, 132, 0.7)',
                        'rgba(54, 162, 235, 0.7)',
                        'rgba(255, 206, 86, 0.7)',
                        'rgba(75, 192, 192, 0.7)',
                        'rgba(153, 102, 255, 0.7)'
                    ],
                }]
            },
            options: {
                maintainAspectRatio: false, // Permite que el gráfico se ajuste al contenedor
                plugins: {
                    legend: {
                        position: 'bottom', // Mueve la leyenda abajo
                    }
                }
            }
        });
    }

});