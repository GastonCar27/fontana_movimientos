let selectReceptor = document.querySelector('[name="receptor"]')
let receptor_buscador = document.querySelector('[name="buscador_receptor"]')
let timeout_2 = null;
receptor_buscador.addEventListener('input',(evento) => {
buscar_en_input(evento,receptor_buscador,selectReceptor,timeout_2);
})