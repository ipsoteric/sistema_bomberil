/* static/js/bomberil_forms.js */
document.addEventListener('DOMContentLoaded', function() {
    
    const Validator = {
        // --- REGLAS DE VALIDACIÓN ---
        rules: {
            required: (val) => val.trim().length > 0,
            email: (val) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val),
            integer: (val) => /^\d+$/.test(val),
            'letters-only': (val) => /^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]*$/.test(val),
            phone: (val) => /^(\+?56)?\s?(\d{9}|\d{8})$/.test(val.replace(/\s/g, '')),
            min: (val, min) => val.length >= parseInt(min),
            max: (val, max) => val.length <= parseInt(max),
            date: (val, input) => {
                if (!val) return true;
                const min = input.dataset.dateMin;
                const max = input.dataset.dateMax;
                if (min && val < min) return false;
                if (max && val > max) return false;
                return true;
            }
        },
        // --- FORMATEADORES ---
        formatters: {
            capitalize: (val) => {
                return val.toLowerCase().replace(/\b\w/g, l => l.toUpperCase());
            },
            phone: (val) => val // El widget de teléfono maneja su propio formato
        },
        // --- INICIALIZACIÓN ---
        init: function() {
            // 1. Configurar Inputs Individuales
            const selector = 'input[data-rule-required], input[data-rule-type], input[type="date"], textarea[data-rule-required]';
            const inputs = document.querySelectorAll(selector);
            
            inputs.forEach(input => {
                // IGNORAR WIDGETS ESPECIALES (Ellos tienen su propio JS)
                if (input.closest('.rut-widget-container') || input.closest('.telefono-widget-container')) return;

                this.wrapInput(input);
                
                // Eventos
                input.addEventListener('input', (e) => this.handleInput(e.target));
                input.addEventListener('blur', (e) => this.handleBlur(e.target));
                
                // Validar al cargar si tiene valor
                if(input.value) this.validate(input);
            });
        },
        // --- LÓGICA DE ENVÍO (GATEKEEPER) ---
        handleSubmit: function(e, inputs) {
            let formIsValid = true;
            let firstErrorInput = null;

            // 1. Validar Inputs Genéricos (Nombre, Email, etc)
            inputs.forEach(input => {
                if (input.closest('.rut-widget-container') || input.closest('.telefono-widget-container')) return;
                
                // Forzamos validación visual
                this.validate(input);
                
                // Chequeamos si quedó inválido
                if (input.classList.contains('is-invalid')) {
                    formIsValid = false;
                    if (!firstErrorInput) firstErrorInput = input;
                }
            });

            // 2. Validar Widgets Especiales (RUT y Teléfono)
            // Buscamos si alguno de los widgets tiene la clase .is-invalid o si es requerido y está vacío
            
            // RUT
            document.querySelectorAll('.rut-widget-container').forEach(widget => {
                const wrapper = widget.querySelector('.rut-widget-wrapper');
                const inputCuerpo = widget.querySelector('.rut-cuerpo');
                
                // Si está inválido O (es requerido, está vacío y no tiene estado válido)
                // Nota: Asumimos que si es requerido y está vacío, el usuario no interactuó.
                // Aquí simplificamos buscando la clase de error que pone rut_widget.js
                if (wrapper.classList.contains('is-invalid')) {
                    formIsValid = false;
                    if (!firstErrorInput) firstErrorInput = inputCuerpo;
                }
            });

            // TELÉFONO
            document.querySelectorAll('.telefono-widget-container').forEach(widget => {
                const wrapper = widget.querySelector('.rut-widget-wrapper');
                const input = widget.querySelector('input');
                 if (wrapper.classList.contains('is-invalid')) {
                    formIsValid = false;
                    if (!firstErrorInput) firstErrorInput = input;
                }
            });


            // 3. DECISIÓN FINAL
            if (!formIsValid) {
                e.preventDefault(); // DETIENE EL ENVÍO AL SERVIDOR
                e.stopPropagation();
                
                // UX: Scrollear hacia el primer error y hacerle foco
                if (firstErrorInput) {
                    firstErrorInput.focus();
                    firstErrorInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
                
                // Opcional: Mostrar una alerta toast o mensaje global
                console.warn("Formulario bloqueado por errores de validación.");
            }
        },
        wrapInput: function(input) {
            // Evitar doble wrap
            if (input.parentNode.classList.contains('bomberil-input-wrapper')) return;

            const wrapper = document.createElement('div');
            wrapper.className = 'bomberil-input-wrapper'; // El CSS maneja la posición relativa
            input.parentNode.insertBefore(wrapper, input);
            wrapper.appendChild(input);

            // Inyectar Iconos
            const iconContainer = document.createElement('div');
            iconContainer.className = 'bomberil-feedback-icon';
            iconContainer.innerHTML = `
                <i class="fas fa-check-circle text-success d-none icon-valid"></i>
                <i class="fas fa-exclamation-circle text-danger d-none icon-invalid"></i>
            `;
            wrapper.appendChild(iconContainer);
        },
        handleInput: function(input) {
            const transform = input.dataset.transform;
            if (transform && this.formatters[transform]) {
                const start = input.selectionStart;
                input.value = this.formatters[transform](input.value);
                input.setSelectionRange(start, start);
            }
            this.validate(input);
        },
        handleBlur: function(input) {
            this.validate(input, true);
        },
        validate: function(input, isBlur = false) {
            const value = input.value;
            let isValid = true;
            let errorMsg = "";

            // 1. Si está vacío y no es requerido -> Estado Neutro
            if (value.length === 0 && !input.dataset.ruleRequired) {
                this.updateUI(input, 'neutro');
                return;
            }

            // 2. Validaciones
            if (input.dataset.ruleRequired && value.trim() === "") {
                isValid = false;
                errorMsg = "Requerido";
            }
            
            if (isValid && input.dataset.ruleType && value.length > 0) {
                const type = input.dataset.ruleType;
                if (this.rules[type] && !this.rules[type](value, input)) {
                    isValid = false;
                    errorMsg = "Formato inválido";
                }
            }
            
            if (isValid && input.dataset.ruleMin) {
                if (!this.rules.min(value, input.dataset.ruleMin)) isValid = false;
            }

            this.updateUI(input, isValid ? 'valido' : 'invalido', errorMsg);
        },
        updateUI: function(input, estado, msg = "") {
            const wrapper = input.closest('.bomberil-input-wrapper');
            if (!wrapper) return;

            const iconValid = wrapper.querySelector('.icon-valid');
            const iconInvalid = wrapper.querySelector('.icon-invalid');
            
            // Limpiar estados
            input.classList.remove('is-valid', 'is-invalid');
            iconValid.classList.add('d-none');
            iconInvalid.classList.add('d-none');

            if (estado === 'valido') {
                input.classList.add('is-valid');
                iconValid.classList.remove('d-none');
            } else if (estado === 'invalido') {
                input.classList.add('is-invalid');
                iconInvalid.classList.remove('d-none');
            }
        }
    };
    Validator.init();
});