function openTab(tabName) {
    // Oculta todos los contenidos de las pestañas
    const tabs = document.getElementsByClassName("tab-content");
    for (let i = 0; i < tabs.length; i++) {
        tabs[i].style.display = "none";
    }

    // Desactiva todos los botones de las pestañas
    const tabBtns = document.getElementsByClassName("tab-btn");
    for (let i = 0; i < tabBtns.length; i++) {
        tabBtns[i].classList.remove("active");
    }

    // Muestra el contenido de la pestaña seleccionada
    document.getElementById(tabName).style.display = "block";
    
    // Activa el botón de la pestaña seleccionada
    event.currentTarget.classList.add("active");
}