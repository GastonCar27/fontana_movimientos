let selectEmisor = document.querySelector('[name="emisor"]')
let emisor_buscador = document.querySelector('[name="buscador_emisor"]')
let timeout = null;
emisor_buscador.addEventListener('input',(evento) => {
buscar_en_input(evento,emisor_buscador,selectEmisor,timeout);
})