document.addEventListener('DOMContentLoaded', function () {

    // --- LÓGICA PARA LOS MENÚS DESPLEGABLES ---
    
    // Escucha clics en todos los botones de acciones
    document.querySelectorAll('.boton-menu-acciones').forEach(button => {
        button.addEventListener('click', function (event) {
            // Evita que el clic se propague a otros elementos (como el 'window')
            event.stopPropagation();
            
            // Encuentra el menú asociado a ESTE botón
            const menu = this.nextElementSibling;
            
            // Cierra cualquier otro menú que pueda estar abierto
            document.querySelectorAll('.menu-acciones-usuarios.visible').forEach(openMenu => {
                if (openMenu !== menu) {
                    openMenu.classList.remove('visible');
                }
            });
            
            // Muestra u oculta el menú actual
            menu.classList.toggle('visible');
        });
    });
    
    // Cierra los menús si se hace clic en cualquier otra parte de la página
    window.addEventListener('click', function () {
        document.querySelectorAll('.menu-acciones-usuarios.visible').forEach(menu => {
            menu.classList.remove('visible');
        });
    });
  
})
