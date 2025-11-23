document.addEventListener('DOMContentLoaded', function() {
            const estacionSelect = document.getElementById('estacion-filter');
            const rangoSelect = document.getElementById('rango-filter');
            const searchInput = document.getElementById('search-input');

            function aplicarFiltros() {
                const estacion = estacionSelect.value;
                const rango = rangoSelect.value;
                const busqueda = searchInput.value;

                const url = new URL(window.location.href);
                url.searchParams.set('estacion', estacion);
                url.searchParams.set('rango', rango);
                
                if (busqueda) {
                    url.searchParams.set('q', busqueda);
                } else {
                    url.searchParams.delete('q');
                }

                window.location.href = url.toString();
            }

            estacionSelect.addEventListener('change', aplicarFiltros);
            rangoSelect.addEventListener('change', aplicarFiltros);

            let timeout = null;
            searchInput.addEventListener('keyup', function(e) {
                clearTimeout(timeout);
                if (e.key === 'Enter') {
                    aplicarFiltros();
                } else {
                    // Pequeño retardo para buscar automáticamente al dejar de escribir
                    timeout = setTimeout(aplicarFiltros, 800);
                }
            });
        });