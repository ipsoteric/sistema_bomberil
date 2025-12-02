document.addEventListener('DOMContentLoaded', function() {
    
    // Función Matemática
    const calcularDV = (cuerpo) => {
        let suma = 0, mul = 2;
        for (let i = cuerpo.length - 1; i >= 0; i--) {
            suma += parseInt(cuerpo.charAt(i)) * mul;
            mul = mul === 7 ? 2 : mul + 1;
        }
        const res = 11 - (suma % 11);
        return res === 11 ? '0' : res === 10 ? 'K' : res.toString();
    };

    const widgets = document.querySelectorAll('.rut-widget-container');

    widgets.forEach(container => {
        const wrapper = container.querySelector('.rut-widget-wrapper');
        const inputCuerpo = container.querySelector('.rut-cuerpo');
        const inputDv = container.querySelector('.rut-dv');
        
        // Iconos reales
        const iconValid = container.querySelector('.icon-valid');
        const iconInvalid = container.querySelector('.icon-invalid');

        const actualizarEstado = () => {
            // 1. Limpieza inicial
            let cuerpo = inputCuerpo.value.replace(/\D/g, '');
            
            // Formateo visual (puntos)
            if (cuerpo.length > 0) {
                inputCuerpo.value = new Intl.NumberFormat('es-CL').format(cuerpo);
            }

            // 2. Lógica de Cálculo
            if (cuerpo.length < 1) {
                // Si está vacío, limpiamos todo
                inputDv.value = "";
                wrapper.classList.remove('is-valid', 'is-invalid');
                iconValid.classList.add('d-none');
                iconInvalid.classList.add('d-none');
                return;
            }

            // Calculamos siempre (Usuario no puede intervenir)
            const dvCalculado = calcularDV(cuerpo);
            
            // 3. Asignación Automática
            inputDv.value = dvCalculado;

            // 4. Validación Visual
            // Si hay al menos 7 dígitos (RUT real mínimo), damos el visto bueno
            if (cuerpo.length >= 7) {
                wrapper.classList.add('is-valid');
                wrapper.classList.remove('is-invalid');
                iconValid.classList.remove('d-none');
                iconInvalid.classList.add('d-none');
            } else {
                // Aún escribiendo... quitamos validación visual fuerte
                wrapper.classList.remove('is-valid', 'is-invalid');
                iconValid.classList.add('d-none');
                iconInvalid.classList.add('d-none');
            }
        };

        // Escuchar input en el cuerpo
        inputCuerpo.addEventListener('input', actualizarEstado);

        // Inicializar (por si viene con datos del servidor al editar)
        actualizarEstado();
    });
});