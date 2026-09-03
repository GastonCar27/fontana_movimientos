
let bruto_input = document.querySelector('[name="bruto"]')
let tara_input = document.querySelector('[name="tara"]')
let descuento_input = document.querySelector('[name="descuento"]')
let total_input = document.querySelector('[name="total"]')
bruto_input.addEventListener('input', calculo_total)
tara_input.addEventListener('input', calculo_total)
descuento_input.addEventListener('input', calculo_total)

function calculo_total(){
    let bruto = parseFloat(bruto_input.value) || 0;
    let tara = parseFloat(tara_input.value) || 0;
    let descuento = parseFloat(descuento_input.value) || 0;
    total_input.value = bruto - tara - descuento
}


