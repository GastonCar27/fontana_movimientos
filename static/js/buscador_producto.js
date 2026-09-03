let selectProducto = document.querySelector('[name="producto"]')
let producto_buscador = document.querySelector('[name="buscador_producto"]')
let timeout_3 = null;
producto_buscador.addEventListener('input',(evento) => {
buscar_en_input(evento,producto_buscador,selectProducto,timeout_3);
})