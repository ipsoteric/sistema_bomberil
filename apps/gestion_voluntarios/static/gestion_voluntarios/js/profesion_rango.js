    // --- LÓGICA VISUAL DE PESTAÑAS ---
    function openTab(tabId) {
        // Ocultar todos los contenidos
        document.querySelectorAll('.tab-content').forEach(tab => {
            tab.style.display = 'none';
            tab.classList.remove('active');
        });
        
        // Desactivar botones
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Mostrar seleccionado
        const selectedTab = document.getElementById(tabId);
        if (selectedTab) {
            selectedTab.style.display = 'block';
            selectedTab.classList.add('active');
        }

        // Activar botón
        const activeBtn = document.querySelector(`button[onclick="openTab('${tabId}')"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    }

    document.addEventListener('DOMContentLoaded', function() {
        const searchProfesion = document.getElementById('search-profesion');
        const searchCargo = document.getElementById('search-cargo');
        const filterTipoCargo = document.getElementById('filter-tipo-cargo');

        // --- 1. DETECTAR QUÉ PESTAÑA ABRIR ---
        const urlParams = new URLSearchParams(window.location.search);
        
        // Si hay búsqueda de RANGO, abrimos rangos. Si no, Profesiones.
        if (urlParams.has('q_cargo') || urlParams.has('tipo_cargo')) {
            openTab('rangos');
        } else {
            openTab('profesiones');
        }

        // --- 2. FUNCIÓN INTELIGENTE DE FILTRADO ---
        // Ahora recibe 'contexto' para saber qué limpiar
        function updateFilters(contexto) {
            const url = new URL(window.location.href);
            
            if (contexto === 'profesiones') {
                // Si estamos filtrando profesiones, aplicamos ese filtro...
                if (searchProfesion.value) url.searchParams.set('q_profesion', searchProfesion.value);
                else url.searchParams.delete('q_profesion');

                // ...Y BORRAMOS LOS FILTROS DE RANGOS para no confundir al sistema
                url.searchParams.delete('q_cargo');
                url.searchParams.delete('tipo_cargo');
            } 
            else if (contexto === 'rangos') {
                // Si estamos filtrando rangos, aplicamos esos filtros...
                if (searchCargo.value) url.searchParams.set('q_cargo', searchCargo.value);
                else url.searchParams.delete('q_cargo');

                if (filterTipoCargo.value && filterTipoCargo.value !== 'global') {
                    url.searchParams.set('tipo_cargo', filterTipoCargo.value);
                } else {
                    url.searchParams.delete('tipo_cargo');
                }

                // ...Y BORRAMOS EL FILTRO DE PROFESIONES
                url.searchParams.delete('q_profesion');
            }

            // Recargar página
            window.location.href = url.toString();
        }

        // --- ASIGNAR EVENTOS ---
        
        // Buscador Profesiones -> Contexto 'profesiones'
        if(searchProfesion) {
            searchProfesion.addEventListener('keyup', function(e) {
                if (e.key === 'Enter') updateFilters('profesiones');
            });
        }

        // Buscador Cargos -> Contexto 'rangos'
        if(searchCargo) {
            searchCargo.addEventListener('keyup', function(e) {
                if (e.key === 'Enter') updateFilters('rangos');
            });
        }

        // Filtro Tipo Cargo -> Contexto 'rangos'
        if(filterTipoCargo) {
            filterTipoCargo.addEventListener('change', function() {
                updateFilters('rangos');
            });
        }
    });
