document.addEventListener('DOMContentLoaded', function() {
    const inputPass = document.querySelector('.input-new-password');
    const box = document.getElementById('password-feedback-box');
    
    // Si no estamos en la página correcta, salir
    if (!inputPass || !box) return;

    // Elementos de la lista
    const reqs = {
        length: document.getElementById('req-length'),
        upper: document.getElementById('req-upper'),
        lower: document.getElementById('req-lower'),
        number: document.getElementById('req-number'),
        symbol: document.getElementById('req-symbol')
    };

    // 1. Mostrar caja al entrar
    inputPass.addEventListener('focus', () => {
        box.classList.remove('d-none');
    });

    // 2. Lógica de validación en tiempo real
    inputPass.addEventListener('input', function() {
        const val = inputPass.value;

        // Función helper para pintar verde/rojo
        const setStatus = (el, isValid) => {
            const icon = el.querySelector('i');
            if (isValid) {
                el.classList.remove('text-muted', 'text-danger');
                el.classList.add('text-success', 'fw-bold');
                icon.classList.remove('far', 'fa-circle');
                icon.classList.add('fas', 'fa-check-circle');
            } else {
                el.classList.remove('text-success', 'fw-bold');
                el.classList.add('text-muted'); // O text-danger si prefieres ser más agresivo
                icon.classList.remove('fas', 'fa-check-circle');
                icon.classList.add('far', 'fa-circle');
            }
        };

        // --- REGLAS (Coinciden con settings.py) ---
        setStatus(reqs.length, val.length >= 12);
        setStatus(reqs.upper, /[A-Z]/.test(val));
        setStatus(reqs.lower, /[a-z]/.test(val));
        setStatus(reqs.number, /\d/.test(val));
        // Símbolos permitidos
        setStatus(reqs.symbol, /[!@#$%^&*(),.?":{}|<>]/.test(val));
    });

    // 3. Confirmación de contraseña (Bonus visual)
    const inputConfirm = document.getElementById('id_new_password2'); // ID estándar de Django
    const matchFeedback = document.getElementById('match-feedback');

    if (inputConfirm) {
        inputConfirm.addEventListener('input', function() {
            if (inputConfirm.value.length === 0) {
                matchFeedback.classList.add('d-none');
                return;
            }

            matchFeedback.classList.remove('d-none');
            if (inputConfirm.value === inputPass.value) {
                matchFeedback.innerText = "Las contraseñas coinciden";
                matchFeedback.className = "text-xs fw-bold mt-1 text-success";
            } else {
                matchFeedback.innerText = "Las contraseñas no coinciden";
                matchFeedback.className = "text-xs fw-bold mt-1 text-danger";
            }
        });
    }
});