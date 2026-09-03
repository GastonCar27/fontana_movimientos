window.addEventListener("load", function() {
    const cajaSelect = document.querySelector("#id_caja") || document.querySelector("#id_idBancoCuenta");
    const libroSelect = document.querySelector("select[id$='-libro']");

    if (cajaSelect && libroSelect) {
        cajaSelect.addEventListener("change", function() {
            const cajaId = this.value;
            
            // Opcional: Recorremos las opciones del select de libros y ocultamos/mostramos 
            // según un atributo personalizado o dejamos la validación del backend activa.
            Array.from(libroSelect.options).forEach(function(option) {
                if (!option.value) return; // Ignorar la opción vacía "---------"
                
                // Si la opción tuviera un atributo de caja (ej: data-caja="1"), se evaluaría aquí.
                // Por seguridad y estabilidad en Django, el filtro estricto se realiza en el backend con clean().
            });
        });
    }
});