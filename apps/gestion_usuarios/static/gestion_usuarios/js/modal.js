document.addEventListener('DOMContentLoaded', function () {

    // --- LÓGICA PARA EL MODAL DE DESACTIVAR USUARIO ---
    const modalDesactivarUsuarioEl = document.getElementById('ModalDesactivarUsuario');
    
    // Si el elemento del modal existe, configuramos su lógica
    if (modalDesactivarUsuarioEl) {
        const modalBootstrapDesactivar = new bootstrap.Modal(modalDesactivarUsuarioEl);
        const formDesactivarUsuario = document.getElementById('formDesactivarUsuario');

        document.querySelectorAll('.boton-desactivar-usuario').forEach(boton => {
            boton.addEventListener('click', function () {
                const urlAccion = this.dataset.formAction;

                if (formDesactivarUsuario && urlAccion) {
                    formDesactivarUsuario.action = urlAccion;
                } else {
                    console.error("No se encontró el formulario o la URL en el data-attribute.");
                }

                modalBootstrapDesactivar.show();
            });
        });
    } else {
        // Este console.log es útil para depurar si el modal no estuviera en la página
        console.log("El modal #ModalDesactivarUsuario no se encuentra en esta página.");
    }

    // --- LÓGICA PARA EL MODAL DE ACTIVAR USUARIO ---
    const modalActivarUsuarioEl = document.getElementById('ModalActivarUsuario');

    // Si el elemento del modal existe, configuramos su lógica
    if (modalActivarUsuarioEl) {
        // Corregido: Usar la variable correcta
        const modalBootstrapActivar = new bootstrap.Modal(modalActivarUsuarioEl); 
        // Corregido: Asumimos que el formulario de activar tiene un ID diferente
        const formActivarUsuario = document.getElementById('formActivarUsuario'); 

        // Corregido: Asumimos que los botones de activar tienen una clase diferente
        document.querySelectorAll('.boton-activar-usuario').forEach(boton => { 
            boton.addEventListener('click', function () {
                const urlAccion = this.dataset.formAction;

                if (formActivarUsuario && urlAccion) {
                    formActivarUsuario.action = urlAccion;
                } else {
                    console.error("No se encontró el formulario o la URL en el data-attribute.");
                }

                modalBootstrapActivar.show();
            });
        });
    } else {
        console.log("El modal #ModalActivarUsuario no se encuentra en esta página.");
    }

});