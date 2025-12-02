document.addEventListener('DOMContentLoaded', function() {
    const inputsTelefono = document.querySelectorAll('.telefono-widget-container input');

    inputsTelefono.forEach(input => {
        const container = input.closest('.telefono-widget-container');
        const wrapper = container.querySelector('.rut-widget-wrapper');
        const iconValid = container.querySelector('.icon-valid');
        const iconInvalid = container.querySelector('.icon-invalid');

        const validarTelefono = () => {
            // 1. OBTENER VALOR LIMPIO (Solo números)
            let raw = input.value.replace(/\D/g, '');
            
            // 2. FORMATEO SIMPLE (9 12345678)
            // Solo si hay más de 1 dígito, insertamos el espacio después del primero
            let formatted = raw;
            if (raw.length > 1) {
                formatted = raw.substring(0, 1) + ' ' + raw.substring(1);
            }
            
            // Aplicamos el valor formateado
            // (Esto evita que se bloquee el borrado)
            input.value = formatted;

            // 3. VALIDACIÓN
            // Limpieza visual
            wrapper.classList.remove('is-valid', 'is-invalid');
            iconValid.classList.add('d-none');
            iconInvalid.classList.add('d-none');

            if (raw.length === 0) return; // Vacío = Neutro

            // Regla: Debe empezar con 9 y tener 9 dígitos
            if (raw.length === 9 && raw.startsWith('9')) {
                wrapper.classList.add('is-valid');
                iconValid.classList.remove('d-none');
            } else {
                // Si ya escribió 9 y está mal, o si empieza con algo que no es 9
                if (raw.length >= 9 || (raw.length > 0 && !raw.startsWith('9'))) {
                    wrapper.classList.add('is-invalid');
                    iconInvalid.classList.remove('d-none');
                }
            }
        };

        

        input.addEventListener('input', validarTelefono);
        // Validar al inicio por si viene con datos
        validarTelefono();
    });
});